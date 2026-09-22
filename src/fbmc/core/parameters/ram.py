import pandas as pd
import pypsa
import xarray as xr
from typing import Any 


def calculate_flow_reliability_margin(line_capacities: pd.Series, reliability_margin_factor: float = 0.0) -> pd.Series:
    """Calculate Flow Reliability Margin (FRM) for transmission lines.
    
    Args:
        line_capacities: Thermal capacity limits in MW
        reliability_margin_factor: Safety factor (0-1, default 0.1)
        
    Returns:
        Flow Reliability Margin values in MW
    """
    if not 0 <= reliability_margin_factor <= 1:
        raise ValueError("Reliability margin factor must be between 0 and 1")
    
    if (line_capacities < 0).any():
        raise ValueError("Line capacities must be positive")

    return line_capacities * reliability_margin_factor


def calculate_branch_capacity(sub_network: pd.DataFrame) -> xr.DataArray:
    """Calculate the capacity of each branch (line or transformer) in the sub-network."""
    branches = sub_network.branches()
    # name multiindex levels: (type, name)
    branches.index.set_names(['branch_component', 'branch'], inplace=True)
    
    return xr.DataArray(
        data=branches.s_nom.values,
        coords={
            'branch': branches.index.get_level_values('branch'),
        },
        dims=['branch']
    ).assign_coords(
        branch_component=('branch', branches.index.get_level_values('branch_component'))
    )

    

def calculate_ram(
        sub_network: pypsa.SubNetwork,
        zonal_ptdf: xr.DataArray,
        base_flows: pd.DataFrame,
        net_positions_base_case: pd.DataFrame,
        min_ram: float,
        reliability_margin_factor: float,
    ) -> xr.DataArray:
    """
    Calculate the Remaining Available Margin (RAM) for a given power network.
    Optional: Add a zonal PTDF term to the RAM calculation: zPTDF * net_positions.

    Args:
        network: PyPSA network containing the initial state
        zonal_ptdf_dict: dict {snapshot: pd.DataFrame[zones, CNECs]}
        min_ram: Minimum RAM value as fraction of capacity (default 0.0)
        reliability_margin_factor: Safety factor for reliability margin (default 0.1)

    Returns:
        Tuple[DataFrame, DataFrame] Upper and lower RAM values, with dimensions (CNECs, snapshots)
    """

    if sub_network.transformers_i().isin(sub_network.lines_i()).any():
        raise ValueError(f"Transformers and lines cannot have the same names. Overlapping names: {sub_network.transformers_i().intersection(sub_network.lines_i()).tolist()}")

    cnecs = zonal_ptdf.coords['cnec']   # need to make the rest of the code to be able to handle full CNEC description. 

    # ideally, we have a CNEC labelling representing tuples of (line, outage, direction)
    # upper_ram_dict, lower_ram_dict = {}, {}       

    branch_capacity = calculate_branch_capacity(sub_network)

    # Calculate flow reliability margin
    frm = calculate_flow_reliability_margin(branch_capacity, 
                                            reliability_margin_factor=reliability_margin_factor)

    safety_adjusted_capacity = branch_capacity - frm

    # Reindex safety_adjusted_capacity to match CNECs. 
    # if isinstance(cnecs, pd.MultiIndex):
    #     safety_adjusted_capacity = (
    #         safety_adjusted_capacity
    #         .reindex(cnecs.get_level_values(0))  # align by branch names
    #         .set_axis(cnecs)                     # assign full MultiIndex
    #     )

    reference_flow = base_flows.sel(cnec=cnecs) - xr.dot(zonal_ptdf, net_positions_base_case, dims='Zone')
    cnec_branches = cnecs['branch'].values 

    cap_at_cnec = safety_adjusted_capacity.sel(branch=xr.DataArray(cnec_branches, dims='cnec')).reset_coords(drop=True)
    upper_ram = cap_at_cnec - reference_flow
    lower_ram = - cap_at_cnec - reference_flow

    if min_ram > 0:
        upper_ram = upper_ram.clip(min=min_ram * cap_at_cnec)
        lower_ram = lower_ram.clip(max=-min_ram * cap_at_cnec)

    assert (upper_ram >= lower_ram).values.all(), "Upper RAM must be greater than lower RAM for all CNECs"

    return upper_ram, lower_ram


