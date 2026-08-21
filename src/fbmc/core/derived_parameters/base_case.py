import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from fbmc.core.derived_parameters.security_constrained import apply_bodf
from fbmc.core.derived_parameters.utils import filter_on_cnecs, set_branch_coord_to_cnec

def _calc_base_flows(trafo_p0: pd.DataFrame, line_p0: pd.DataFrame) -> xr.DataArray:
    def to_da(df: pd.DataFrame, branch_component: str) -> xr.DataArray:
        return xr.DataArray(
            data=df.values,
            coords={'snapshot': df.index, 'branch': df.columns.values},
            dims=['snapshot', 'branch']
        ).assign_coords(branch_component=('branch', [branch_component] * df.shape[1]))
    return xr.concat([to_da(trafo_p0, 'Transformer'), to_da(line_p0, 'Line')], dim='branch')


def _calc_net_positions(buses_p: pd.DataFrame, zone_names: pd.Series) -> xr.DataArray:
    net_positions = (
        xr.DataArray(
            data=buses_p.values,
            coords={'snapshot': buses_p.index, 'Bus': buses_p.columns.values},
            dims=['snapshot', 'Bus']
        )
        .assign_coords(Zone=('Bus', zone_names.values))
        .groupby('Zone').sum('Bus')
    )
    if float(np.abs(net_positions.sum('Zone')).max()) > 1:
        raise ValueError("Net positions do not sum to zero.")
    return net_positions


def _get_base_flows_subnet(sub_network: pypsa.SubNetwork) -> xr.DataArray:
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""
    trafo_p0 = sub_network.pnl('transformers')['p0']
    lines_p0 = sub_network.pnl('lines')['p0']
    if trafo_p0.empty:
        trafo_p0 = pd.DataFrame(data=0,index=sub_network.snapshots, columns=sub_network.transformers_i(), dtype=float)
    if lines_p0.empty:
        lines_p0 = pd.DataFrame(data=0,index=sub_network.snapshots, columns=sub_network.lines_i(), dtype=float)
    return _calc_base_flows(trafo_p0, lines_p0)

def get_base_flows_subnet_non_security_constrained(sub_network: pypsa.SubNetwork, cnecs: xr.Coordinates) -> xr.DataArray:
    base_flows = _get_base_flows_subnet(sub_network)
    base_flows = filter_on_cnecs(base_flows, cnecs)
    base_flows = set_branch_coord_to_cnec(base_flows, cnecs)
    return base_flows

def get_base_flows_subnet_security_constrained(sub_network: pypsa.SubNetwork, bodf: xr.DataArray, cnecs: xr.Coordinates, bodf_columnwise_matrix_size_limit: int) -> xr.DataArray:
    base_flows = _get_base_flows_subnet(sub_network)
    base_flows_constrained = apply_bodf(base_flows, bodf)
    return base_flows_constrained


def get_base_flows(net: pypsa.Network) -> xr.DataArray:
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""
    return _calc_base_flows(net.transformers_t.p0, net.lines_t.p0)


def calc_base_net_positions_subnet(sub_network: pypsa.SubNetwork) -> xr.DataArray:
    """Calculate net positions for each zone based on bus power values."""
    buses_p0 = sub_network.pnl('buses')['p']
    if buses_p0.empty:
        buses_p0 = pd.DataFrame(data=0,index=sub_network.snapshots, columns=sub_network.buses_i(), dtype=float)
    return _calc_net_positions(buses_p0, sub_network.df('buses').zone_name)


def calc_base_net_positions(net: pypsa.Network) -> xr.DataArray:
    """Calculate net positions for each zone based on bus power values."""
    return _calc_net_positions(net.buses_t.p, net.buses.zone_name)
