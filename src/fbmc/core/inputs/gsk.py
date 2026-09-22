import numpy as np
import pandas as pd
import pypsa
import xarray as xr
from scipy.stats import norm, halfnorm

from .helpers import (
    get_uncertain_elements,
    initialize_gen_difference,
    introduce_variation_to_network,
    calculate_generation_difference,
    process_generation_difference,
    silence_output,
)

from ...enums import GSKStrategy


LOAD_SHEDDING_CARRIER = "load-shedding"


def gsk_dict_to_xarray(gsk: dict) -> xr.DataArray:
    first = gsk[next(iter(gsk))]
    if not isinstance(first, pd.DataFrame):
        raise ValueError("GSK must be a dictionary of DataFrames.")
    return xr.DataArray(
        data=list(gsk.values()),
        coords={
            'snapshot': list(gsk.keys()),
            'Zone': first.index,
            'Bus': first.columns,
        },
        dims=['snapshot', 'Zone', 'Bus']
    )


def _filter_generators_for_gsk(
    generators: pd.DataFrame,
    excluded_carrier: str = LOAD_SHEDDING_CARRIER,
) -> pd.DataFrame:
    if 'carrier' not in generators.columns:
        return generators
    return generators.loc[~(generators['carrier'] == excluded_carrier)].copy()


def calculate_gsk(nodal_net: pypsa.Network,
                  gsk_strategy: GSKStrategy | str,
                  gsk_kwargs: dict) -> xr.DataArray:
    """
    Calculate the Generator Shift Key (GSK) of every node in the network.
    
    The GSK represents how changes in a zone's net position are distributed among
    its nodes. It is used to transform nodal PTDFs to zonal PTDFs for flow-based
    market coupling.
    
    Parameters
    ----------
    nodal_net : pypsa.Network
        The network object containing generators and buses.
    gsk_strategy : GSKStrategy | str
        The strategy to use for calculating the GSK.
    gsk_kwargs : dict
        Keyword arguments for GSK calculation.
    
    Returns
    -------
    xr.DataArray
        GSK values with dimensions ['snapshot', 'Zone', 'Bus'].
        Values represent the share of a zone's net position change allocated to each bus.
    
    Raises
    ------
    ValueError
        If an unknown GSK method is specified or if required network components are missing.
    """
    if isinstance(gsk_strategy, str):
        gsk_strategy = GSKStrategy(gsk_strategy)

    # Validate network has required components
    if len(nodal_net.generators) == 0:
        raise ValueError("Network contains no generators. Cannot calculate GSK.")
    
    if 'zone_name' not in nodal_net.buses.columns:
        raise ValueError("Buses in network must have 'zone_name' attribute for GSK calculation.")

    # Select method based on config
    if gsk_strategy == GSKStrategy.ADJUSTABLE_CAP:
        gsk = gsk_adjustable_cap(nodal_net.generators, nodal_net.buses, **gsk_kwargs)
        gsk = {snap: gsk.copy() for snap in nodal_net.snapshots}
    elif gsk_strategy == GSKStrategy.ITERATIVE_UNCERTAINTY:
        gsk = gsk_iterative_uncertainty(
            nodal_net,
            **gsk_kwargs
        )
    elif gsk_strategy == GSKStrategy.CURRENT_GENERATION:
        gsk = gsk_current_generation(nodal_net.generators, nodal_net.generators_t.p, nodal_net.buses)
    elif gsk_strategy == GSKStrategy.MERIT_ORDER:
        gsk = calc_merit_order_based_gsk(nodal_net, **gsk_kwargs)
    elif gsk_strategy == GSKStrategy.BUS_P:
        gsk = gsk_bus_p(nodal_net)
    elif gsk_strategy == GSKStrategy.P_NOM:
        gsk_generators = _filter_generators_for_gsk(nodal_net.generators)
        gsk = gsk_p_nom(gsk_generators, nodal_net.buses)
    else:
        raise ValueError(f"Unknown method: {gsk_strategy}. Supported methods are: 'P_NOM', 'MERIT_ORDER','ADJUSTABLE_CAP', 'ITERATIVE_UNCERTAINTY', 'CURRENT_GENERATION', 'ITERATIVE_FBMC'.")
    
    if type(gsk) is pd.DataFrame:
        gsk = {snapshot: gsk for snapshot in nodal_net.snapshots}
    for snapshot in nodal_net.snapshots:
        assert bool((
            np.isclose(
            np.diag(
                gsk[snapshot]
                .T
                .groupby(nodal_net.buses.zone_name)
                .sum()
                .reindex(index=nodal_net.buses.zone_name.unique(), columns=nodal_net.buses.zone_name.unique())
                .values
                ),
            1.0
            )).all()), f"GSK matrix should be normalized to 1 per zone, and should not have non-zeros for buses outside the zone. For snapshot {snapshot}, GSK matrix diagonal is {np.diag(gsk[snapshot].T.groupby(nodal_net.buses.zone_name).sum().reindex(index=nodal_net.buses.zone_name.unique(), columns=nodal_net.buses.zone_name.unique()).values)}"
        # Calculate parameters

    if isinstance(gsk, pd.DataFrame):
        gsk = {snapshot: gsk.copy() for snapshot in nodal_net.snapshots}

    return gsk_dict_to_xarray(gsk)

