"""
Configuration for the tornado sensitivity analysis.

Define every parameter you want to test in PARAMETERS. Each entry:

- name:      human-readable label, shown on the tornado chart
- component: PyPSA component to modify, e.g. 'generators', 'loads',
             'lines', 'storage_units', 'links'
- attribute: the attribute/column to perturb. Works for both static
             attributes (e.g. 'marginal_cost', 'p_nom', 'capital_cost')
             and time-varying attributes stored in <component>_t
             (e.g. 'p_set', 'p_max_pu')
- selector:  (optional) which assets of that component are affected.
               "all"                    -> every asset (default)
               ["Gen1", "Gen2"]         -> explicit list of names
               lambda df: df["carrier"] == "gas"   -> boolean mask callable
- countries: (optional) list of country codes, e.g. ["DE", "FR", "ES"].
             If given, this ONE entry is expanded by run_tornado.py into
             one independent parameter PER country (e.g. "Gas price - DE",
             "Gas price - FR", "Gas price - ES"), each masked to that
             country's buses and combined with `selector` via AND.
             Country membership is derived from each asset's bus using
             COUNTRY_BUS_PREFIX_LENGTH below (or a 'country' column on
             network.buses, if present -- see welfare.bus_country_map()).
             Omit "countries" for a single system-wide run.
- variation: relative variation to apply, e.g. 0.20 for +/-20%
"""

PARAMETERS = [
    {
        "name": "Renewables capacity",
        "component": "generators",
        "attribute": "p_nom",
        "selector": lambda df: df["carrier"].isin(["onwind", "solar", "solar-hsat"]),
        "countries": ['BE', 'DE', 'DK', 'FR', 'GB', 'IE', 'LU', 'NL'],  # run independently per country
        "variation": 0.20,
    },

    {
        "name": "Storage capacity",
        "component": "storage_units",
        "attribute": "p_nom",
        "selector": "all",
        "countries": ['BE', 'DE', 'DK', 'FR', 'GB', 'IE', 'LU', 'NL'],  # run independently per country
        "variation": 0.20,
    },

    {
        "name": "Gas price (marginal cost of gas generators)",
        "component": "generators",
        "attribute": "marginal_cost",
        "selector": lambda df: df["carrier"] == "CCGT",
        "variation": 0.2,
    },

    {
        "name": "Renewable production",
        "component": "generators",
        "attribute": "p_max_pu",
        "selector": lambda df: df["carrier"].isin(["onwind", "solar", "solar-hsat"]),
        "variation": 0.20,
    },

    {
        "name": "Demand level",
        "component": "loads",
        "attribute": "p_set",
        "selector": "all",
        "countries": ['BE', 'DE', 'DK', 'FR', 'GB', 'IE', 'LU', 'NL'],
        "variation": 0.10,
    },
    # {
    #     "name": "Wind capacity (system-wide)",
    #     "component": "generators",
    #     "attribute": "p_nom",
    #     "selector": lambda df: df["carrier"] == "wind",
    #     # no "countries" -> single system-wide run, not expanded
    #     "variation": 0.20,
    # },
    # ... add as many parameters as you need
]

# Path to your baseline PyPSA network (.nc, .h5, or a folder of CSVs
# depending on how you normally load it)

#BASELINE_NETWORK_PATH = "/Users/ng-work/Models/pypsa-fbmc/tornado-analysis/inputs/validation/three-country-fbmc.nc"
BASELINE_NETWORK_PATH = "/Users/ng-work/Models/pypsa-fbmc/tornado-analysis/inputs/test/base_s_25_elec_Ep100.nc"


#RESULTS_DIR = "/Users/ng-work/Models/pypsa-fbmc/tornado-analysis/results/validation"
RESULTS_DIR = "/Users/ng-work/Models/pypsa-fbmc/tornado-analysis/results/test_param"

# How to map buses to countries when network.buses has no 'country' column,
# e.g. bus "DE1" -> "DE" with prefix_length=2. Set to None if your network
# already carries a 'country' column on network.buses.
COUNTRY_BUS_PREFIX_LENGTH = 2

# Value of lost load (EUR/MWh), used to compute consumer surplus since
# demand is normally modelled as inelastic (fixed p_set) in PyPSA. Adjust
# to match your model's assumptions, or replace consumer_surplus_by_country()
# in welfare.py if you have elastic demand / demand curves.
VOLL = 3000

#baseline preprocessing
FREEZE_EXPANSION_FLAG = True
BZ_RENAME_FLAG = True
BZ_RENAME_FILE = "/Users/ng-work/Models/pypsa-fbmc/tornado-analysis/inputs/test/bz_rename.csv"

