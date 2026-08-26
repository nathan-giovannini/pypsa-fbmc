import pandas as pd


def freeze_expansion(network):
    """
    Replace nominal capacities by their optimized values, save the original capacities as _orig and
    disable further expansion.

    Parameters
    ----------
    network : pypsa.Network
    """

    for comp in network.components.values():
        df = getattr(network, comp.list_name, None)
        if df is None or df.empty:
            continue

        if {"p_nom", "p_nom_opt", "p_nom_extendable"}.issubset(df.columns):
            mask = df["p_nom_extendable"]
            df.loc[mask, "p_nom_orig"] = df.loc[mask, "p_nom"]
            df.loc[mask, "p_nom"] = df.loc[mask, "p_nom_opt"]
            df.loc[mask, "p_nom_extendable"] = False

        if {"s_nom", "s_nom_opt", "s_nom_extendable"}.issubset(df.columns):
            mask = df["s_nom_extendable"]
            df.loc[mask, "s_nom_orig"] = df.loc[mask, "s_nom"]
            df.loc[mask, "s_nom"] = df.loc[mask, "s_nom_opt"]
            df.loc[mask, "s_nom_extendable"] = False

        if {"e_nom", "e_nom_opt", "e_nom_extendable"}.issubset(df.columns):
            mask = df["e_nom_extendable"]
            df.loc[mask, "e_nom_orig"] = df.loc[mask, "e_nom"]
            df.loc[mask, "e_nom"] = df.loc[mask, "e_nom_opt"]
            df.loc[mask, "e_nom_extendable"] = False

    return network

def bidding_zones_rename(network, csv_path):
    """
    Add a new column zone_name with a custom zone that differs from the countru name when a country has more than one bidding zone

    Parameters
    ----------
    network : pypsa.Network
    """
    # network.buses["zone_name"] = network.buses.country
    # network.buses.loc["DK1 0", "zone_name"] = "DK-10"
    # network.buses.loc["DK1 3", "zone_name"] = "DK-13"
    # network.buses.loc["DK3 0", "zone_name"] = "DK-30"
    # network.buses.loc["GB2 0", "zone_name"] = "NIR"
    # network.remove("Bus", "DK1 3")


    mapping = pd.read_csv(csv_path)

    # Initialize zone_name from country
    network.buses["zone_name"] = network.buses.country

    # Assign zone names
    for _, row in mapping.iterrows():
        bus = row["name_bus"]
        zone = row["rename_zone"]

        if bus in network.buses.index and pd.notna(zone):
            network.buses.loc[bus, "zone_name"] = zone
            print(f"Replacing zone_name of {bus} with {zone}")

    # Remove buses
    for bus in mapping["remove_bus"].dropna():
        if bus in network.buses.index:
            network.remove("Bus", bus)
            print(f"removed bus {bus}")

    return network