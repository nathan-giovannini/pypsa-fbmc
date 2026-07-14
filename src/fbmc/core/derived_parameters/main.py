import pypsa
import xarray as xr

from .security_constrained import get_subnetwork_bodf
from .ram import calculate_ram
from .ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf_non_security_constrained, calc_subnet_ptdf_security_constrained
from ...settings import FBMCConfig
from fbmc.core.derived_parameters.base_case import get_base_flows_subnet_non_security_constrained, calc_base_net_positions_subnet, get_base_flows_subnet_security_constrained
from ...types import SubnetFBMCParameters, InputParametersSubnet


def calculate_fbmc_parameters_subnet(
    input_parameters_subnet: InputParametersSubnet,
    config: FBMCConfig
) -> SubnetFBMCParameters:
    return _calculate_fbmc_parameters_subnet(
        sub_network=input_parameters_subnet.base_case,
        gsk=input_parameters_subnet.gsk,
        cnecs=input_parameters_subnet.cnecs,
        config=config
    )

    


def _calculate_fbmc_parameters_subnet(
    sub_network: pypsa.SubNetwork,
    gsk: xr.DataArray,
    cnecs: xr.Coordinates,
    config: FBMCConfig
) -> SubnetFBMCParameters:
    """
    Orchestration function that takes a sub-network that represents the base case of that area, and other 
    input parameters (gsk, cnecs) and calculates the FBMC parameters (RAM, zPTDF)

    Parameters
    ----------
    sub_network : pypsa.SubNetwork
        The sub-network to calculate security constrainted parameters for. Represents the base case,
        so flows should be set. Must have a 'zone_name' column in its buses DataFrame to link it to the GSK.
    gsk : xr.DataArray
        Generation shift key mapping for each snapshot. Must contain at least the buses and zones in the subnetwork. 
    config : FBMCConfig
        Configuration object. 
    Returns
    -------
    FBMCParameters
        Dataclass containing upper and lower RAM, zPTDF and CNECs.
    """
    if sub_network.buses_i().size < 3:
        raise NotImplementedError("Sub-networks with less than 3 buses are not supported.")

    if config.add_security_constraints:
        bodf = get_subnetwork_bodf(sub_network, cnecs, config.security_constraint_bodf_size_threshold)
        nodal_ptdf = calc_subnet_ptdf_security_constrained(sub_network, bodf, bodf_columnwise_matrix_size_limit=config.security_constraint_bodf_columnwise_matrix_size_limit)
        base_flows_subnet = get_base_flows_subnet_security_constrained(sub_network, bodf, cnecs, bodf_columnwise_matrix_size_limit=config.security_constraint_bodf_columnwise_matrix_size_limit)
        cnecs = nodal_ptdf.coords['cnec']  # Update CNECs to match the potentially reduced set in apply_security_param_changes
    else:
        nodal_ptdf = get_subnetwork_ptdf_non_security_constrained(sub_network, cnecs)
        base_flows_subnet = get_base_flows_subnet_non_security_constrained(sub_network, cnecs)


    base_net_positions_subnet = calc_base_net_positions_subnet(sub_network)


    z_ptdf = calculate_zonal_ptdf(nodal_ptdf, gsk, cnecs)

    upper_ram, lower_ram = calculate_ram(
        sub_network, 
        z_ptdf, 
        base_flows_subnet, 
        net_positions_base_case=base_net_positions_subnet,
        reliability_margin_factor=config.reliability_margin_factor, 
        min_ram=config.min_ram
        )
    zones = sub_network.buses().zone_name.unique()
    fbmc_parameters = SubnetFBMCParameters(   
        upper_ram=upper_ram,
        lower_ram=lower_ram,
        z_ptdf=z_ptdf,
        cnecs=cnecs,
        zones=zones,
    )

    return fbmc_parameters