def gsk_iterative_uncertainty(
    network: pypsa.Network,
    uncertain_carriers: list[str] = ['offshore-wind', 'onshore-wind'],
    num_iterations: int = 10,
    gen_variation_std_dev: float = 0.1,
    load_variation_std_dev: float = 0.1
) -> dict[pd.Timestamp, pd.DataFrame]:
    """
    Calculate GSK using Monte Carlo simulation with uncertainty in generation and load.
    
    This method:
    1. Creates variations of the base case with uncertainty in generation and load
    2. Optimizes each variation to see how generation responds
    3. Uses these responses to determine which generators are most flexible
    4. Constructs GSK values based on the average response of generators
    
    Parameters
    ----------
    network : pypsa.Network
        The network to calculate GSKs for
    uncertain_carriers : list
        list of generation technologies with uncertainty (e.g. wind, solar)
    num_iterations : int
        Number of Monte Carlo iterations (higher = more stable results)
    gen_variation_std_dev : float
        Standard deviation for generator variation as fraction of nominal power
    load_variation_std_dev : float
        Standard deviation for load variation as fraction of nominal power
        
    Returns
    -------
    dict[pd.Timestamp, pd.DataFrame]
        dictionary of DataFrames containing GSK values for each bus and zone, one per snapshot
    """
    # Validate inputs
    if num_iterations < 1:
        raise ValueError("Number of iterations must be at least 1")
    if gen_variation_std_dev < 0 or load_variation_std_dev < 0:
        raise ValueError("Standard deviations must be non-negative")

    # Run the network once to get initial generation and load values
    try:
        with silence_output():
            network.optimize(solver_name='gurobi')
    except Exception as e:
        raise RuntimeError(f"Failed to optimize initial network state: {e}")

    # Collect the loads and gens (wind) with uncertainty
    uncertain_gens, uncertain_loads = get_uncertain_elements(network, uncertain_carriers)
    
    # Initialize the generation difference array
    gen_difference = initialize_gen_difference(network, num_iterations)

    # Perform stochastic sampling
    for i in range(num_iterations):
        # Create a fresh copy for this iteration
        stochastic_network = network.copy(snapshots=network.snapshots)
        
        # Apply uncertainty to generators and loads
        introduce_variation_to_network(
            stochastic_network,
            uncertain_gens,
            uncertain_loads,
            gen_variation_std_dev,
            load_variation_std_dev,
        )

        # Calculate generation differences after optimization
        gen_difference[i,:,:] = calculate_generation_difference(stochastic_network)
        
    # Process results and calculate GSK
    return process_generation_difference(gen_difference, network)





