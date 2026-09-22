import pandas as pd
import pypsa
from typing import Sequence
from linopy import Model, LinearExpression
import xarray as xr
import logging
from dataclasses import dataclass

from .security_constraints import add_security_constraints
from .types import ReferenceDispatch

logger = logging.getLogger(__name__)

def select_flex_gens(net, flexible_carriers: Sequence[str]) -> pd.Index:
    return net.generators.index[
            net.generators.carrier.isin(flexible_carriers)
        ]



def run_redispatch(
        nodal_net:pypsa.Network, 
        dispatch_results:ReferenceDispatch, 
        adjustable_carriers=None, 
        security_constrained_flag=True, 
        branch_outages=None,
        load_shedding_cost=1000,
        deviation_factor=1.0,
        create_model_kwargs: dict[str, str] = None,
        solver_kwargs: dict[str, str] = None
        ) -> pypsa.Network:
    """Run redispatch either with or without N-1 security constraint. 

    Args:
        nodal_net (pypsa.Network): _description_
        dispatch_results (ReferenceDispatch): _description_
        adjustable_carriers (_type_, optional): _description_. Defaults to None.
        security_constrained_flag (bool, optional): _description_. Defaults to True.
        branch_outages (_type_, optional): _description_. Defaults to None.
        load_shedding_cost (int, optional): _description_. Defaults to 1000.

    Raises:
        ValueError: _description_

    Returns:
        pypsa.Network: _description_
    """
    if solver_kwargs is None:
        solver_kwargs = {}

    if create_model_kwargs is None:
        create_model_kwargs = {}

    if adjustable_carriers is None:
        adjustable_carriers = nodal_net.generators.carrier.unique()

    flex_gens_up = select_flex_gens(nodal_net, adjustable_carriers)
    add_load_shedding(nodal_net, load_shedding_cost=load_shedding_cost)


    nodal_net.buses.loc[:, 'sub_network'] = pd.NA
    nodal_net.lines.loc[:, 'sub_network'] = pd.NA
    nodal_net.transformers.loc[:, 'sub_network'] = pd.NA
    _set_nodal_objective(
        nodal_net,
        dispatch_results,
        flex_gens_up,
        deviation_factor,
        create_model_kwargs=create_model_kwargs,
    )
    if security_constrained_flag:
        add_security_constraints(nodal_net, branch_outages)
    logger.info("Solving redispatch optimization...")
    
    nodal_net.model.solve(**solver_kwargs)
    cost = get_costs(nodal_net)

    if nodal_net.model.termination_condition != 'optimal':
        raise ValueError("Redispatch optimization did not solve to optimality.")
    return nodal_net, cost


def add_load_shedding(net: pypsa.Network, load_shedding_cost: float) -> None:
    load_shedding_names = pd.Index(net.buses.index + "_load_shedding")
    existing_names = load_shedding_names.intersection(net.generators.index)
    if len(existing_names) > 0:
        net.generators.loc[existing_names, "marginal_cost"] = load_shedding_cost

    new_names = load_shedding_names.difference(existing_names)
    if new_names.empty:
        return

    net.add(
        "Generator",
        new_names,
        bus=new_names.str.removesuffix("_load_shedding"),
        p_nom=1e6,
        marginal_cost=load_shedding_cost,
        carrier="load-shedding",
    )



def _set_nodal_objective(
        net,
        dispatch_results,
        redispatchable_gen_inds,
        rt_deviation_factor,
        load_shedding_cost=1000,
        create_model_kwargs=None,
    ) -> None:
    '''Create a model instance and alter its objective from the standard PyPSA formulation.'''
    if net.model is None:
        # model = net.optimize.create_model()
        from fbmc.core.model.main import _create_model_without_meshed_split
        model = _create_model_without_meshed_split(net, create_model_kwargs=create_model_kwargs)
    else:
        model = net.model

    gen_p_old = xr.DataArray(
            dispatch_results.generators_p.values,
            coords=[net.snapshots, redispatchable_gen_inds],
            dims=["snapshot", "Generator"]
        )
    storage_unit_data = None
    if "StorageUnit-p_dispatch" in model.variables:
        storage_unit_data = StorageUnitData(
            p_old=xr.DataArray(
                dispatch_results.storage_units_p.values,
                coords=[net.snapshots, net.storage_units.index],
                dims=["snapshot", "StorageUnit"]
            ),
            soc_old=xr.DataArray(
                dispatch_results.storage_levels.values,
                coords=[net.snapshots, net.storage_units.index],
                dims=["snapshot", "StorageUnit"]
            ),
            water_values=dispatch_results.water_values,
            soc_min=0.0,
            soc_max=None
        )
    model.objective = _get_nodal_objective(
        model=model,
        net=net,
        rt_reference_price=100.0,
        rt_deviation_factor=rt_deviation_factor,
        gen_p_old=gen_p_old,
        redispatchable_gen_inds=redispatchable_gen_inds,
        storage_unit_data=storage_unit_data,
        load_shedding_cost=load_shedding_cost,
        load_shedding_gen_inds=net.generators.index[net.generators.carrier == 'load-shedding']
    )

    return 

def get_costs(
    net: pypsa.Network,
):
    gen_costs = (net.get_switchable_as_dense('Generator', 'marginal_cost') * net.generators_t.p).sum().sum()
    return gen_costs


