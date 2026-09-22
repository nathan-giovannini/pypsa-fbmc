"""
Add the FBMC constraints to the network
"""

import pypsa
import pandas as pd
import xarray as xr
from copy import deepcopy

from .fbmc_constraints import construct_lower_ram_constraint, construct_upper_ram_constraint, construct_zonal_balance_constraint
from .zonal_generation import define_net_positions_constraint, add_net_position_variable


def create_zonal_generation(network: pypsa.Network):
    """
    Main function to add zonal generation variables and constraints to the network.
    """
    # Add the zonal generation variable to the model
    zones = network.buses.index.to_list()
    snapshots = network.snapshots.to_list()
    add_net_position_variable(network, zones, snapshots)
    define_net_positions_constraint(network)

    return 

def _remove_coords(
    data_array: xr.DataArray, 
    coords_to_remove: list[str]
) -> xr.DataArray:
    """
    Remove unwanted coordinates from the DataArray to avoid issues with linopy.
    """
    for coord in coords_to_remove:
        if coord in data_array.coords:
            data_array = data_array.drop(coord)
    return data_array


def add_fbmc_constraints(
        network: pypsa.Network, 
        sub_network_name: str,
        zones: pd.Index,
        zPTDF_xr: xr.DataArray,
        upper_RAM_xr: xr.DataArray,
        lower_RAM_xr: xr.DataArray,
        upper_ram_only_flag: bool = False,
    ) -> pypsa.Network:
    """
    Main function to add FBMC constraints to the network.
    
    Parameters
    ----------
    network : pypsa.Network
        The zonal PyPSA network to add constraints to.
    zPTDF_df : pd.DataFrame or dict of pd.DataFrame
        Either a single DataFrame containing zPTDF values (static GSKs),
        or a dictionary of DataFrames with snapshots as keys (snapshot-based GSKs).
    RAM_df : pd.DataFrame
        DataFrame containing RAM values.
    """
    # xarray conversion
    unwanted_coords = [
        'branch_component',
        'branch',
        'outage',
        'outage_component'
    ]
    zPTDF_xr = _remove_coords(zPTDF_xr, unwanted_coords)
    upper_RAM_xr = _remove_coords(upper_RAM_xr, unwanted_coords)
    lower_RAM_xr = _remove_coords(lower_RAM_xr, unwanted_coords)

    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    upper_cne_constraint = construct_upper_ram_constraint(
        zPTDF_xr, 
        network.model.variables["Zone-p"],
        upper_RAM_xr, 
        )
    network.model.add_constraints(upper_cne_constraint, name=f"CNEC-upper-RAM-subnet-{sub_network_name}")

    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    if not upper_ram_only_flag:
        lower_cne_constraint = construct_lower_ram_constraint(
            zPTDF_xr, 
            network.model.variables["Zone-p"], 
            lower_RAM_xr, 
            )
        network.model.add_constraints(lower_cne_constraint, name=f"CNEC-lower-RAM-subnet-{sub_network_name}")

    # Ensure the Net Position of all zones adds up to 0
    zonal_balance_constraint = construct_zonal_balance_constraint(
        network.model.variables["Zone-p"].sel(Zone=zones)
    )
    network.model.add_constraints(zonal_balance_constraint, name=f"Zonal_balance-subnet-{sub_network_name}")

    

def remove_original_constraints(network):
    """"
    Remove the original constraints introduced by pyPSA from the network model.
    
    Parameters
    ----------
    network : pypsa.Network
        The zonal PyPSA network from which to remove constraints.

    """
    network.model.remove_constraints("Bus-nodal_balance")
    
    # if it exists, remove the bus-meshed-nodal_balance constraint as well.
    if "Bus-meshed-nodal_balance" in network.model.constraints:
        network.model.remove_constraints("Bus-meshed-nodal_balance")

def remove_original_constraints_by_bus(network, buses):
    """"
    Remove the original constraints introduced by pyPSA from the network model.
    
    Parameters
    ----------
    network : pypsa.Network
        The zonal PyPSA network from which to remove constraints.

    """
    constraint_to_keep = deepcopy(network.model.constraints["Bus-nodal_balance"].drop_sel(Bus=buses))
    network.model.remove_constraints("Bus-nodal_balance")
    network.model.add_constraints(constraint_to_keep, name="Bus-nodal_balance")
    
    # if it exists, remove the bus-meshed-nodal_balance constraint as well.
    if "Bus-meshed-nodal_balance" in network.model.constraints:
        raise NotImplementedError("The function remove_original_constraints_by_subnet is not implemented yet. It should remove the Bus-meshed-nodal_balance constraint only for the buses in the sub-network, but this requires modifications to the pyPSA model structure that have not been implemented yet.")
        network.model.remove_constraints("Bus-meshed-nodal_balance")
