"""
Functions for converting between nodal and zonal network representations.
"""

import pandas as pd
import pypsa
import numpy as np


def copy_net(oldnet, time_dependent_attrs=None):
    """
    Use only default columns to prevent issues when a pypsa net of a different version is used. 
    Do retain buses.country as a non-default attribute since its used for zone_name.

    Args:
        oldnet (_type_): _description_
        time_dependent_attrs (dict, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    net = pypsa.Network()
     # --- Copy static components ---
    bus_data_to_transfer = oldnet.buses.loc[:, oldnet.buses.columns.isin(pypsa.Network().buses.columns)]
    line_data_to_transfer = oldnet.lines.loc[:, oldnet.lines.columns.isin(pypsa.Network().lines.columns)]
    transformer_data_to_transfer = oldnet.transformers.loc[:, oldnet.transformers.columns.isin(pypsa.Network().transformers.columns)]
    storage_unit_data_to_transfer = oldnet.storage_units.loc[:, oldnet.storage_units.columns.isin(pypsa.Network().storage_units.columns)]
    link_data_to_transfer = oldnet.links.loc[:, oldnet.links.columns.isin(pypsa.Network().links.columns)]
    generator_data_to_transfer = oldnet.generators.loc[:, oldnet.generators.columns.isin(pypsa.Network().generators.columns)]
    load_data_to_transfer = oldnet.loads.loc[:, oldnet.loads.columns.isin(pypsa.Network().loads.columns)]
    carrier_data_to_transfer = oldnet.carriers.loc[:, oldnet.carriers.columns.isin(pypsa.Network().carriers.columns)]

    if 'country' in oldnet.buses.columns:
        bus_data_to_transfer.loc[:, 'country'] = oldnet.buses['country']

    if "sub_network" in oldnet.buses.columns:
        bus_data_to_transfer = bus_data_to_transfer.drop(columns=["sub_network"])
        line_data_to_transfer = line_data_to_transfer.drop(columns=["sub_network"])
        transformer_data_to_transfer = transformer_data_to_transfer.drop(columns=["sub_network"])
    
    assert pypsa.Network().buses.index.name == bus_data_to_transfer.index.name, "Bus index name does not match"
    assert pypsa.Network().lines.index.name == line_data_to_transfer.index.name, "Line index name does not match"
    assert pypsa.Network().transformers.index.name == transformer_data_to_transfer.index.name, "Transformer index name does not match"
    assert pypsa.Network().storage_units.index.name == storage_unit_data_to_transfer.index.name, "Storage unit index name does not match"
    assert pypsa.Network().links.index.name == link_data_to_transfer.index.name, "Link index name does not match"
    assert pypsa.Network().generators.index.name == generator_data_to_transfer.index.name, "Generator index name does not match"
    assert pypsa.Network().loads.index.name == load_data_to_transfer.index.name, "Load index name does not match"
    assert pypsa.Network().carriers.index.name == carrier_data_to_transfer.index.name,  "Carrier index name does not match"

     # --- Add components to new network ---

    net.add('Bus', oldnet.buses.index, **bus_data_to_transfer)
    net.add('Line', oldnet.lines.index, **line_data_to_transfer)
    net.add('Transformer', oldnet.transformers.index, **transformer_data_to_transfer)
    net.add('StorageUnit', oldnet.storage_units.index, **storage_unit_data_to_transfer)
    net.add('Link', oldnet.links.index, **link_data_to_transfer)
    net.add('Generator', oldnet.generators.index, **generator_data_to_transfer)
    net.add('Load', oldnet.loads.index, **load_data_to_transfer)
    net.add('Carrier', oldnet.carriers.index, **carrier_data_to_transfer)


    net.set_snapshots(oldnet.snapshots)

    if time_dependent_attrs is None:
        # copy all time-dependent attributes if none specified
        comp_list = ['generators_t', 'loads_t', 'storage_units_t', 'links_t', 'lines_t', 'transformers_t']
        for comp in comp_list:
            if hasattr(oldnet, comp):
                old_attr = getattr(oldnet, comp)
                new_attr = getattr(net, comp)
                for attr_name in old_attr:
                    if not old_attr[attr_name].empty:
                        old_df = old_attr[attr_name]
                        cols = old_df.columns
                        if attr_name in new_attr:
                            new_attr[attr_name].loc[:, cols] = old_df.values
                        else:
                            print(f"Skipping missing attribute {attr_name}")
    else:
        for attr_name in time_dependent_attrs:
            
            for attr in time_dependent_attrs[attr_name]:
                df = oldnet.__getattribute__(attr_name)[attr]
                if not df.empty:
                    net.__getattribute__(attr_name)[attr].loc[:, df.columns] = df.values

    return net


def nodal_to_zonal(n, bus_zone_map: pd.Series, interzonal_cap_factor: float=0.7, add_ntc_flag: bool=False):
    """
    Converts a nodal PyPSA-Eur network to a zonal network by:
    - Adding one bus per zone
    - Remapping all one-port components to zones
    - Removing all branch components (lines, links transformers)
    - Adding a single high-capacity link between each pair of connected zones
    based on the sum of capacities of inter-zonal lines and links in the original network
    """
    
    # Check if zone mapping exists
    if bus_zone_map.isna().any():
        raise ValueError(f"Some buses do not have a zone assigned: {bus_zone_map[bus_zone_map.isna()]}")

    # Remove the model if it exists to avoid issues during copying
    # Try-except needed because hasattr(n, 'model') raises an error if model not created. 
    try:
        if hasattr(n, 'model'):
            del(n.model) 
    except ValueError: 
        pass

    # Copy the original nodal network
    zonal_net = copy_net(n)

    # Store original mapping from nodal bus -> zone

    zones = bus_zone_map.unique()

    # STEP 1: Remap one-port components (generators, loads, storage_units, etc.) to zones
    for c in zonal_net.iterate_components(zonal_net.one_port_components):
        c.df.bus = c.df.bus.map(bus_zone_map)  
    

    # STEP 3: Create a new bus for each zone (at the mean x/y of all buses in that zone)
    for zone_name, buses_zone in n.buses.groupby(bus_zone_map):
        x_zone, y_zone= np.mean(buses_zone.x), np.mean(buses_zone.y)
        zonal_net.add("Bus", zone_name, x=x_zone, y=y_zone) 

    zonal_net.buses.index.name = "Bus"

    # Remove all original nodal buses (i.e. sub-zonal nodes) 
    zonal_net.remove("Bus", zonal_net.buses.index[~np.isin(zonal_net.buses.index, zones)])  

    # STEP 4: Aggregate inter-zonal capacities (lines and DC links)
    if not add_ntc_flag:
        zonal_net.remove('Line', zonal_net.lines.index)
        zonal_net.remove('Transformer', zonal_net.transformers.index)
        zonal_net.links.loc[:, 'bus0'] = zonal_net.links.bus0.map(bus_zone_map)
        zonal_net.links.loc[:, 'bus1'] = zonal_net.links.bus1.map(bus_zone_map)
        internal_links =  zonal_net.links.bus0 == zonal_net.links.bus1
        zonal_net.remove('Link', zonal_net.links.index[internal_links])
    else:
        add_ntcs(zonal_net, n, bus_zone_map, zones, interzonal_cap_factor)
    return zonal_net


def add_ntcs(zonal_net, n, bus_zone_map: pd.Series, zones, interzonal_cap_factor: float=0.7):
    interzonal_cap = pd.DataFrame(0.0, index=zones, columns=zones)
    for i in zones:
        for j in zones:
            if i == j:
                continue
            # Lines (AC): sum s_nom between zones
            mask_lines = (
                ((n.lines.bus0.map(bus_zone_map) == i) & (n.lines.bus1.map(bus_zone_map) == j)) |
                ((n.lines.bus0.map(bus_zone_map) == j) & (n.lines.bus1.map(bus_zone_map) == i))
            )
            # Links (DC): sum p_nom between zones
            mask_links = (
                ((n.links.bus0.map(bus_zone_map) == i) & (n.links.bus1.map(bus_zone_map) == j)) |
                ((n.links.bus0.map(bus_zone_map) == j) & (n.links.bus1.map(bus_zone_map) == i))
            )
            cap = interzonal_cap_factor * n.lines.loc[mask_lines, "s_nom"].sum() + \
                n.links.loc[mask_links, "p_nom"].sum()
            interzonal_cap.loc[i, j] = cap

    # # STEP 2: Remove all branch components (lines, links, transformers)
    for c in zonal_net.iterate_components(zonal_net.branch_components):
        zonal_net.remove(c.name, c.df.index)

    # STEP 5: Add a single bidirectional link between each connected zone pair
    for i in zones:
        for j in zones:
            if i < j and interzonal_cap.loc[i,j] > 0: # avoid duplicates
                zonal_net.add("Link",
                    name=f"{i}---{j}",
                    bus0=i,
                    bus1=j,
                    p_nom=interzonal_cap.loc[i,j],
                    p_min_pu=-1.0,
                    carrier="NTC"
                )

def nodal_to_zonal_nocopy(
    nodal_network: pypsa.Network,
    snapshots: None |  list[pd.Index] = None,
    zone_column: str = 'zone_name',
    bidirectional_links: bool = True
) -> pypsa.Network:
 # Validate inputs
    if zone_column not in nodal_network.buses.columns:
        raise ValueError(f"The column '{zone_column}' does not exist in the nodal network's buses")
    
    # Create a new zonal network
    zonal_network = pypsa.Network()
    
    # Set snapshots
    if snapshots is None:
        snapshots = nodal_network.snapshots
    else:
        zonal_network.set_snapshots(snapshots)
    
    # Add zonal buses (one for each unique zone in the nodal network)
    zones = nodal_network.buses[zone_column].unique()
    for zone in zones:
        zonal_network.add("Bus", zone, v_nom=nodal_network.buses.v_nom.mean())
    
    # Move generators to their respective zonal buses
    for gen in nodal_network.generators.itertuples():
        # Get the zone name for this generator's bus
        bus_name = gen.bus
        zone_name = nodal_network.buses.at[bus_name, zone_column]
        
        # Add the generator to the zonal network at its zone
        gen_dict = {col: getattr(gen, col) for col in nodal_network.generators.columns 
                   if col != 'bus' and hasattr(gen, col)}
        gen_dict['bus'] = zone_name  # Use the zone name as the bus
        
        zonal_network.add("Generator", gen.Index, **gen_dict)
    
    # Copy generator time series data if it exists
    for attr_name in nodal_network.generators_t:
        if attr_name != 'p':
            if not nodal_network.generators_t[attr_name].empty:
                zonal_network.generators_t[attr_name] = nodal_network.generators_t[attr_name].copy()
        
    # Move loads to their respective zonal buses
    if not nodal_network.loads.empty:
        for load in nodal_network.loads.itertuples():
            # Get the zone name for this load's bus
            bus_name = load.bus
            zone_name = nodal_network.buses.at[bus_name, zone_column]
            
            # Add the load to the zonal network at its zone
            load_dict = {col: getattr(load, col) for col in nodal_network.loads.columns 
                        if col != 'bus' and hasattr(load, col)}
            load_dict['bus'] = zone_name  # Use the zone name as the bus
            
            zonal_network.add("Load", load.Index, **load_dict)
        
        # Copy load time series data if it exists
        for attr_name in nodal_network.loads_t:
            if attr_name != 'p':
                if not nodal_network.loads_t[attr_name].empty:
                    zonal_network.loads_t[attr_name] = nodal_network.loads_t[attr_name].copy()
        
    
    # Copy carriers from the original network
    if hasattr(nodal_network, 'carriers') and not nodal_network.carriers.empty:
        for carrier in nodal_network.carriers.index:
            if carrier not in zonal_network.carriers.index:
                carrier_data = {col: nodal_network.carriers.at[carrier, col] 
                               for col in nodal_network.carriers.columns 
                               if carrier in nodal_network.carriers.index}
                zonal_network.add('Carrier', carrier, **carrier_data)
    
    return zonal_network