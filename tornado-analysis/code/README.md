# Tornado sensitivity analysis for a PyPSA-based market model

A config-driven framework: define the parameters you want to test once
(optionally per-country), and the driver perturbs each one by ±20% (all
others held at baseline), runs the model, and logs both scalar output
metrics and the resulting welfare distribution by country.

## Files

- `config.py` — the file you edit most: list of parameters (component,
  attribute, which assets, variation size, optional `countries`), plus
  `COUNTRY_BUS_PREFIX_LENGTH` and `VOLL` settings.
- `perturb.py` — multiplies a chosen attribute by `(1 ± variation)` on a
  *copy* of the network. Handles both static attributes
  (`network.generators.marginal_cost`) and time series
  (`network.loads_t.p_set`).
- `param_expansion.py` — expands any parameter with a `"countries": [...]`
  entry into one independent parameter per country (e.g. `"Gas price - DE"`,
  `"Gas price - FR"`), masked to that country's buses.
- `welfare.py` — computes producer surplus, consumer surplus (needs a VOLL
  assumption, since PyPSA demand is normally inelastic), and congestion
  rent (split 50/50 across interconnected countries), aggregated by
  country from a solved network. Also computes `distribution_shift()`, a
  scalar summary of how much welfare moved between countries vs baseline.
- `model_interface.py` — **the file you adapt to your actual market
  model**. Must return a dict of metrics, optionally including
  `"welfare_by_country"` (a `{country: welfare}` dict). A ready example is
  included for `network.optimize()`.
- `run_tornado.py` — runs baseline + every low/high perturbation (after
  expanding country-scoped parameters), writing:
  - `results/tornado_results.csv` — one row per run: scalar metrics plus
    `welfare_distribution_shift` (use this as the tornado chart metric)
  - `results/welfare_by_country.csv` — one row per (run, country), with
    the full disaggregation kept as separate columns
    (`producer_surplus`, `storage_surplus`, `consumer_surplus`,
    `line_congestion_rent`, `link_congestion_rent`, `total`), plus
    `welfare_share` and `delta_share_vs_baseline` computed from `total`.
    The disaggregation is there for later analysis (e.g. "did this
    parameter mostly hit consumers or producers in country X?"), not just
    the headline total.
- `analyze_tornado.py` — builds the tornado chart for a chosen metric
  (defaults to `welfare_distribution_shift`).
- `analyze_welfare_distribution.py` — for one specific parameter/direction,
  plots baseline vs perturbed welfare shares by country, so you can see
  *which* countries gain or lose.

## Usage

1. Edit `config.py`: set `BASELINE_NETWORK_PATH`, list your `PARAMETERS`
   (add `"countries": [...]` to any you want run independently per
   country), and set `COUNTRY_BUS_PREFIX_LENGTH` / `VOLL`.
2. Edit `model_interface.py` so `run_model(network)` calls your actual
   market model and returns the metrics you want (welfare_by_country is
   computed for you via `welfare.py` if you're using PyPSA's optimizer).
3. Run:
   ```bash
   python run_tornado.py
   python analyze_tornado.py --metric welfare_distribution_shift
   python analyze_welfare_distribution.py --parameter "Gas price - DE" --direction high
   ```

## Notes / assumptions worth checking

- **Country mapping**: by default, country = first `COUNTRY_BUS_PREFIX_LENGTH`
  characters of the bus name (`"DE1"` → `"DE"`). If your network has an
  explicit `country` column on `network.buses`, that's used automatically
  instead (see `welfare.bus_country_map()`).
- **Consumer surplus needs VOLL**: since demand is typically fixed
  (inelastic) in PyPSA, consumer surplus is computed as
  `(VOLL - price) * demand`. The default (3000 EUR/MWh) is a common
  placeholder — replace it with whatever assumption your study uses, or
  rework `consumer_surplus_by_country()` if you have real demand curves.
- **Congestion rent allocation**: interconnector rent is split 50/50
  between the two countries a line connects. Change the split logic in
  `congestion_rent_by_country()` if your analysis needs a different
  convention (e.g. attribute fully to the importer).
- **storage_units / links**: included. Storage producer surplus applies
  `marginal_cost` only to the discharging (positive dispatch) leg; link
  rent accounts for efficiency losses via PyPSA's `p0`/`p1` convention and
  nets out any link `marginal_cost`. Both are split the same 50/50 way as
  line congestion rent when they connect two countries.
- **`welfare_distribution_shift`** is the sum of absolute changes in each
  country's *share* of total system welfare vs baseline — it isolates
  redistribution from overall welfare growth/shrinkage, so it's a good
  tornado-chart metric for "which parameters reshuffle welfare across
  borders the most."
- **Failed runs** are caught per-run and logged with
  `status="failed: ..."` rather than crashing the whole sweep.
- **Runtime**: if each solve is expensive, consider parallelizing the
  loop in `run_tornado.py` (e.g. `concurrent.futures.ProcessPoolExecutor`)
  once a single run is confirmed to work correctly.