"""
Applies a single +/- perturbation to a copy of a PyPSA network, for both
static attributes (network.generators.marginal_cost, ...) and time-varying
attributes stored in the *_t dataframes (network.loads_t.p_set, ...).
"""

import copy
import pandas as pd
import pypsa


def _resolve_mask(index, selector, static_df):
    """Return a boolean Series aligned to `index` marking selected assets."""
    if selector == "all":
        return pd.Series(True, index=index)
    if callable(selector):
        mask = selector(static_df)
        return mask.reindex(index, fill_value=False)
    # assume list/iterable of names
    return pd.Series(index.isin(selector), index=index)


def apply_perturbation(network: pypsa.Network, param: dict, direction: str) -> pypsa.Network:
    """
    Return a COPY of `network` with a single parameter perturbed.

    direction: 'low' -> value * (1 - variation)
               'high' -> value * (1 + variation)
    """
    n = copy.deepcopy(network)
    component = param["component"]
    attribute = param["attribute"]
    factor = (1 - param["variation"]) if direction == "low" else (1 + param["variation"])

    static_df = getattr(n, component)
    time_container = getattr(n, f"{component}_t", None)

    if attribute in static_df.columns:
        mask = _resolve_mask(static_df.index, param["selector"], static_df)
        static_df.loc[mask, attribute] = static_df.loc[mask, attribute] * factor

    elif time_container is not None and attribute in time_container:
        ts = time_container[attribute]  # DataFrame: snapshots x assets
        mask = _resolve_mask(ts.columns, param["selector"], static_df)
        cols = ts.columns[mask.values]
        ts.loc[:, cols] = ts.loc[:, cols] * factor

    else:
        raise ValueError(
            f"Attribute '{attribute}' not found as a static column on "
            f"n.{component} nor as a time series on n.{component}_t"
        )

    return n
