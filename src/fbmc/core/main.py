# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 13:01:07 2025

@author: ameldekok
"""

import pypsa
import pandas as pd
import logging
import linopy as lp 
import xarray as xr

from .derived_parameters.main import calculate_fbmc_parameters_subnet
from ..types import SubnetFBMCParameters, InputParameters

from .constraints.main import create_zonal_generation
from .constraints.main import add_fbmc_constraints, remove_original_constraints, remove_original_constraints_by_bus
from ..settings import FBMCConfig

logging.basicConfig(level=logging.INFO)


def _create_model_without_meshed_split(network: pypsa.Network, create_model_kwargs: dict = None) -> lp.Model:
    """Create PyPSA model without separate meshed/weakly-meshed nodal balance."""
    from pypsa.optimization import optimize as optimize_module

    if create_model_kwargs is None:
        create_model_kwargs = {}

    original_get_meshed = optimize_module.get_strongly_meshed_buses

    def _no_meshed_buses(n: pypsa.Network, threshold: int = 45) -> pd.Index:
        return pd.Index([], name=n.buses.index.name)

    optimize_module.get_strongly_meshed_buses = _no_meshed_buses

    model = network.optimize.create_model(**create_model_kwargs)
    logging.info("Created optimization model without meshed split.")

    optimize_module.get_strongly_meshed_buses = original_get_meshed

    return model


        
def calculate_fbmc_parameters(
        input_parameters: InputParameters,
        config: FBMCConfig = FBMCConfig(),
    ) -> dict[str, SubnetFBMCParameters]:
    """
    Set up the FBMC model by calculating parameters and adding constraints.
    
    Parameters
    ----------
    basecase_nodal_network : pypsa.Network
        The base case nodal network to be used for FBMC.
    zonal_net : pypsa.Network
        The target zonal network to be used for FBMC.
    config : FBMCConfig
        Configuration object for FBMC parameters.
    
    Returns
    -------
    pypsa.Network
        The target zonal network with added FBMC constraints.
    """

    if input_parameters.base_case.sub_networks.empty:
        input_parameters.base_case.determine_network_topology()
    logging.info(f"Determined {len(input_parameters.base_case.sub_networks)} sub-networks in the base case nodal network.")
    fbmc_parameters: dict[str, SubnetFBMCParameters] = {}

    for sub_network_name in input_parameters.base_case.sub_networks.index:
        input_parameters_subnet = input_parameters.for_subnet(sub_network_name)
        if input_parameters_subnet.base_case.buses_i().size < 3:
            logging.warning(f"Sub-network {sub_network_name} has less than 3 buses. Skipping FBMC parameter calculation and constraint addition for this sub-network.")
            continue

        

        subnet_fbmc_parameters: SubnetFBMCParameters = calculate_fbmc_parameters_subnet(
            input_parameters_subnet,
            config,
            )
        fbmc_parameters[sub_network_name] = subnet_fbmc_parameters
    
    return fbmc_parameters


def setup_fbmc_model(
        zonal_net: pypsa.Network,
        input_parameters: InputParameters,
        config: FBMCConfig,
    ) -> tuple[lp.Model, dict[str, SubnetFBMCParameters]]:
    """Set up the FBMC optimization model by calculating FBMC parameters and adding the corresponding constraints to the zonal network.

    Args:
        zonal_net (pypsa.Network): _description_
        basecase_nodal_network (pypsa.Network): _description_
        gsk (pd.DataFrame | dict[pd.Timestamp, pd.DataFrame]): _description_
        gsk_strategy (GSKStrategy): _description_
        config (FBMCConfig, optional): _description_. Defaults to FBMCConfig().

    Returns:
        lp.Model: linopy model with FBMC constraints added
        dict[str, SubnetFBMCParameters]: dict of FBMC parameters for each sub-network
    """

    fbmc_parameters = calculate_fbmc_parameters(
        input_parameters=input_parameters, config=config)

    if zonal_net.model is None:
        model = _create_model_without_meshed_split(zonal_net, create_model_kwargs=config.create_model_kwargs)
    
    create_zonal_generation(zonal_net)
    remove_original_constraints_loop(zonal_net, input_parameters.base_case)
    add_fbmc_constraints_loop(
        zonal_net, 
        fbmc_parameters, 
        config.upper_ram_only_flag
    )

    return model, fbmc_parameters


def remove_original_constraints_loop(
    zonal_net: pypsa.Network,
    basecase_nodal_network: pypsa.Network
    ) -> None:
    """Remove original nodal balance constraint from `zonal_net` for zones that have more than three buses such that FBMC constraints can be generated. 

    Args:
        zonal_net (pypsa.Network): Zonal net for which original constraints should be removed
        basecase_nodal_network (pypsa.Network): Base case nodal network to determine sub-network sizes
    """
    if basecase_nodal_network.sub_networks.empty:
        basecase_nodal_network.determine_network_topology()

    sub_net_lengths = basecase_nodal_network.sub_networks.obj.apply(lambda x: len(x.buses()))

    #remove_original_constraints(zonal_net)

    if not (sub_net_lengths < 3).any():
        remove_original_constraints(zonal_net)
        return

    for name, sub_network_df in basecase_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_df.obj
        if sub_network.buses_i().size >= 3:
            zones = sub_network.buses().zone_name.unique()
            zonal_buses = zonal_net.buses.index[zonal_net.buses.index.isin(zones)]
            remove_original_constraints_by_bus(zonal_net, zonal_buses)
    return


def add_fbmc_constraints_loop(
        zonal_net: pypsa.Network,
        fbmc_parameters: dict[str, SubnetFBMCParameters],
        upper_ram_only_flag: bool,
    ) -> None:
    """Add FBMC constraints for each sub-network in the zonal network."""

    for sub_network_name, parameters in fbmc_parameters.items():
        zPTDF_xr = parameters.z_ptdf
        upper_RAM_xr = parameters.upper_ram
        lower_RAM_xr = parameters.lower_ram
        zones = parameters.zones

        add_fbmc_constraints(
            zonal_net,
            sub_network_name,
            zones,
            zPTDF_xr,
            upper_RAM_xr,
            lower_RAM_xr,
            upper_ram_only_flag
        )
        
        

