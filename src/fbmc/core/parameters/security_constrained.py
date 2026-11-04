import pypsa
import pandas as pd
import numpy as np
import xarray as xr


BODF_COLUMNWISE_MATRIX_SIZE_LIMIT = 5_000_000


def get_subnetwork_bodf(
        sub_network: pypsa.SubNetwork, 
        cnecs: xr.Coordinates,
        min_size_threshold: float = 0.05
        ) -> xr.DataArray:
    """
    Extract BODF values for each (branch, outage) pair in cnecs from a sub-network.

    Parameters
    ----------
    sub_network : pypsa.SubNetwork
        The sub-network to extract BODF values from.
    cnecs : xr.Coordinates
        Coordinates where the first level contains the outages and the second level contains the branches.
    min_size_threshold : float
        Minimum absolute value of BODF to include in the result, to reduce computational size. Default is 0.05.
    """
    sub_network.calculate_BODF()
    branches_multi = sub_network.branches_i()
    branch_names = branches_multi.get_level_values('name')

    cnec_branches = cnecs['branch'].values
    cnec_outages = cnecs['outage'].values

    # Integer positions of the cnec pairs directly
    row_idx = pd.Index(branch_names).get_indexer(cnec_branches)
    col_idx = pd.Index(branch_names).get_indexer(cnec_outages)

    bodf = xr.DataArray(
        sub_network.BODF[row_idx, col_idx],
        coords={'cnec': cnecs['cnec'],
                'branch_component': cnecs['branch_component'],
                'outage_component': cnecs['outage_component']},
        dims=['cnec']
    )
    bodf = bodf.where(np.abs(bodf) > min_size_threshold, drop=True)

    return bodf


def calc_bodf_cnec_values(BODF: pd.DataFrame, cnecs: pd.MultiIndex) -> pd.Series:
    """
    Extract BODF values for each (line, outage) pair in cnecs.

    Parameters
    ----------
    BODF : pd.DataFrame
        The Branch Outage Distribution Factor matrix with shape (branches x outages).
    cnecs : pd.MultiIndex
        MultiIndex where the first level contains the outages and the second level contains the branches.

    Returns
    -------
    pd.Series
        Series containing the BODF values for each (line, outage) pair in cnecs.
    """
    

    branches = cnecs.get_level_values('branch')
    outages = cnecs.get_level_values('outage')

    # Get integer positions for each (branch, outage) pair
    row_idx = BODF.index.get_indexer(branches)
    col_idx = BODF.columns.get_indexer(outages)

    # Extract only the matching diagonal elements
    bodf_cnec_values = BODF.values[row_idx, col_idx]
    return bodf_cnec_values
    # return pd.Series(bodf_cnec_values, index=cnecs, name='BODF_value')

def _should_use_columnwise_bodf(
        da: xr.DataArray,
        bodf: xr.DataArray,
        matrix_size_limit: int | None,
        ) -> bool:
    """Select a RAM-saving path when the intermediate matrix would be large."""
    if matrix_size_limit is None:
        return False

    estimated_elements = bodf.coords['cnec'].size * da.size / da.coords['branch'].size
    return estimated_elements > matrix_size_limit


def _apply_bodf_numpy(
        values: np.ndarray,
        branch_positions: np.ndarray,
        outage_positions: np.ndarray,
        bodf_values: np.ndarray,
        ) -> np.ndarray:
    """Apply BODF to a branch-first NumPy array."""
    branch_values = np.take(values, branch_positions, axis=0)
    outage_values = np.take(values, outage_positions, axis=0)
    return branch_values + outage_values * bodf_values.reshape((-1,) + (1,) * (values.ndim - 1))


def apply_bodf_columnwise(da: xr.DataArray, bodf: xr.DataArray) -> xr.DataArray:
    """Apply BODF one column at a time to lower peak RAM usage.
    Do computation in numpy for speed and possibility to use numba in the future if useful.
    Note: fully ai generated but test shows the same result as the vectorized version. 
    """
    missing = (set(bodf.coords['branch'].values) | set(bodf.coords['outage'].values)) \
              - set(da.coords['branch'].values)
    if missing:
        raise KeyError(f"BODF contains branch/outage labels missing from da: {missing}")

    branch_axis = da.get_axis_num('branch')
    values = np.moveaxis(da.values, branch_axis, 0)

    branch_index = da.get_index('branch')
    branch_positions = branch_index.get_indexer(bodf.coords['branch'].values)
    outage_positions = branch_index.get_indexer(bodf.coords['outage'].values)
    if (branch_positions < 0).any() or (outage_positions < 0).any():
        raise KeyError("BODF contains branch/outage labels missing from da")

    result_values = _apply_bodf_numpy(
        values,
        branch_positions,
        outage_positions,
        np.asarray(bodf.values),
    )

    other_dims = [dim for dim in da.dims if dim != 'branch']
    coords = {
        'cnec': bodf.coords['cnec'],
        'branch_component': bodf.coords['branch_component'],
        'outage_component': bodf.coords['outage_component']
    }

    coords.update({dim: da.coords[dim] for dim in other_dims})
    return xr.DataArray(
        result_values,
        coords=coords,
        dims=['cnec', *other_dims],
    )

def apply_bodf(
        da: xr.DataArray,
        bodf: xr.DataArray,
        matrix_size_limit: int | None = BODF_COLUMNWISE_MATRIX_SIZE_LIMIT,
        ) -> xr.DataArray:
    """Assumes df has index branches.
    Applies outage scenarios defined by the BODF. 
    Returns a new df with index as (line, outage) pairs and columns the same as the input df, containing the adjusted flows for each outage scenario.
    """

    if _should_use_columnwise_bodf(da, bodf, matrix_size_limit):
        return apply_bodf_columnwise(da, bodf)

    # bare indexers on cnec — no branch/outage coords to collide
    outage_idx = xr.DataArray(bodf.coords['outage'].values, dims='cnec')
    branch_idx = xr.DataArray(bodf.coords['branch'].values, dims='cnec')

    # da[outage] row per cnec, scaled by bodf
    
    outage_term = da.sel(branch=xr.DataArray(bodf.coords['outage'].values, dims='cnec')).reset_coords(drop=True) * bodf.reset_coords(drop=True)

    # da[monitored branch] row per cnec
    base_term = da.sel(branch=branch_idx).drop_vars('branch')

    result = base_term + outage_term
    drop_names = [name for name in ['cnec', 'branch', 'outage'] if name in result.coords]
    if drop_names:
        result = result.drop_vars(drop_names)
    result = result.assign_coords(
        cnec=bodf.coords['cnec'],
        branch_component=xr.DataArray(bodf.coords['branch_component'].values, dims='cnec'),
        outage_component=xr.DataArray(bodf.coords['outage_component'].values, dims='cnec'),
    )
                                      
    return result



def reindex_to_cnec_nr(df: pd.DataFrame | pd.Series, cnecs_df: pd.DataFrame, from_index: str ='branch') -> pd.DataFrame | pd.Series:
    """
    Reindex the given DataFrame or Series to match the CNEC numbering.

    Parameters
    ----------
    df : pd.DataFrame | pd.Series
        The DataFrame or Series to reindex.
    cnecs_df : pd.DataFrame
        The CNEC DataFrame containing the new index.
    from_index : str
        The column name to use as the new index.

    Returns
    -------
    pd.DataFrame | pd.Series
        The reindexed DataFrame or Series.
    """
    return (
        df.reindex(index=cnecs_df[from_index])
        .set_axis(cnecs_df.index)
    )





