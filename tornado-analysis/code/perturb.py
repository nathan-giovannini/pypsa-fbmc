"""
Applies a single +/- perturbation to a copy of a PyPSA network, for both
static attributes (network.generators.marginal_cost, ...) and time-varying
attributes stored in the *_t dataframes (network.loads_t.p_set, ...).

Supports two types of perturbations:
- Percentage-based: variation (e.g. 0.20 for ±20%)
- Discrete/absolute: discrete_change (e.g. 100 for ±100 units)
  Can also specify discrete_change_low and/or discrete_change_high for asymmetric changes
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

    Supports three perturbation modes:
    - Percentage-based (using 'variation' key):
        direction: 'low' -> value * (1 - variation)
                   'high' -> value * (1 + variation)
    
    - Discrete/absolute symmetric (using 'discrete_change' key):
        direction: 'low' -> value - discrete_change
                   'high' -> value + discrete_change

    - Discrete/absolute asymmetric (using 'discrete_change_low' and/or 'discrete_change_high'):
        direction: 'low' -> value - discrete_change_low (if specified)
                   'high' -> value + discrete_change_high (if specified)
        If only one is specified, only that direction is perturbed.

    Either 'variation' OR one of the discrete_change options should be specified, but not both.
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
    elif "discrete_change_low" in param or "discrete_change_high" in param:
        # Discrete/absolute asymmetric perturbation
        if direction == "low":
            if "discrete_change_low" not in param:
                # If only high is defined, skip low direction
                return n
            adjustment = -param["discrete_change_low"]
        else:  # direction == "high"
            if "discrete_change_high" not in param:
                # If only low is defined, skip high direction
                return n
            adjustment = param["discrete_change_high"]
        use_factor = False
    elif "discrete_change" in param:
        # Discrete/absolute symmetric perturbation
        adjustment = -param["discrete_change"] if direction == "low" else param["discrete_change"]
        use_factor = False
    else:
        raise ValueError(
            "Parameter must specify either 'variation' (for percentage-based), "
            "'discrete_change' (for symmetric absolute changes), "
            "or 'discrete_change_low'/'discrete_change_high' (for asymmetric changes)"
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
