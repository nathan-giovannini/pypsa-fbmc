import pandas as pd
import pypsa
import xarray as xr
import linopy as lp

import logging
from collections.abc import Sequence
from pathlib import Path


import pandas as pd
from linopy import merge
from xarray import DataArray
from pypsa.components.common import as_components
from pypsa.descriptors import get_switchable_as_dense as as_dense




def add_net_position_variable(network: pypsa.Network, zones: list, snapshots: list) -> lp.Variable: 
    """
    Add Zone-p (net position) variables for a given PyPSA network.
    
    Args:
        network (pypsa.Network): The PyPSA network object containing the model.
        zones (list): List of zone names.
        snapshots (list): List of timestamps for the analysis period.
    
    Returns:
        linopy.Variable: A variable with dimensions ("snapshot", "Zone") representing 
            the zonal generation for each snapshot and zone.
    """
    
    zonal_generation = network.model.add_variables(
        name="Zone-p",
        coords={"snapshot": snapshots, "Zone": zones},  
        dims=["snapshot", "Zone"],  
        )
    
    return zonal_generation


def define_net_positions_constraint(
    zonal_net: pypsa.Network,
    sns: pd.Index = None,
    buses_input: Sequence | None = None,
    suffix: str = "",
) -> None:
    """Define net positions based on PyPSA 0.35.0 nodal balance constraint at
    https://github.com/PyPSA/PyPSA/blob/f26ee3052107aaa20511a6de543c85c39897ca78/pypsa/optimization/constraints.py
    The NPs contain the effect of Generators, Loads, StorageUnits, Links.
    Links are included to model transport by HVDC lines following Standard Hybrid Coupling
    """
    if sns is None:
        sns = zonal_net.snapshots
    m = zonal_net.model
    if buses_input is None:
        buses = zonal_net.buses.index.copy()
    else:
        buses = pd.Index(buses_input)
    args = [
        ["Generator", "p", "bus", 1],
        ["Store", "p", "bus", 1],
        ["StorageUnit", "p_dispatch", "bus", 1],
        ["StorageUnit", "p_store", "bus", -1],
        ["Link", "p", "bus0", -1],
        ["Link", "p", "bus1", as_dense(zonal_net, "Link", "efficiency", sns)],
    ]

    if not zonal_net.links.empty:
        for i in zonal_net.components.links.additional_ports:
            eff = as_dense(zonal_net, "Link", f"efficiency{i}", sns)
            args.append(["Link", "p", f"bus{i}", eff])


    exprs = []

    for arg in args:
        c, attr, column, sign = arg

        if zonal_net.static(c).empty:
            continue

        if "sign" in zonal_net.static(c):
            # additional sign necessary for branches in reverse direction
            sign = sign * zonal_net.static(c).sign

        expr = DataArray(sign) * m[f"{c}-{attr}"]
        cbuses = zonal_net.static(c)[column][lambda ds: ds.isin(buses)].rename("Bus")

        #  drop non-existent multiport buses which are ''
        if column in ["bus" + i for i in zonal_net.c.links.additional_ports]:
            cbuses = cbuses[cbuses != ""]

        expr = expr.sel({c: cbuses.index})

        if expr.size:
            exprs.append(expr.groupby(cbuses).sum())

    zonal_production = merge(exprs, join="outer").reindex(Bus=buses)
    active = zonal_net.loads.query("active").index
    fixed_load = (
        (-as_dense(zonal_net, "Load", "p_set", sns, active) * zonal_net.loads.sign[active])
        .T.groupby(zonal_net.loads.bus[active])
        .sum()
        .T.reindex(columns=buses, fill_value=0)
        .set_axis(buses, axis=1)
    )

    # the name for multi-index is getting lost by groupby before pandas 1.4.0
    # TODO remove once we bump the required pandas version to >= 1.4.0


    empty_nodal_balance = (zonal_production.vars == -1).all("_term")
    fixed_load = DataArray(fixed_load)
    if empty_nodal_balance.any():
        if (empty_nodal_balance & (fixed_load != 0)).any().item():
            msg = "Empty LHS with non-zero RHS in nodal balance constraint."
            raise ValueError(msg)

        mask = ~empty_nodal_balance
    else:
        mask = None

    if suffix:
        zonal_production = zonal_production.rename(Bus=f"Bus{suffix}")
        fixed_load = fixed_load.rename(Bus=f"Bus{suffix}")
        if mask is not None:
            mask = mask.rename(Bus=f"Bus{suffix}")

    zonal_production = zonal_production.rename({"Bus": "Zone"})
    if fixed_load.coords.get("Bus") is not None:
        print('Fixed load has coordinate Bus')
        fixed_load = fixed_load.rename({"Bus": "Zone"})
    zonal_net.model.add_constraints(zonal_net.model.variables['Zone-p'] - (zonal_production - fixed_load), "=", 0, name=f"Zone{suffix}-definition", mask=mask)
