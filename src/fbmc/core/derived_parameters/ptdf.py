import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from fbmc.core.derived_parameters.security_constrained import apply_bodf
from fbmc.core.derived_parameters.utils import filter_on_cnecs, set_branch_coord_to_cnec


def _get_subnetwork_ptdf(sub_network: pypsa.SubNetwork) -> xr.DataArray:
    """
    Extract PTDF matrix from the network model.
    Returns PTDF matrix and associated sub_network.
    """
    sub_network.calculate_PTDF()
    ptdf = xr.DataArray(
        sub_network.PTDF,
        coords={
            'branch': sub_network.branches_i().droplevel(0).values, 
            'Bus': sub_network.buses_o 
        },
        dims=['branch', 'Bus']
    ).assign_coords(branch_component=('branch', sub_network.branches_i().get_level_values(0)))
    return ptdf

def get_subnetwork_ptdf_non_security_constrained(sub_network: pypsa.SubNetwork, cnecs: xr.Coordinates) -> xr.DataArray:
    ptdf = _get_subnetwork_ptdf(sub_network)
    ptdf = filter_on_cnecs(ptdf, cnecs)
    ptdf = set_branch_coord_to_cnec(ptdf, cnecs)
    return ptdf

def calc_subnet_ptdf_security_constrained(sub_network: pypsa.SubNetwork, bodf: xr.DataArray, bodf_columnwise_matrix_size_limit: int) -> xr.DataArray:
    nodal_ptdf = _get_subnetwork_ptdf(sub_network)
    nodal_ptdf = apply_bodf(nodal_ptdf, bodf, matrix_size_limit=bodf_columnwise_matrix_size_limit)
    return nodal_ptdf

def calculate_zonal_ptdf(
        ptdf: pd.DataFrame, 
        gsk: xr.DataArray, 
        cnecs: pd.Index | pd.MultiIndex,
        ) -> xr.DataArray:
    """
    Transform nodal PTDF to zonal PTDF using Generation Shift Keys (GSK).
    PTDF shape: (branches, buses). buses are only the ones in the subnetwork.
    GSK shape: (zones, buses, ..). buses can be all buses in the full net. 
    CNECs shape: (branches) for N-0 CNECs, or (branches, outaged_branches) for N-1 CNECs
    zPTDF shape: (CNECs, zones). 
    """

    if not ptdf.coords['Bus'].isin(gsk.coords['Bus']).all():
        raise ValueError("PTDF columns must include GSK buses") #PTDF is based on subnetwork, GSK is based on full network

    gsk_subnet = gsk.sel(Bus=ptdf.coords['Bus']) # Align GSK to PTDF columns based on zone names
    # gsk_filtered = gsk_filtered.loc[gsk_filtered.sum(axis=1) > 1e-6]  # Remove zones with zero GSK in this subnetwork


    assert np.abs(gsk_subnet.sum('Bus') - 1).max() < 1e-6, "GSK rows must sum to 1"
    z_ptdf = xr.dot(gsk_subnet, ptdf, dims='Bus')

    # if not isinstance(cnecs, pd.MultiIndex):
    #     breakpoint()  # need to check if needed
    #     z_ptdf = z_ptdf.sel(cnec=cnecs) # filter on cnecs
    return z_ptdf


def filter_zptdf(
        z_ptdf: xr.DataArray,
        sensitivity_threshold: float = 0.05
        ):
    """
    Filter zonal PTDF to include only those with a signficant sensitivity to NP changes.
    """
    z_ptdf_mask = z_ptdf.max(dim=['zones', 'snapshot']) - z_ptdf.min(dim=['zones', 'snapshot']) > sensitivity_threshold
    z_ptdf_filtered = z_ptdf.where(z_ptdf_mask, drop=True)
    return z_ptdf_filtered