# def get_water_values(net: pypsa.Network) -> xr.DataArray:
#     return xr.DataArray(
#     net.model.dual["StorageUnit-energy_balance"].values,  # or whatever your constraint is named
#     coords=[net.snapshots, net.storage_units.index],
#     dims=["snapshot", "StorageUnit"]
#     )


@dataclass
class StorageUnitData:
    p_old: xr.DataArray
    soc_old: xr.DataArray
    water_values: xr.DataArray
    soc_min: float
    soc_max: float | xr.DataArray
    

def _get_nodal_objective(
    model: Model,
    net: pypsa.Network,
    rt_reference_price: float,
    rt_deviation_factor: float,
    gen_p_old: xr.DataArray,
    redispatchable_gen_inds: list | None = None,
    storage_unit_data: StorageUnitData | None = None,
    delta_t=1.0,
    load_shedding_cost=1000,
    load_shedding_gen_inds=None,  # indices of dummy generators representing load shedding
):
    """
    Formulate the redispatch objective. 
    If rt_deviation_factor = 1, this corresponds to a pure minimization of dispatch deviations + a penalty for load shedding. 
    If rt_deviation_factor = 0, this corresponds to a pure cost minimization 
    """
    objective = 0
    # ============ GENERATORS ============
    gen_vars = model.variables["Generator-p"].sel(Generator=redispatchable_gen_inds)
    snapshots = gen_vars.coords["snapshot"]
    generators = gen_vars.coords["Generator"].sel(Generator=redispatchable_gen_inds)
    gen_p_old = gen_p_old.sel(Generator=redispatchable_gen_inds)

    # Deviation variables
    gen_delta_plus = model.add_variables(
        lower=0, coords=[snapshots, generators], name="Generator-delta_plus"
    )
    gen_delta_minus = model.add_variables(
        lower=0, coords=[snapshots, generators], name="Generator-delta_minus"
    )

    # Linearize: delta_plus - delta_minus = p - p_old
    model.add_constraints(
        gen_delta_plus - gen_delta_minus == gen_vars - gen_p_old,
        name="Generator-abs_split"
    )

    # Marginal cost as DataArray (snapshot, Generator)
    marginal_cost = xr.DataArray(
        net.get_switchable_as_dense('Generator', 'marginal_cost').loc[:, generators].values,
        coords=[snapshots, generators],
        dims=["snapshot", "Generator"]
    )

    # Blended price: marginal cost (economic) ↔ flat reference price (volume)
    gen_price_up = (
        (1 - rt_deviation_factor) * marginal_cost
        + rt_deviation_factor * rt_reference_price
    )
    gen_price_dn = (
        - (1 - rt_deviation_factor) * marginal_cost
        + rt_deviation_factor * rt_reference_price
    )

    gen_objective = (gen_price_up * gen_delta_plus + gen_price_dn * gen_delta_minus).sum()
    objective += gen_objective
    
    if storage_unit_data is not None:

        # --- Storage deviation variables ---
        storage_vars = model.variables["StorageUnit-p_dispatch"] - model.variables["StorageUnit-p_store"]
        snapshots = storage_vars.coords["snapshot"]
        storage_units = storage_vars.coords["StorageUnit"]

        delta_plus = model.add_variables(
            lower=0, coords=[snapshots, storage_units], name="StorageUnit-delta_plus"
        )
        delta_minus = model.add_variables(
            lower=0, coords=[snapshots, storage_units], name="StorageUnit-delta_minus"
        )

        # Linearized absolute value: delta_plus - delta_minus = p - p_old
        deviation = storage_vars - storage_unit_data.p_old
        model.add_constraints(
            delta_plus - delta_minus == deviation, name="StorageUnit-abs_split"
        )

        # --- SoC feasibility constraints ---
        if storage_unit_data.soc_max is None:
            soc_max = xr.DataArray(
                (net.storage_units.max_hours * net.storage_units.p_nom).values,
                coords=[storage_units]
            )
        else:
            soc_max = storage_unit_data.soc_max
        cumulative_delta = (storage_vars - storage_unit_data.p_old).cumsum("snapshot") * delta_t
  
        soc_new = - cumulative_delta + storage_unit_data.soc_old 

        model.add_constraints(soc_new >= storage_unit_data.soc_min, name="StorageUnit-soc_lower")
        model.add_constraints(soc_new <= soc_max, name="StorageUnit-soc_upper")

        # --- Storage objective term ---
        # water_values shape: (snapshot, StorageUnit)
        # Blend between true opportunity cost (water value) and flat reference price,
        # using the same rt_deviation_factor as generators for consistency
        storage_price_up = (
            (1 - rt_deviation_factor) * storage_unit_data.water_values
            + rt_deviation_factor * rt_reference_price
        )
        storage_price_dn = (
            - (1 - rt_deviation_factor) * storage_unit_data.water_values
            + rt_deviation_factor * rt_reference_price
        )

        storage_objective = (storage_price_up * delta_plus + storage_price_dn * delta_minus).sum() 
        objective += storage_objective
    # load shedding objective

    if load_shedding_gen_inds is not None:
        load_shedding_vars = model.variables["Generator-p"].sel(Generator=load_shedding_gen_inds)
        load_shedding_objective = (load_shedding_cost * load_shedding_vars).sum()
        
        objective += load_shedding_objective

    return objective