import xarray as xr

def filter_on_cnecs(
        da: xr.DataArray,
        cnecs: xr.Coordinates,
    ) -> xr.DataArray:
    """Filter a DataArray to include only the CNECs specified in the cnecs coordinates.
    """
    return da.sel(branch=cnecs['branch'])


def set_branch_coord_to_cnec(da: xr.DataArray, cnecs: xr.Coordinates) -> xr.DataArray:
    """Rename the 'branch' coordinate to 'cnec' and assign the CNEC coordinate values based on the branch names."""
    return da.assign_coords(cnec=('branch', cnecs['branch'].values)).swap_dims({"branch": "cnec"})