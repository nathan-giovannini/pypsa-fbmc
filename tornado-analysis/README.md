# Tornado sensitivity analysis (Snakemake)

Standalone workflow: perturb parameters of a PyPSA network one at a time,
solve with standard PyPSA (`n.optimize`), and compare scalar metrics and
the welfare distribution across countries. All user input lives in
`config.yaml`.

## Run

From this folder:

```bash
snakemake -j 4                  # full workflow
snakemake -j 4 -n               # dry run: see what would be (re)computed
pytest tests                    # unit tests
```

Inputs live in `inputs/<study>/`, outputs in `results/<study>/`. Each case
is a separate job, so adding or editing a perturbation in `config.yaml`
only reruns the new/changed cases, then re-aggregates and re-plots.

## Workflow

1. `prepare_baseline` – once: `n.optimize.fix_optimal_capacities()` (the
   network must contain `*_opt` values) and `n.optimize.add_load_shedding()`
   on the configured buses (one global cost). Load-shedding generators are
   named `"<bus> load shedding"`.
2. `run_baseline_case` / `run_case` – one solve per case, writing
   `cases/<case>/metrics.json` and `welfare.csv`.
3. `aggregate` – `tornado_results.csv`, `welfare_by_country.csv`.
4. `plot_tornado`, `plot_welfare` – charts for `tornado_metrics` / `welfare_plots`.

## Perturbation structure (`config.yaml`)

| field | meaning |
|---|---|
| `target.component/attribute` | what to change |
| `target.kind` | `static` (`n.generators.p_nom`) or `timeseries` (`n.loads_t.p_set`, all snapshots) |
| `selector` | `names`, `carrier`, `countries`, `query` (pandas query), combined with AND |
| `per_country` | one independent case per country in `selector.countries` |
| `mode` | `relative` → value·(1±x); `absolute` → value±x, spread over selected assets proportionally to their value |
| `up` / `down` | independent magnitudes; an omitted one is not run |

## Notes

- Consumer surplus uses `voll` (demand is inelastic); load-shedding
  generators earn producer surplus at the shedding price.
- Country = `buses.country` if present, else the first
  `country_bus_prefix_length` characters of the bus name.
- Congestion rent is split 50/50 between the two countries of a line/link.
- `welfare_distribution_shift` = sum of absolute changes in each country's
  welfare share vs baseline.
- Connecting to pypsa-fbmc later means swapping `tornado_analysis/model.py:run_model`.