def gsk_iterative_merit_order(
    network: pypsa.Network,
    uncertain_carriers: list[str] = ['offshore-wind', 'onshore-wind'],
    num_iterations: int = 10,
    gen_variation_std_dev: float = 0.1,
    load_variation_std_dev: float = 0.1
) -> dict[pd.Timestamp, pd.DataFrame]:
    """
    Calculate GSK using Monte Carlo simulation with uncertainty in generation and load.
    
    This method:
    1. Creates variations of the base case with uncertainty in generation and load
    2. Optimizes each variation to see how generation responds
    3. Uses these responses to determine which generators are most flexible
    4. Constructs GSK values based on the average response of generators
    
    Parameters
    ----------
    network : pypsa.Network
        The network to calculate GSKs for
    uncertain_carriers : list
        list of generation technologies with uncertainty (e.g. wind, solar)
    num_iterations : int
        Number of Monte Carlo iterations (higher = more stable results)
    gen_variation_std_dev : float
        Standard deviation for generator variation as fraction of nominal power
    load_variation_std_dev : float
        Standard deviation for load variation as fraction of nominal power
        
    Returns
    -------
    dict[pd.Timestamp, pd.DataFrame]
        dictionary of DataFrames containing GSK values for each bus and zone, one per snapshot
    """
    # Validate inputs
    if num_iterations < 1:
        raise ValueError("Number of iterations must be at least 1")
    if gen_variation_std_dev < 0 or load_variation_std_dev < 0:
        raise ValueError("Standard deviations must be non-negative")

    # Run the network once to get initial generation and load values
    try:
        with silence_output():
            network.optimize(solver_name='gurobi')
    except Exception as e:
        raise RuntimeError(f"Failed to optimize initial network state: {e}")

    # Collect the loads and gens (wind) with uncertainty
    uncertain_gens, uncertain_loads = get_uncertain_elements(network, uncertain_carriers)
    
    # Initialize the generation difference array
    gen_difference = initialize_gen_difference(network, num_iterations)

    # Perform stochastic sampling
    for i in range(num_iterations):
        # Create a fresh copy for this iteration
        stochastic_network = network.copy(snapshots=network.snapshots)
        
        # Apply uncertainty to generators and loads
        introduce_variation_to_network(
            stochastic_network,
            uncertain_gens,
            uncertain_loads,
            gen_variation_std_dev,
            load_variation_std_dev,
        )

        # Store generator values before optimization
        gen_t_before_optimization = stochastic_network.generators_t.p.copy()

        stochastic_network.optimize.create_model()
        

        try:
            # Run optimization silently using the silence_output context manager
            with silence_output():
                stochastic_network.optimize(solver_name="gurobi", solver_options={"OutputFlag": 0})
        except Exception as e:
            raise RuntimeError(f"Network optimization failed: {e}")
        
        # Calculate generation differences (transpose to match expected dimensions)
        gen_difference[i,:,:] = (stochastic_network.generators_t.p - gen_t_before_optimization).values.T

    # Process results and calculate GSK
    return process_generation_difference(gen_difference, network)


