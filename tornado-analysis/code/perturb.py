"""
Applies a single +/- perturbation to a copy of a PyPSA network, for both
static attributes (network.generators.marginal_cost, ...) and time-varying
attributes stored in the *_t dataframes (network.loads_t.p_set, ...).

Supports two types of perturbations:
- Percentage-based: variation (e.g. 0.20 for ±20%)
- Discrete/absolute: discrete_change (e.g. 100 for ±100 units)
  Can also specify discrete_change_low and/or discrete_change_high for asymmetric changes
  When multiple elements match the selector, discrete changes are distributed proportionally
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
        When multiple elements match, discrete_change is distributed proportionally.

    - Discrete/absolute asymmetric (using 'discrete_change_low' and/or 'discrete_change_high'):
        direction: 'low' -> value - discrete_change_low (if specified)
                   'high' -> value + discrete_change_high (if specified)
        If only one is specified, only that direction is perturbed.
        When multiple elements match, changes are distributed proportionally.

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
        distribute_proportionally = False
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
        distribute_proportionally = True
    elif "discrete_change" in param:
        # Discrete/absolute symmetric perturbation
        adjustment = -param["discrete_change"] if direction == "low" else param["discrete_change"]
        use_factor = False
        distribute_proportionally = True
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
            if distribute_proportionally and len(cols) > 1:
                # For discrete changes across multiple assets, distribute proportionally
                # Calculate the proportional share for each asset based on current values
                current_values = ts.loc[:, cols].sum(axis=0)  # Sum across snapshots for each asset
                total_value = current_values.sum()
                
                if total_value > 0:
                    # Distribute the total adjustment proportionally
                    for col in cols:
                        proportion = current_values[col] / total_value
                        ts.loc[:, col] = ts.loc[:, col] + (adjustment * proportion)
                else:
                    # If all values are zero, distribute equally
                    equal_share = adjustment / len(cols)
                    ts.loc[:, cols] = ts.loc[:, cols] + equal_share
            else:
                # Single element or percentage-based: apply adjustment directly
                ts.loc[:, cols] = ts.loc[:, cols] + adjustment

    elif attribute in static_df.columns:
        mask = _resolve_mask(static_df.index, param["selector"], static_df)
        selected_indices = static_df.index[mask.values]
        
        if use_factor:
            static_df.loc[mask, attribute] = static_df.loc[mask, attribute] * adjustment
        else:
            if distribute_proportionally and len(selected_indices) > 1:
                # For discrete changes across multiple assets, distribute proportionally
                current_values = static_df.loc[selected_indices, attribute]
                total_value = current_values.sum()
                print(f"current values: {current_values}")
                
                if total_value > 0:
                    # Distribute the total adjustment proportionally
                    for idx in selected_indices:
                        proportion = static_df.loc[idx, attribute] / total_value
                        print(f"idx x proportion: {idx} x {proportion}")
                        static_df.loc[idx, attribute] = static_df.loc[idx, attribute] + (adjustment * proportion)
                else:
                    # If all values are zero, distribute equally
                    equal_share = adjustment / len(selected_indices)
                    static_df.loc[selected_indices, attribute] = static_df.loc[selected_indices, attribute] + equal_share
            else:
                # Single element or percentage-based: apply adjustment directly
                static_df.loc[mask, attribute] = static_df.loc[mask, attribute] + adjustment

    else:
        raise ValueError(
            f"Attribute '{attribute}' not found as a static column on "
            f"n.{component} nor as a time series on n.{component}_t"
        )

    return n
