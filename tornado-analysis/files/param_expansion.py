"""
Expands PARAMETERS entries that specify `countries` into one independent
parameter per country, so each is perturbed and run as a separate case.

e.g. a config entry with "countries": ["DE", "FR", "ES"] becomes three
parameters named "<name> - DE", "<name> - FR", "<name> - ES", each masked
to that country's buses (combined with any existing selector via AND).
"""

import pandas as pd


def _country_mask(df, bus_country, country):
    if "bus" in df.columns:
        return df["bus"].map(bus_country) == country
    if "bus0" in df.columns and "bus1" in df.columns:
        # for lines/links: asset counts as "in" a country if either end is
        return (df["bus0"].map(bus_country) == country) | (df["bus1"].map(bus_country) == country)
    raise ValueError(
        "Cannot determine country membership: component has neither a "
        "'bus' column nor 'bus0'/'bus1' columns."
    )


def expand_parameters(parameters, bus_country):
    expanded = []
    for param in parameters:
        countries = param.get("countries")
        if not countries:
            expanded.append(param)
            continue

        base_selector = param.get("selector", "all")

        for country in countries:
            def make_selector(base_selector=base_selector, country=country):
                def selector(df):
                    country_mask = _country_mask(df, bus_country, country)
                    if base_selector == "all":
                        return country_mask
                    if callable(base_selector):
                        return base_selector(df) & country_mask
                    return pd.Series(df.index.isin(base_selector), index=df.index) & country_mask
                return selector

            new_param = {k: v for k, v in param.items() if k != "countries"}
            new_param["selector"] = make_selector()
            new_param["name"] = f"{param['name']} - {country}"
            new_param["country"] = country
            expanded.append(new_param)

    return expanded