def gsk_adjustable_cap(
        generators: pd.DataFrame, 
        buses: pd.DataFrame, 
        adjustable_carriers: None | tuple[str] = None,
        ) -> pd.DataFrame:
    """
    Calculate the Generation Shift Key (GSK) based on adjustable energy capacity.
    
    This method assigns GSK values proportional to adjustable generation capacity at each node,
    assuming adjustable plants are the main flexible resources that respond to changes
    in net position.
    
    If a zone has no adjustable generators, GSK values are distributed evenly
    across all generators in that zone.
    
    Parameters
    ----------
    generators : pd.DataFrame
        The DataFrame containing generator data with columns ['carrier', 'bus', 'p_nom'].
    buses : pd.DataFrame
        The DataFrame containing bus data with column ['zone_name'].
    
    Returns
    -------
    pd.DataFrame
        A DataFrame containing the GSKs for each bus-zone pair.
    
    Raises
    ------
    ValueError
        If no generators are found in one or more zones.
    """
    # Constants
    ZONE_COLUMN = 'zone_name'
    BUS_COLUMN = 'bus'
    P_NOM_COLUMN = 'p_nom'
    
    if adjustable_carriers is None:
        adjustable_carriers = generators['carrier'].unique().tolist()

    # Filter generators for adjustable carriers and remove up and down regulators
    adjustable_generators = generators[generators['carrier'].isin(adjustable_carriers)]
    adjustable_generators = adjustable_generators[~(adjustable_generators.index.str.endswith('--rd_up') | adjustable_generators.index.str.endswith('--rd_dn'))]
    
    if len(adjustable_generators) == 0:
        raise ValueError("No adjustable generators found in the network.")
    
    # Assign zone names to adjustable generators based on their bus
    adjustable_zones = buses.loc[adjustable_generators[BUS_COLUMN]][ZONE_COLUMN]
    adjustable_generators = adjustable_generators.assign(zone_name=adjustable_zones.values)
        
    # Get the total adjustable capacity per zone and per bus
    total_adjustable_capacity_per_zone = adjustable_generators.groupby(ZONE_COLUMN)[P_NOM_COLUMN].sum()
    adjustable_capacity_per_node = adjustable_generators.groupby([BUS_COLUMN, ZONE_COLUMN])[P_NOM_COLUMN].sum().to_frame()
    
    # Identify zones with zero adjustable capacity
    zero_capacity_zones = total_adjustable_capacity_per_zone[total_adjustable_capacity_per_zone == 0].index.tolist()
    
    # Get all zones from the network
    all_zones = buses[ZONE_COLUMN].unique()
    
    # Create an adjustable capacity matrix (initially zeros)
    adjustable_capacity_matrix = pd.DataFrame(0.0, index=all_zones, columns=buses.index)
    
    # Fill in the matrix with adjustable capacity values
    for (bus, zone), capacity in adjustable_capacity_per_node.itertuples():
        adjustable_capacity_matrix.at[zone, bus] = capacity
    
    # Initialize GSK matrix with zeros 
    gsk_matrix = pd.DataFrame(0.0, index=all_zones, columns=buses.index)
    
    # For zones with adjustable capacity, calculate GSK based on capacity
    zones_with_adjustable = total_adjustable_capacity_per_zone[total_adjustable_capacity_per_zone > 0].index
    for zone in zones_with_adjustable:
        gsk_matrix.loc[zone] = adjustable_capacity_matrix.loc[zone] / total_adjustable_capacity_per_zone[zone]
    
    # For zones with zero adjustable capacity, distribute GSK evenly across all generators in the zone
    for zone in zero_capacity_zones:
        # Create zone_generators using a safer approach to avoid alignment issues
        # First map buses to zones for all generators
        gen_buses = generators[BUS_COLUMN].values
        bus_zones = buses.loc[gen_buses, ZONE_COLUMN].values
        # Create a boolean mask for generators in this zone
        in_zone_mask = (bus_zones == zone)
        zone_generators = generators.loc[in_zone_mask]
        
        if len(zone_generators) == 0:
            raise ValueError(f"Zone {zone} has no generators at all. Cannot calculate GSK.")
        
        # Group generators by bus and count
        bus_generator_counts = zone_generators.groupby(BUS_COLUMN).size()
        
        # Assign equal weight to each bus proportional to number of generators at that bus
        for bus, count in bus_generator_counts.items():
            gsk_matrix.at[zone, bus] = count / len(zone_generators)
    
    # Find any missing zones not covered by adjustable or zero-adjustable processing
    missing_zones = set(all_zones) - set(zones_with_adjustable) - set(zero_capacity_zones)
    
    # For any remaining zones, also distribute GSK evenly across all generators
    for zone in missing_zones:
        # Use the same safer approach as above
        gen_buses = generators[BUS_COLUMN].values
        bus_zones = buses.loc[gen_buses, ZONE_COLUMN].values
        in_zone_mask = (bus_zones == zone)
        zone_generators = generators.loc[in_zone_mask]
        
        if len(zone_generators) == 0:
            raise ValueError(f"Zone {zone} has no generators at all. Cannot calculate GSK.")
        
        bus_generator_counts = zone_generators.groupby(BUS_COLUMN).size()
        for bus, count in bus_generator_counts.items():
            gsk_matrix.at[zone, bus] = count / len(zone_generators)
    
    gsk_matrix.index.name = None
    
    # Ensure that the sum of GSKs in each zone is 1
    if not np.all(np.isclose(gsk_matrix.sum(axis=1), 1)):
        raise ValueError("GSK calculation error: The sum of GSKs in every zone should be 1.")
    
    gsk_matrix.reindex(index=buses['zone_name'].unique(), columns=buses.index, fill_value=0)
    gsk_matrix.index.name = "Zone"
    return gsk_matrix


