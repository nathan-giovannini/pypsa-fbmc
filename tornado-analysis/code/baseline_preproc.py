import pandas as pd


def freeze_expansion(network):
    """
    Replace nominal capacities by their optimized values and
    disable further expansion.

    Parameters
    ----------
    network : pypsa.Network
    """

    for comp in network.components.values():
        df = getattr(network, comp.list_name, None)

        if df is None or df.empty:
            continue

        cols = df.columns

        # p_nom -> p_nom_opt
        if "p_nom" in cols and "p_nom_opt" in cols:
            df["p_nom"] = df["p_nom_opt"]
            if "p_nom_extendable" in cols:
                df["p_nom_extendable"] = False

        # s_nom -> s_nom_opt
        if "s_nom" in cols and "s_nom_opt" in cols:
            df["s_nom"] = df["s_nom_opt"]
            if "s_nom_extendable" in cols:
                df["s_nom_extendable"] = False

        # e_nom -> e_nom_opt
        if "e_nom" in cols and "e_nom_opt" in cols:
            df["e_nom"] = df["e_nom_opt"]
            if "e_nom_extendable" in cols:
                df["e_nom_extendable"] = False

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