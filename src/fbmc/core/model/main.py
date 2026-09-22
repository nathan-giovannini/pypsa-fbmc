import logging

import linopy as lp
import pandas as pd
import pypsa

from ...settings import FBMCConfig
from ...types import InputParameters, SubnetFBMCParameters
from ..parameters.main import calculate_fbmc_parameters_subnet
from .constraints.main import (
    add_fbmc_constraints,
    create_zonal_generation,
    remove_original_constraints,
    remove_original_constraints_by_bus,
)

logger = logging.getLogger(__name__)


def _create_model_without_meshed_split(
    network: pypsa.Network,
    create_model_kwargs: dict | None = None,
) -> lp.Model:
    """Create a PyPSA model without separate meshed/weakly-meshed nodal balances."""
    from pypsa.optimization import optimize as optimize_module

    create_model_kwargs = create_model_kwargs or {}
    original_get_meshed = optimize_module.get_strongly_meshed_buses

    def _no_meshed_buses(n: pypsa.Network, threshold: int = 45) -> pd.Index:
        return pd.Index([], name=n.buses.index.name)

    optimize_module.get_strongly_meshed_buses = _no_meshed_buses
    try:
        model = network.optimize.create_model(**create_model_kwargs)
    finally:
        optimize_module.get_strongly_meshed_buses = original_get_meshed

    logger.info("Created optimization model without meshed split.")
    return model


def calculate_fbmc_parameters(
    input_parameters: InputParameters,
    config: FBMCConfig,
) -> dict[str, SubnetFBMCParameters]:
    if input_parameters.base_case.sub_networks.empty:
        input_parameters.base_case.determine_network_topology()

    logger.info(
        "Determined %s sub-networks in the base-case nodal network.",
        len(input_parameters.base_case.sub_networks),
    )
    fbmc_parameters: dict[str, SubnetFBMCParameters] = {}
    for sub_network_name in input_parameters.base_case.sub_networks.index:
        subnet_inputs = input_parameters.for_subnet(sub_network_name)
        if subnet_inputs.base_case.buses_i().size < 3:
            logger.warning(
                "Sub-network %s has less than 3 buses. Skipping FBMC parameter calculation.",
                sub_network_name,
            )
            continue

        subnet_parameters = calculate_fbmc_parameters_subnet(
            subnet_inputs,
            config,
        )
        if subnet_parameters is None:
            continue
        fbmc_parameters[sub_network_name] = subnet_parameters

    return fbmc_parameters


def setup_fbmc_model(
    zonal_net: pypsa.Network,
    input_parameters: InputParameters,
    config: FBMCConfig,
) -> tuple[lp.Model, dict[str, SubnetFBMCParameters]]:
    fbmc_parameters = calculate_fbmc_parameters(input_parameters=input_parameters, config=config)
    model = _create_model_without_meshed_split(
        zonal_net,
        create_model_kwargs=config.create_model_kwargs,
    )

    create_zonal_generation(zonal_net)
    remove_original_constraints_loop(zonal_net, input_parameters.base_case)
    add_fbmc_constraints_loop(
        zonal_net,
        fbmc_parameters,
        config.upper_ram_only_flag,
    )
    return model, fbmc_parameters


def remove_original_constraints_loop(
    zonal_net: pypsa.Network,
    base_case_nodal_network: pypsa.Network,
) -> None:
    if base_case_nodal_network.sub_networks.empty:
        base_case_nodal_network.determine_network_topology()

    sub_net_lengths = base_case_nodal_network.sub_networks.obj.apply(lambda x: len(x.buses()))
    if not (sub_net_lengths < 3).any():
        remove_original_constraints(zonal_net)
        return

    for _, sub_network_df in base_case_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_df.obj
        if sub_network.buses_i().size >= 3:
            zones = sub_network.buses().zone_name.unique()
            zonal_buses = zonal_net.buses.index[zonal_net.buses.index.isin(zones)]
            remove_original_constraints_by_bus(zonal_net, zonal_buses)


def add_fbmc_constraints_loop(
    zonal_net: pypsa.Network,
    fbmc_parameters: dict[str, SubnetFBMCParameters],
    upper_ram_only_flag: bool,
) -> None:
    for sub_network_name, parameters in fbmc_parameters.items():
        add_fbmc_constraints(
            zonal_net,
            sub_network_name,
            parameters.zones,
            parameters.z_ptdf,
            parameters.upper_ram,
            parameters.lower_ram,
            upper_ram_only_flag,
        )
