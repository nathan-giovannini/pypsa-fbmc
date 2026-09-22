import pypsa
import pandas as pd
import networkx as nx
import xarray as xr


def find_bridges_sub_network(sub_network: pypsa.SubNetwork) -> pd.MultiIndex:
    """
    Identify bridges in the sub-network. A bridge is a line or transformer that, if removed, would increase the number of connected components in the network.
    These cannot be included as outages considered for CNECs since their outage would disconnect the network (BODF value of NaN).

    Parameters
    ----------
    sub_network : pypsa.SubNetwork

    Returns
    -------
    pd.MultiIndex
        MultiIndex of bridges in the network. (First level: branch type, second level: branch name)
    """

    G = sub_network.graph()
    bridges = list(nx.bridges(G))
    # find all components connecting the bus0 and bus1 pairs of the bridges
    bus0 = sub_network.branches().bus0
    bus1 = sub_network.branches().bus1
    
    bridge_branches = pd.MultiIndex(levels=[[], []], codes=[[], []])
    for u, v in bridges:
        mask = ((bus0 == u) & (bus1 == v)) | ((bus0 == v) & (bus1 == u))
        bridge_branches = bridge_branches.append(sub_network.branches().index[mask]) 

    bridge_branches_da = xr.DataArray(
        data=bridge_branches.values,
        coords={'branch': bridge_branches.get_level_values(1).values},
        dims=['branch']
    ).assign_coords(branch_component=('branch', bridge_branches.get_level_values(0).values)) 
    return bridge_branches_da

def find_bridges_network(net: pypsa.Network) -> xr.DataArray:
    """Loops over all sub-networks (connected AC) in a net and returns the bridge branches.

    Args:
        net (pypsa.Network)

    Returns:
        xr.DataArray: bridge branches with 'branch' dim and 'branch_component' coord.
    """
    return xr.concat(
        [find_bridges_sub_network(subnet) for subnet in net.sub_networks.obj],
        dim='branch'
    )