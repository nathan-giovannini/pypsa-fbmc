"""
Computes market-welfare metrics by country from a solved PyPSA network.

Welfare is decomposed as:
  - producer surplus per generator: (price_at_bus - marginal_cost) * dispatch
  - consumer surplus per load: (VOLL - price_at_bus) * demand
  - congestion rent per line: (price_bus1 - price_bus0) * flow, split
    50/50 between the two connected countries

Consumer surplus needs a value-of-lost-load (VOLL) assumption because
demand in PyPSA is usually modelled as fixed/inelastic (p_set), so there's
no explicit willingness-to-pay curve to integrate. If your model has
elastic demand or bids, replace consumer_surplus_by_country() accordingly.

storage_units and links are not included by default (extend
producer_surplus_by_country / add equivalents if your network uses them
materially).

All of this requires nodal marginal prices (network.buses_t.marginal_price),
so the network must already be solved before calling these functions.
"""

import pandas as pd

DEFAULT_VOLL = 3000  # EUR/MWh -- adjust to match your model's assumptions


def bus_country_map(network, prefix_length=None, country_column=None):
    """
    Map every bus to a country code.

    Priority:
    1. `country_column`, if given and present on network.buses
    2. a 'country' column on network.buses, if present
    3. the first `prefix_length` characters of the bus name
       (e.g. 'DE1' -> 'DE' with prefix_length=2)
    """
    buses = network.buses
    col = country_column or ("country" if "country" in buses.columns else None)
    if col is not None:
        return buses[col]

    if prefix_length is None:
        raise ValueError(
            "No country column found on network.buses; pass prefix_length "
            "to derive country codes from bus names (e.g. 'DE1' -> 'DE')."
        )
    return buses.index.to_series().str[:prefix_length]


def producer_surplus_by_country(network, bus_country):
    gens = network.generators
    if gens.empty:
        return pd.Series(dtype=float)

    country = gens["bus"].map(bus_country)
    dispatch = network.generators_t.p  # snapshots x generators
    price_at_bus = network.buses_t.marginal_price[gens["bus"]]
    price_at_bus.columns = gens.index

    revenue = (price_at_bus * dispatch).sum()
    cost = (gens["marginal_cost"].reindex(dispatch.columns).values * dispatch).sum()
    surplus = revenue - cost
    return surplus.groupby(country).sum()


def consumer_surplus_by_country(network, bus_country, voll=DEFAULT_VOLL):
    loads = network.loads
    if loads.empty:
        return pd.Series(dtype=float)

    country = loads["bus"].map(bus_country)
    demand = network.loads_t.p_set
    price_at_bus = network.buses_t.marginal_price[loads["bus"]]
    price_at_bus.columns = loads.index

    surplus = ((voll - price_at_bus) * demand).sum()
    return surplus.groupby(country).sum()


def congestion_rent_by_country(network, bus_country):
    """
    Rent on transmission lines, split 50/50 between the two connected
    countries. Adjust this allocation rule if your analysis needs a
    different convention (e.g. attribute fully to the importing country).
    """
    lines = network.lines
    if lines.empty:
        return pd.Series(dtype=float)

    flow = network.lines_t.p0  # snapshots x lines, flow leaving bus0
    price0 = network.buses_t.marginal_price[lines["bus0"]]
    price1 = network.buses_t.marginal_price[lines["bus1"]]
    price0.columns = lines.index
    price1.columns = lines.index

    rent = ((price1 - price0) * flow).sum()  # per line, summed over snapshots

    country0 = lines["bus0"].map(bus_country)
    country1 = lines["bus1"].map(bus_country)

    half = rent / 2
    rent_by_country = pd.concat([
        half.groupby(country0).sum(),
        half.groupby(country1).sum(),
    ]).groupby(level=0).sum()

    return rent_by_country


def welfare_by_country(network, bus_country=None, prefix_length=None, voll=DEFAULT_VOLL):
    """
    Total welfare by country = producer surplus + consumer surplus
    + congestion rent. Returns a pandas Series indexed by country code.
    """
    if bus_country is None:
        bus_country = bus_country_map(network, prefix_length=prefix_length)

    ps = producer_surplus_by_country(network, bus_country)
    cs = consumer_surplus_by_country(network, bus_country, voll=voll)
    cr = congestion_rent_by_country(network, bus_country)

    total = pd.concat([ps, cs, cr]).groupby(level=0).sum()
    return total.sort_index()


def welfare_shares(welfare_series):
    total = welfare_series.sum()
    if total == 0:
        return welfare_series * 0
    return welfare_series / total


def distribution_shift(baseline_welfare, perturbed_welfare):
    """
    Sum of absolute changes in each country's share of total welfare,
    vs baseline. 0 = no redistribution; larger = more welfare shifted
    between countries, independent of whether total welfare grew or shrank.
    """
    base_shares = welfare_shares(baseline_welfare)
    pert_shares = welfare_shares(perturbed_welfare)

    all_countries = base_shares.index.union(pert_shares.index)
    base_shares = base_shares.reindex(all_countries, fill_value=0)
    pert_shares = pert_shares.reindex(all_countries, fill_value=0)

    return (pert_shares - base_shares).abs().sum()
