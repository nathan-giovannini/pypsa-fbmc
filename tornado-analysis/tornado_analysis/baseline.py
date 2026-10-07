"""Baseline preprocessing: done once, on the baseline network only."""

import pandas as pd
import pypsa

from .welfare import bus_country_map


def bidding_zones_rename(network, csv_path, prefix_length=None):
    """Add `zone_name` to buses (country by default, overridden by the CSV) and drop listed buses."""
    mapping = pd.read_csv(csv_path)
    network.buses["zone_name"] = bus_country_map(network, prefix_length=prefix_length)
    for _, row in mapping.iterrows():
        if row["name_bus"] in network.buses.index and pd.notna(row["rename_zone"]):
            network.buses.loc[row["name_bus"], "zone_name"] = row["rename_zone"]
    for bus in mapping["remove_bus"].dropna():
        if bus in network.buses.index:
            network.remove("Bus", bus)
    return network


def shedding_buses(network, selection, prefix_length=None):
    """Buses selected by `names` and/or `countries` (AND). Empty selection = all buses."""
    selection = selection or {}
    mask = pd.Series(True, index=network.buses.index)
    if selection.get("names"):
        mask &= network.buses.index.isin(selection["names"])
    if selection.get("countries"):
        country = bus_country_map(network, prefix_length=prefix_length)
        mask &= country.isin(selection["countries"])
    buses = network.buses.index[mask.values]
    if len(buses) == 0:
        raise ValueError("load_shedding.buses selected no bus")
    return buses


def prepare_baseline(network, baseline_cfg, prefix_length=None):
    """
    1. optional bidding-zone renaming
    2. freeze capacity expansion with PyPSA's n.optimize.fix_optimal_capacities()
    3. optional load shedding via n.optimize.add_load_shedding() on selected buses
    """
    baseline_cfg = baseline_cfg or {}

    bz = baseline_cfg.get("bz_rename") or {}
    if bz.get("enabled"):
        network = bidding_zones_rename(network, bz["file"], prefix_length)

    if baseline_cfg.get("fix_optimal_capacities", True):
        network.optimize.fix_optimal_capacities()

    ls = baseline_cfg.get("load_shedding") or {}
    if ls.get("enabled"):
        buses = shedding_buses(network, ls.get("buses"), prefix_length)
        network.optimize.add_load_shedding(
            buses=buses,
            marginal_cost=ls["cost"],
            sign=ls.get("sign", 1),
            **({"p_nom": ls["p_nom"]} if "p_nom" in ls else {}),
        )
    return network
