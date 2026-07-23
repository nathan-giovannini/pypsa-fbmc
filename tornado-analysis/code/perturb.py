"""
Applies a single +/- perturbation to a copy of a PyPSA network, for both
static attributes (network.generators.marginal_cost, ...) and time-varying
attributes stored in the *_t dataframes (network.loads_t.p_set, ...).

Supports two types of perturbations:
- Percentage-based: variation (e.g. 0.20 for ±20%)
- Discrete/absolute: discrete_change (e.g. 100 for ±100 units)
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

    Supports two perturbation modes:
    - Percentage-based (using 'variation' key):
        direction: 'low' -> value * (1 - variation)
                   'high' -> value * (1 + variation)
    
    - Discrete/absolute (using 'discrete_change' key):
        direction: 'low' -> value - discrete_change
                   'high' -> value + discrete_change

    Either 'variation' OR 'discrete_change' should be specified, but not both.
    """
    n = copy.deepcopy(network)
    component = param["component"]
    attribute = param["attribute"]

    # Determine perturbation type and calculate the adjustment
    if "variation" in param:
        # Percentage-based perturbation
        factor = (1 - param["variation"]) if direction == "low" else (1 + param["variation"])
        use_factor = True
        adjustment = factor
    elif "discrete_change" in param:
        # Discrete/absolute perturbation
        adjustment = -param["discrete_change"] if direction == "low" else param["discrete_change"]
        use_factor = False
    else:
        raise ValueError(
            "Parameter must specify either 'variation' (for percentage-based) "
            "or 'discrete_change' (for absolute value changes)"
        )

    static_df = getattr(n, component)
    time_container = getattr(n, f"{component}_t", None)

    if time_container is not None and attribute in time_container:
        ts = time_container[attribute]  # DataFrame: snapshots x assets
        mask = _resolve_mask(ts.columns, param["selector"], static_df)
        cols = ts.columns[mask.values]
        if use_factor:
            ts.loc[:, cols] = ts.loc[:, cols] * adjustment
        else:
            ts.loc[:, cols] = ts.loc[:, cols] + adjustment

    elif attribute in static_df.columns:
        mask = _resolve_mask(static_df.index, param["selector"], static_df)
        if use_factor:
            static_df.loc[mask, attribute] = static_df.loc[mask, attribute] * adjustment
        else:
            static_df.loc[mask, attribute] = static_df.loc[mask, attribute] + adjustment

    else:
        raise ValueError(
            f"Attribute '{attribute}' not found as a static column on "
            f"n.{component} nor as a time series on n.{component}_t"
        )

    return n
