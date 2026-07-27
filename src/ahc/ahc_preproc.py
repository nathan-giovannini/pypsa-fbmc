import pypsa
import pandas as pd

def set_ahc(
        nodal_net: pypsa.Network,
        bus_zone_map,
    ):
    """Set up the network for advance hybrid coupling
    Steps:
    - Create the virtual hubs at start/landing location of HVDC lines
    - Replace the start/landing point of HVDC lines with the virtual hubs
    - Create a line connecting the virtual hubs to the AC node, while assigning flows from the original network

    Args:
        nodal_net (pypsa.Network): nodal network to which virtual hubs will be added.
        bus_zone_map: mapping from nodal buses to bidding zones

    Returns:
        nodal_net (pypsa.Network): Updated nodal network
    """

    link_zone0 = nodal_net.links.bus0.map(bus_zone_map)
    link_zone1 = nodal_net.links.bus1.map(bus_zone_map)

    cross_zone_links = nodal_net.links[link_zone0 != link_zone1]

    cross_zone_buses = pd.unique(
        pd.concat([cross_zone_links.bus0, cross_zone_links.bus1])
    )

    # Create VH buses
    for bus in cross_zone_buses:
        vh_bus = f"VH {bus}"

        if vh_bus not in nodal_net.buses.index:
            nodal_net.buses.loc[vh_bus] = nodal_net.buses.loc[bus]

    # Save original capacities before rewiring
    bus_caps = {}

    for bus in cross_zone_buses:
        connected = cross_zone_links[
            (cross_zone_links.bus0 == bus) |
            (cross_zone_links.bus1 == bus)
            ]

        # Assuming capacity column is p_nom
        bus_caps[bus] = connected.p_nom.sum() + 1

    # Replace the starting/landing point of HVDC lines to the virtual hubs
    bus_map = {bus: f"VH {bus}" for bus in cross_zone_buses}

    nodal_net.links.loc[cross_zone_links.index, "bus0"] = (
        nodal_net.links.loc[cross_zone_links.index, "bus0"]
        .replace(bus_map)
    )

    nodal_net.links.loc[cross_zone_links.index, "bus1"] = (
        nodal_net.links.loc[cross_zone_links.index, "bus1"]
        .replace(bus_map)
    )

    # Create the lines that connect the VH to the nodes
    for bus in cross_zone_buses:
        vh_bus = f"VH {bus}"

        # create the line
        nodal_net.add(
            "Line",
            f"{bus} <-> {vh_bus}",
            bus0=bus,
            bus1=vh_bus,
            s_nom=bus_caps[bus],  # original capacity + 1 MW
            x=0.0001,  # very small reactance
            r=0.0,
        )

        # assign values from the original solution
        connected = cross_zone_links[
            (cross_zone_links.bus0 == bus) |
            (cross_zone_links.bus1 == bus)
            ]
        p0 = sum(
            nodal_net.links_t.p0[l]
            if cross_zone_links.at[l, "bus0"] == bus
            else nodal_net.links_t.p1[l]
            for l in connected.index
        )
        nodal_net.lines_t.p0[f"{bus} <-> VH {bus}"] = p0
        nodal_net.lines_t.p1[f"{bus} <-> VH {bus}"] = -p0
        nodal_net.buses_t.p[vh_bus] = -p0 * 0

        nodal_net.add(
            "Load",
            f"{vh_bus} load",
            bus=vh_bus,
            p_set=pd.Series(0.0, index=nodal_net.snapshots)
        )

    vh_mask = nodal_net.buses.index.str.contains("vh", case=False, na=False)

    nodal_net.buses.loc[vh_mask, "zone_name"] = nodal_net.buses.index[vh_mask]
    bus_zone_map = nodal_net.buses['zone_name']


    return nodal_net, bus_zone_map

