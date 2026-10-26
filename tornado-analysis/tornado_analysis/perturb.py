"""
Apply one perturbation to a copy of a PyPSA network.

A case spec (see config.expand_cases) states:
  target    component / attribute / kind (static | timeseries)
  selector  names, carrier, countries, query -- combined with AND
  mode      relative: value * (1 +/- magnitude)
            absolute: value +/- magnitude, distributed over the selected
                      assets proportionally to their current value
  direction up (+) or down (-)
"""

import pandas as pd


def _country_mask(df, bus_country, countries):
    if "bus" in df.columns:
        return df["bus"].map(bus_country).isin(countries)
    if "bus0" in df.columns and "bus1" in df.columns:
        # lines/links: an asset is "in" a country if either end is
        return df["bus0"].map(bus_country).isin(countries) | df["bus1"].map(bus_country).isin(countries)
    raise ValueError("Cannot determine country: component has neither 'bus' nor 'bus0'/'bus1'.")


def select_assets(static_df, selector, bus_country=None):
    """Return the index of assets matching every given selector key."""
    mask = pd.Series(True, index=static_df.index)
    selector = selector or {}
    if selector.get("names"):
        mask &= static_df.index.isin(selector["names"])
    if selector.get("carrier"):
        carriers = selector["carrier"]
        carriers = [carriers] if isinstance(carriers, str) else carriers
        if "carrier" not in static_df.columns:
            raise ValueError("selector.carrier used but component has no 'carrier' column")
        mask &= static_df["carrier"].isin(carriers)
    if selector.get("countries"):
        if bus_country is None:
            raise ValueError("selector.countries needs a bus->country map")
        mask &= _country_mask(static_df, bus_country, selector["countries"])
    if selector.get("query"):
        mask &= static_df.index.isin(static_df.query(selector["query"]).index)
    return static_df.index[mask.values]


def apply_perturbation(network, case, bus_country=None):
    """Return a COPY of `network` with the case applied."""
    n = network.copy()
    target = case["target"]
    component, attribute, kind = target["component"], target["attribute"], target["kind"]
    sign = 1 if case["direction"] == "up" else -1
    delta = sign * case["magnitude"]
    mode = case["mode"]

    static_df = getattr(n, component)
    assets = select_assets(static_df, case.get("selector"), bus_country)
    if len(assets) == 0:
        raise ValueError(f"Perturbation '{case['parameter']}' selected no {component}")

    if kind == "timeseries":
        container = getattr(n, f"{component}_t")
        if attribute not in container or container[attribute].empty:
            raise ValueError(f"n.{component}_t has no time series '{attribute}'")
        ts = container[attribute]
        cols = [a for a in assets if a in ts.columns]
        if not cols:
            raise ValueError(f"None of the selected {component} has a time series '{attribute}'")
        if mode == "relative":
            ts.loc[:, cols] = ts.loc[:, cols] * (1 + delta)
        else:
            weights = ts[cols].sum(axis=0)
            total = weights.sum()
            share = weights / total if total > 0 else pd.Series(1 / len(cols), index=cols)
            ts.loc[:, cols] = ts.loc[:, cols] + share * delta
    else:
        if attribute not in static_df.columns:
            raise ValueError(f"n.{component} has no static column '{attribute}'")
        values = static_df.loc[assets, attribute].astype(float)
        if mode == "relative":
            static_df.loc[assets, attribute] = values * (1 + delta)
        else:
            total = values.sum()
            share = values / total if total > 0 else pd.Series(1 / len(assets), index=assets)
            static_df.loc[assets, attribute] = values + share * delta
    return n
