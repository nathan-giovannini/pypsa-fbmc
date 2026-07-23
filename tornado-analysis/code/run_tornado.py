"""
Main driver for the tornado sensitivity analysis.

For every parameter in config.PARAMETERS (after expanding any
country-scoped entries into per-country parameters), runs the model with
the parameter set to -variation and +variation (all else at baseline),
plus one baseline run for reference.

Supports three types of perturbations:
- Percentage-based (variation): ±N%
- Discrete symmetric (discrete_change): ±N units, distributed proportionally across multiple elements
- Discrete asymmetric (discrete_change_low/high): ±N units with optional directional constraints

Two result files are produced, both written incrementally so a long run
can be interrupted safely:

- results/tornado_results.csv    one row per run, scalar metrics + a
                                  "welfare_distribution_shift" summary
                                  (how much welfare moved between countries,
                                  vs baseline -- use this as the tornado
                                  chart metric)
- results/welfare_by_country.csv one row per (run, country): the full
                                  welfare disaggregation (producer_surplus,
                                  storage_surplus, consumer_surplus,
                                  line_congestion_rent, link_congestion_rent,
                                  total), its share of total system welfare,
                                  and the change in that share vs baseline
                                  -- so the breakdown is available for
                                  further analysis later, not just totals

Usage:
    python run_tornado.py
"""

import os
import pypsa
import pandas as pd

from config import PARAMETERS, BASELINE_NETWORK_PATH, RESULTS_DIR, COUNTRY_BUS_PREFIX_LENGTH, FREEZE_EXPANSION_FLAG, BZ_RENAME_FLAG, BZ_RENAME_FILE
from perturb import apply_perturbation
from model_interface import run_model
from param_expansion import expand_parameters
from welfare import bus_country_map, distribution_shift, WELFARE_COMPONENT_COLUMNS
from baseline_preproc import freeze_expansion, bidding_zones_rename

WELFARE_COLUMNS = WELFARE_COMPONENT_COLUMNS + ["total"]


def _split_metrics(raw_metrics):
    """Pull the welfare_by_country dict out of the flat scalar metrics and
    turn it back into a DataFrame indexed by country."""
    metrics = dict(raw_metrics)
    welfare_dict = metrics.pop("welfare_by_country", {})
    welfare_df = pd.DataFrame.from_dict(welfare_dict, orient="index")
    welfare_df = welfare_df.reindex(columns=WELFARE_COLUMNS, fill_value=0)
    return metrics, welfare_df


def _welfare_rows(parameter, direction, welfare_df, baseline_df):
    all_countries = welfare_df.index.union(baseline_df.index)
    welfare_df = welfare_df.reindex(all_countries, fill_value=0)
    baseline_df = baseline_df.reindex(all_countries, fill_value=0)

    total = welfare_df["total"].sum()
    baseline_total = baseline_df["total"].sum()

    rows = []
    for country in all_countries:
        share = welfare_df.loc[country, "total"] / total if total else 0
        baseline_share = baseline_df.loc[country, "total"] / baseline_total if baseline_total else 0

        row = {"parameter": parameter, "direction": direction, "country": country}
        for col in WELFARE_COLUMNS:
            row[col] = welfare_df.loc[country, col]
        row["welfare_share"] = share
        row["delta_share_vs_baseline"] = share - baseline_share
        rows.append(row)
    return rows


def _get_perturbation_description(param):
    """Generate a human-readable description of the perturbation magnitude and type."""
    if "variation" in param:
        return f"{param['variation']*100:.0f}%"
    elif "discrete_change_low" in param or "discrete_change_high" in param:
        parts = []
        if "discrete_change_low" in param:
            parts.append(f"-{param['discrete_change_low']}")
        if "discrete_change_high" in param:
            parts.append(f"+{param['discrete_change_high']}")
        return "/".join(parts) if len(parts) == 2 else parts[0]
    elif "discrete_change" in param:
        return f"±{param['discrete_change']}"
    return "unknown"


def _should_run_direction(param, direction):
    """Check if a particular direction should be run for this parameter."""
    if "variation" in param or "discrete_change" in param:
        # Percentage-based and symmetric discrete always run both directions
        return True
    
    # Asymmetric discrete changes
    if direction == "low" and "discrete_change_low" not in param:
        return False
    if direction == "high" and "discrete_change_high" not in param:
        return False
    return True


def _save(tornado_records, welfare_records, tornado_path, welfare_path):
    pd.DataFrame(tornado_records).to_csv(tornado_path, index=False)
    pd.DataFrame(welfare_records).to_csv(welfare_path, index=False)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    tornado_path = os.path.join(RESULTS_DIR, "tornado_results.csv")
    welfare_path = os.path.join(RESULTS_DIR, "welfare_by_country.csv")

    print(f"Loading baseline network from {BASELINE_NETWORK_PATH}")
    baseline_network = pypsa.Network(BASELINE_NETWORK_PATH)

    #baseline_network.set_snapshots(baseline_network.snapshots[:24]) #for quick runs
    bus_country = bus_country_map(baseline_network, prefix_length=COUNTRY_BUS_PREFIX_LENGTH)

    if FREEZE_EXPANSION_FLAG == True:
        baseline_network = freeze_expansion(baseline_network)

    if BZ_RENAME_FLAG == True:
        baseline_network = bidding_zones_rename(baseline_network, BZ_RENAME_FILE)

    parameters = expand_parameters(PARAMETERS, bus_country)
    print(f"{len(PARAMETERS)} configured parameter(s) expanded to {len(parameters)} "
          f"parameter run(s) (country-scoped entries become one run per country).")

    print("Running baseline case...")
    baseline_metrics, baseline_welfare = _split_metrics(run_model(baseline_network.copy()))
    print(f"Baseline metrics: {baseline_metrics}")

    tornado_records = [{
        "parameter": "baseline", "direction": "baseline", "status": "ok",
        "welfare_distribution_shift": 0.0, **baseline_metrics,
    }]
    welfare_records = _welfare_rows("baseline", "baseline", baseline_welfare, baseline_welfare)
    _save(tornado_records, welfare_records, tornado_path, welfare_path)

    for param in parameters:
        for direction in ["low", "high"]:
            # Skip directions that aren't defined for asymmetric discrete changes
            if not _should_run_direction(param, direction):
                print(f"Skipping '{param['name']}' [{direction}] (not configured for this direction)")
                continue
            
            perturbation_desc = _get_perturbation_description(param)
            sign = "-" if direction == "low" else "+"
            print(f"Running '{param['name']}' [{direction}] ({sign}{perturbation_desc}) ...")
            perturbed_network = apply_perturbation(baseline_network, param, direction)

            try:
                metrics, welfare = _split_metrics(run_model(perturbed_network))
                shift = distribution_shift(baseline_welfare["total"], welfare["total"])
                status = "ok"
            except Exception as e:
                print(f"  FAILED: {e}")
                metrics = {k: None for k in baseline_metrics}
                welfare = pd.DataFrame(columns=WELFARE_COLUMNS)
                shift = None
                status = f"failed: {e}"

            tornado_records.append({
                "parameter": param["name"],
                "direction": direction,
                "status": status,
                "welfare_distribution_shift": shift,
                **metrics,
            })
            welfare_records.extend(_welfare_rows(param["name"], direction, welfare, baseline_welfare))

            _save(tornado_records, welfare_records, tornado_path, welfare_path)

    print(f"\nDone. Results saved to {tornado_path} and {welfare_path}")


if __name__ == "__main__":
    main()
