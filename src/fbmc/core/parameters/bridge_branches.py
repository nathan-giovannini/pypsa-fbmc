import networkx as nx
import pypsa
import xarray as xr


def _empty_bridge_array() -> xr.DataArray:
    return xr.DataArray(
        data=[],
        coords={
            "branch": [],
            "branch_component": ("branch", []),
        },
        dims=["branch"],
    )


def find_bridges_sub_network(sub_network: pypsa.SubNetwork) -> xr.DataArray:
    """
    Identify bridge branches in a sub-network.

    A bridge branch is a line or transformer whose removal disconnects the network.
    The returned value is an ``xarray.DataArray`` with dimension ``branch`` and the
    coordinate ``branch_component`` describing whether each branch is a ``Line`` or
    ``Transformer``.
    """
    graph = sub_network.graph()
    bridges = list(nx.bridges(graph))
    bus0 = sub_network.branches().bus0
    bus1 = sub_network.branches().bus1

    branch_components: list[str] = []
    branch_names: list[str] = []
    for u, v in bridges:
        mask = ((bus0 == u) & (bus1 == v)) | ((bus0 == v) & (bus1 == u))
        matching = sub_network.branches().index[mask]
        branch_components.extend(matching.get_level_values(0).tolist())
        branch_names.extend(matching.get_level_values(1).tolist())

    if not branch_names:
        return _empty_bridge_array()

    return xr.DataArray(
        data=branch_names,
        coords={"branch": branch_names},
        dims=["branch"],
    ).assign_coords(branch_component=("branch", branch_components))


def find_bridges_network(net: pypsa.Network) -> xr.DataArray:
    """
    Return all bridge branches across every sub-network in ``net``.

    The return value is an ``xarray.DataArray`` with dimension ``branch`` and the
    coordinate ``branch_component``.
    """
    bridge_arrays = [find_bridges_sub_network(subnet) for subnet in net.sub_networks.obj]
    non_empty = [bridge_array for bridge_array in bridge_arrays if bridge_array.sizes["branch"] > 0]
    if not non_empty:
        return _empty_bridge_array()
    return xr.concat(non_empty, dim="branch")
