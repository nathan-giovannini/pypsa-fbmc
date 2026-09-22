import linopy as lp
import pandas as pd
import xarray as xr


def create_load_zone_mapping(loads: pd.DataFrame) -> xr.DataArray:
    """
    Create an xarray mapping of loads to their respective zones.
    """
    load_zone_mapping = xr.DataArray(
        [loads.at[load, 'bus'] for load in loads.index],
        dims=["Load"],
        coords={"Load": loads.index}
    )
    return load_zone_mapping


def create_load_zone_mask(load_zone_mapping: xr.DataArray, zones: list) -> xr.DataArray:
    """
    Create a mask for the loads in the zones.
    """
    zone_da = xr.DataArray(zones, dims = ["Zone"], coords = {"Zone": zones})
    mask = zone_da == load_zone_mapping
    return mask


def get_zonal_loads(load_zone_mask, loads_t_pset):
    """
    Get the total loads per zone (xarray)
    """
    loads_xr = xr.DataArray(
        loads_t_pset.T,
        dims=["Load", "snapshot"],
        coords={"Load": loads_t_pset.columns, "snapshot": loads_t_pset.index}
    )
    return (loads_xr * load_zone_mask).sum(dim="Load")

# ---- Constraint Construction ----

def construct_lower_ram_constraint(zPTDF: xr.DataArray, net_positions: lp.LinearExpression, lower_ram: xr.DataArray):
    return (zPTDF * net_positions).sum(dim="Zone") >= lower_ram


def construct_upper_ram_constraint(zPTDF: xr.DataArray, net_positions: lp.LinearExpression, upper_ram: xr.DataArray):
    return (zPTDF * net_positions).sum(dim="Zone") <= upper_ram


def construct_zonal_balance_constraint(net_positions: lp.LinearExpression):
    return net_positions.sum(dim="Zone") == 0