def gsk_current_generation(generators: pd.DataFrame, generators_t_p: pd.DataFrame, buses: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    """
    Calculate the GSK based on current generation values for each snapshot.

    Parameters
    ----------
    generators : pd.DataFrame
        DataFrame containing static generator data (must include 'bus').
    generators_t_p : pd.DataFrame
        DataFrame containing time-series generator power output (p). 
        Index: snapshots, Columns: generator names.
    buses : pd.DataFrame
        DataFrame containing bus data (must include 'zone_name').

    Returns
    -------
    dict[pd.Timestamp, pd.DataFrame]
        A dictionary where keys are snapshots and values are DataFrames 
        containing the GSKs (Index: zones, Columns: buses).
        
    Raises
    ------
    ValueError
        If generators_t_p is empty, or if mapping generators to zones fails.
    """
    ZONE_COLUMN = 'zone_name'
    BUS_COLUMN = 'bus'

    if generators_t_p.empty:
        raise ValueError("generators_t_p DataFrame cannot be empty.")
        
    if 'bus' not in generators.columns:
         raise ValueError("Generators DataFrame must include 'bus' column.")
         


    # Map generators to zones and buses
    try:
        bus_to_zone = buses[ZONE_COLUMN].to_dict()
        gen_to_bus = generators[BUS_COLUMN].to_dict()
        gen_to_zone = {gen: bus_to_zone.get(gen_to_bus.get(gen)) 
                       for gen in generators.index if gen in generators_t_p.columns} # Only consider generators present in generators_t_p
    except KeyError as e:
        raise ValueError(f"Failed to map generators to zones or buses: {e}")

    all_zones = sorted(buses[ZONE_COLUMN].unique())
    all_buses = sorted(buses.index)
    gsk_matrices = {}

    for snapshot in generators_t_p.index:
        snapshot_generation = generators_t_p.loc[snapshot]
        
        # Create DataFrame for the snapshot's generation with bus and zone info
        gen_data_snapshot = pd.DataFrame({'p': snapshot_generation})
        gen_data_snapshot['bus'] = gen_data_snapshot.index.map(gen_to_bus)
        gen_data_snapshot['zone'] = gen_data_snapshot['bus'].map(bus_to_zone)
        
        # Drop generators that couldn't be mapped (e.g., if bus is missing)
        gen_data_snapshot = gen_data_snapshot.dropna(subset=['bus', 'zone'])

        # Calculate total generation per zone for this snapshot
        total_generation_per_zone = gen_data_snapshot.groupby('zone')['p'].sum()
        
        # Calculate generation per bus for this snapshot
        generation_per_bus = gen_data_snapshot.groupby('bus')['p'].sum()

        # Initialize GSK matrix for the snapshot
        gsk_matrix = pd.DataFrame(0.0, index=all_zones, columns=all_buses)

        for zone in all_zones:
            zone_total_gen = total_generation_per_zone.get(zone, 0)
            
            # Get buses belonging to this zone
            buses_in_zone = buses.index[buses[ZONE_COLUMN] == zone].tolist()

            if zone_total_gen > 1e-6: # Use a small threshold to avoid division by zero issues
                # Calculate GSK based on generation share
                for bus in buses_in_zone:
                    bus_gen = generation_per_bus.get(bus, 0)
                    if bus_gen > 0:
                         gsk_matrix.at[zone, bus] = bus_gen / zone_total_gen
            else:
                # Distribute GSK evenly among buses in the zone if total generation is zero
                if buses_in_zone:
                    gsk_matrix.loc[zone, buses_in_zone] = 1.0 / len(buses_in_zone)

        # Ensure rows sum to 1 (handle potential floating point inaccuracies)
        gsk_matrix = gsk_matrix.apply(lambda row: row / row.sum() if row.sum() > 1e-6 else row, axis=1)

        # Re-apply equal distribution for zero-sum rows if normalization failed
        for zone in all_zones:
             if gsk_matrix.loc[zone].sum() < 1e-6:
                 buses_in_zone = buses.index[buses[ZONE_COLUMN] == zone].tolist()
                 if buses_in_zone:
                     gsk_matrix.loc[zone, buses_in_zone] = 1.0 / len(buses_in_zone)

        gsk_matrix.index.name = None # Remove index name
        gsk_matrices[snapshot] = gsk_matrix

    return gsk_matrices


def gsk_p_nom(generators: pd.DataFrame, buses: pd.DataFrame) -> pd.DataFrame:
    """Calculate the GSK based on the nominal power of generators in each zone. 
    !! DOES NOT INCLUDE STORAGE !!

    Args:
        generators (pd.DataFrame): DataFrame containing generator data with columns ['bus', 'p_nom'].
        buses (pd.DataFrame): DataFrame containing bus data with column ['zone_name'].

    Returns:
        pd.DataFrame: GSK matrix with zones as index and buses as columns.
    """
    gen_zone_map = generators.bus.map(buses['zone_name'])
    total_p_nom_per_zone = generators.groupby(gen_zone_map)['p_nom'].sum()
    p_nom_per_node = generators.groupby([generators.bus, gen_zone_map])['p_nom'].sum().to_frame()
    
    gsk_matrix = pd.DataFrame(0.0, index=buses['zone_name'].unique(), columns=buses.index)
    
    for (bus, zone), p_nom in p_nom_per_node.itertuples():
        if total_p_nom_per_zone[zone] > 0:
            gsk_matrix.at[zone, bus] = p_nom / total_p_nom_per_zone[zone]

    # Fallback: if no eligible generation remains in a zone, distribute equally across zone buses.
    zone_names = buses['zone_name']
    for zone in zone_names.unique():
        if np.isclose(gsk_matrix.loc[zone].sum(), 0.0):
            buses_in_zone = zone_names[zone_names == zone].index
            if len(buses_in_zone) > 0:
                gsk_matrix.loc[zone, buses_in_zone] = 1.0 / len(buses_in_zone)
    
    gsk_matrix.index.name = None
    return gsk_matrix


def calc_merit_order_based_gsk(network: pypsa.Network,
                     standard_deviation: int | float | dict | pd.Series,

                     ) -> dict[pd.Index, pd.DataFrame]:
    """Calculate the GSK based on the merit order of generators in each zone. 
    !! DOES NOT INCLUDE STORAGE !!

    Args:
        network (pypsa.Network): nodal network. buses must have 'zone_name' attribute.
        standard_deviation (int | float | dict | pd.Series): _description_

    Returns:
        dict[pd.Index, pd.DataFrame]: GSKs for each snapshot.
    """

    gen_zone_map = network.generators.bus.map(network.buses['zone_name'])

    reference_generation_zones = network.generators_t.p.T.groupby(gen_zone_map).sum().T
    
    if isinstance(standard_deviation, (int | float)):
        standard_deviation = pd.Series(standard_deviation, index=reference_generation_zones.columns)
    isk_dict = {}
    for snapshot in network.snapshots:
        isk_dict_snapshot = {}
        for zone, gens in network.generators.groupby(gen_zone_map):
            p_max_sorted_cs, sorted_inds = calc_p_max_sorted_cs(network, gens.index, snapshot)
            gen_weights = assign_merit_order_weights(p_max_sorted_cs, sorted_inds, mean=reference_generation_zones.loc[snapshot, zone], std=standard_deviation.loc[zone], method='positive') 

            isk_dict_snapshot[zone] = normalize_gsk_zone(gen_weights, network.generators.bus)

        all_zones_gsk = concat_isk(isk_dict_snapshot)
        isk_dict[snapshot] = all_zones_gsk.reindex(index=network.buses['zone_name'].unique(), columns=network.buses.index, fill_value=0)

    return isk_dict

def calc_pos_neg_gsk(
        network, 
        standard_deviation: int | float | dict | pd.Series
        ) -> tuple[dict[pd.Index, pd.DataFrame], dict[pd.Index, pd.DataFrame]]:

    zones = network.buses['zone_name'].unique()

    gen_zone_map = network.generators.bus.map(network.buses['zone_name'])
    reference_np_zones = network.generators_t.p.T.groupby(gen_zone_map).sum().T
    pos_isk = {}
    neg_isk = {}
    
    if isinstance(standard_deviation, (int | float)):
        standard_deviation = pd.Series(standard_deviation, index=zones)
    for snapshot in network.snapshots:
        pos_isk_dict = {}
        neg_isk_dict = {}
        for zone, gens in network.generators.groupby(gen_zone_map):
            p_max_sorted_cs, sorted_inds = calc_p_max_sorted_cs(network, gens.index, snapshot)
            gen_weights_pos = assign_merit_order_weights(p_max_sorted_cs, sorted_inds, mean=reference_np_zones.loc[snapshot, zone], std=standard_deviation[zone], method='positive') 
            gen_weights_neg = assign_merit_order_weights(p_max_sorted_cs, sorted_inds, mean=reference_np_zones.loc[snapshot, zone], std=standard_deviation[zone], method='negative') 

            pos_isk_dict[zone] = normalize_gsk_zone(gen_weights_pos, network.generators.bus)
            neg_isk_dict[zone] = normalize_gsk_zone(gen_weights_neg, network.generators.bus)

        pos_isk[snapshot] = concat_isk(pos_isk_dict).reindex(columns=network.buses.index, index=network.buses['zone_name'].unique(), fill_value=0)
        neg_isk[snapshot] = concat_isk(neg_isk_dict).reindex(columns=network.buses.index, index=network.buses['zone_name'].unique(), fill_value=0)
    return pos_isk, neg_isk


def calc_p_max_sorted_cs(network, generator_inds, snapshot):
    """Calculate the cumulative generation capacity of generators in the merit order.
    
    Args:
        network (pypsa.Network): _description_
        generator_inds (pd.Index): Generator indices to select. 
        snapshot: single snapshot to consider. 

    Returns:
        tuple: A tuple containing:
            - p_max_sorted_cs (np.array): Cumulative sum of maximum generation capacities sorted by marginal cost. The first entry is zero. 
            - sorted_inds (pd.Index): Indices of the generators sorted by marginal cost. 
    """
    mc = network.get_switchable_as_dense('Generator', 'marginal_cost').loc[snapshot, generator_inds]
    p_max = network.get_switchable_as_dense('Generator', 'p_max_pu').loc[snapshot, generator_inds] * network.generators.loc[generator_inds, 'p_nom']
    sorted_inds = mc.sort_values().index
    p_max_sorted_cs_ser = p_max.loc[sorted_inds].cumsum()
    # add a zero at the start to represent the cumulative sum before the first generator
    p_max_sorted_cs = np.concat(([0], p_max_sorted_cs_ser.values))
    return p_max_sorted_cs, sorted_inds



def assign_merit_order_weights(p_max_sorted_cs, sorted_inds, mean, std, method='neutral'):
    """Assign GSK weights based on the generators' position in the merit order curve. 
    More weight is assigned to generators close to the expected market clearing dispatch ('mean').


    Args:
        p_max_sorted_cs (np.array): Cumulative generator capacities sorted by marginal cost. Length G+1, where G is the number of generators. 1st entry is zero.
        sorted_inds (pd.Index): Generator indices sorted by marginal cost. Length G.
        mean (float): Expected market clearing dispatch value.
        std (float): Standard deviation of the dispatch.
        method (str, optional): Type of weighing function to apply.
        Options: 'neutral', 'positive', 'negative'. 
        'neutral' indicates multiplication with standard normal, 
        'positive' indicates multiplication with a positive half-normal distribution,
        'negative' indicates multiplication with half-normal distribution of negative values.
        Defaults to 'neutral'.

    Returns:
        _type_: _description_
    """
    if len(sorted_inds) == 1:
        return pd.Series([1], index=sorted_inds)
    elif method == 'neutral':
        generator_weight = norm.cdf(p_max_sorted_cs[1:], loc=mean, scale=std) - norm.cdf(p_max_sorted_cs[:-1], loc=mean, scale=std)
    elif method == 'positive':
        generator_weight = halfnorm.cdf(p_max_sorted_cs[1:], loc=mean, scale=std) - halfnorm.cdf(p_max_sorted_cs[:-1], loc=mean, scale=std)
    elif method == 'negative':
        generator_weight = halfnorm.cdf(-p_max_sorted_cs[1:], loc=-mean, scale=std) - halfnorm.cdf(-p_max_sorted_cs[:-1], loc=-mean, scale=std)
    weight = pd.Series(generator_weight, index=sorted_inds)
    if weight.sum() == 0:
        raise ValueError("All generators have zero weight.")
    return weight

def normalize_gsk_zone(generator_weights, gen_bus):
    """Normalize generator weights to create GSK for a specific zone."""
    gsk = generator_weights.groupby(gen_bus).sum()
    gsk = gsk / gsk.sum()  # Normalize to ensure they sum to 1
    return gsk

def concat_isk(isk_dict):
    return pd.DataFrame(isk_dict).T.fillna(0)


def gsk_bus_p(nodal_network: pypsa.Network) -> dict[pd.Index, pd.DataFrame]:
    """Calculate GSK based on bus power injections.
    Also add the power injection from links to the bus power injections.

    Returns:
        dict[pd.Index, pd.DataFrame]: GSKs for each snapshot.
    """
    gsk_dict = {}
    for snapshot in nodal_network.snapshots:
        link_p0 = nodal_network.links_t.p0.loc[snapshot]
        link_p1 = nodal_network.links_t.p1.loc[snapshot]
        link_p0_by_bus = link_p0.groupby(nodal_network.links.bus0).sum()
        link_p1_by_bus = link_p1.groupby(nodal_network.links.bus1).sum()
        bus_p = nodal_network.buses_t.p.loc[snapshot] - link_p1_by_bus.reindex(nodal_network.buses.index, fill_value=0) - link_p0_by_bus.reindex(nodal_network.buses.index, fill_value=0) 
        zone_names = nodal_network.buses['zone_name']
        gsk_matrix = pd.DataFrame(0.0, index=zone_names.unique(), columns=nodal_network.buses.index)

        for zone in zone_names.unique():
            buses_in_zone = zone_names[zone_names == zone].index
            total_zone_p = bus_p[buses_in_zone].sum()

            if abs(total_zone_p) > 1e-6:  # Avoid division by zero
                for bus in buses_in_zone:
                    gsk_matrix.at[zone, bus] = bus_p[bus] / total_zone_p
            else:
                # Distribute GSK evenly if total power is zero
                gsk_matrix.loc[zone, buses_in_zone] = 1.0 / len(buses_in_zone)

        # Normalize rows to ensure they sum to 1
        gsk_matrix = gsk_matrix.apply(lambda row: row / row.sum() if row.sum() > 1e-6 else row, axis=1)

        # Re-apply equal distribution for zero-sum rows if normalization failed
        for zone in zone_names.unique():
            if gsk_matrix.loc[zone].sum() < 1e-6:
                buses_in_zone = zone_names[zone_names == zone].index
                gsk_matrix.loc[zone, buses_in_zone] = 1.0 / len(buses_in_zone)

        gsk_matrix.index.name = None  # Remove index name
        gsk_dict[snapshot] = gsk_matrix

    return gsk_dict
    