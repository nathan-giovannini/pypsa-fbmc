"""
Main driver for the tornado sensitivity analysis.

For every parameter in config.PARAMETERS (after expanding any
country-scoped entries into per-country parameters), runs the model with
the parameter set to -variation and +variation (all else at baseline),
plus one baseline run for reference.

Two result files are produced, both written incrementally so a long run
can be interrupted safely:

- results/tornado_results.csv    one row per run, scalar metrics + a
                                  "welfare_distribution_shift" summary
                                  (how much welfare moved between countries,
                                  vs baseline -- use this as the tornado
                                  chart metric)
- results/welfare_by_country.csv one row per (run, country): welfare level,
                                  its share of total system welfare, and
                                  the change in that share vs baseline

Usage:
    python run_tornado.py
"""

import os
import pypsa
import pandas as pd

from config import PARAMETERS, BASELINE_NETWORK_PATH, RESULTS_DIR, COUNTRY_BUS_PREFIX_LENGTH
from perturb import apply_perturbation
from model_interface import run_model
from param_expansion import expand_parameters
from welfare import bus_country_map, distribution_shift


def _split_metrics(raw_metrics):
    """Pull the welfare_by_country dict out of the flat scalar metrics."""
    metrics = dict(raw_metrics)
    welfare = metrics.pop("welfare_by_country", {})
    return metrics, pd.Series(welfare, dtype=float)


def _welfare_rows(parameter, direction, welfare, baseline_welfare):
    all_countries = welfare.index.union(baseline_welfare.index)
    welfare = welfare.reindex(all_countries, fill_value=0)
    baseline_welfare = baseline_welfare.reindex(all_countries, fill_value=0)

    total = welfare.sum()
    baseline_total = baseline_welfare.sum()

    rows = []
    for country in all_countries:
        share = welfare[country] / total if total else 0
        baseline_share = baseline_welfare[country] / baseline_total if baseline_total else 0
        rows.append({
            "parameter": parameter,
            "direction": direction,
            "country": country,
            "welfare": welfare[country],
            "welfare_share": share,
            "delta_share_vs_baseline": share - baseline_share,
        })
    return rows


def _save(tornado_records, welfare_records, tornado_path, welfare_path):
    pd.DataFrame(tornado_records).to_csv(tornado_path, index=False)
    pd.DataFrame(welfare_records).to_csv(welfare_path, index=False)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    tornado_path = os.path.join(RESULTS_DIR, "tornado_results.csv")
    welfare_path = os.path.join(RESULTS_DIR, "welfare_by_country.csv")

    print(f"Loading baseline network from {BASELINE_NETWORK_PATH}")
    baseline_network = pypsa.Network(BASELINE_NETWORK_PATH)
    bus_country = bus_country_map(baseline_network, prefix_length=COUNTRY_BUS_PREFIX_LENGTH)
    ## here I can put also the pre-processing of the baseline_network (capacity-freeze, zone_columns)

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
            print(f"Running '{param['name']}' [{direction}] "
                  f"({'-' if direction == 'low' else '+'}{param['variation']*100:.0f}%) ...")
            perturbed_network = apply_perturbation(baseline_network, param, direction)

            try:
                metrics, welfare = _split_metrics(run_model(perturbed_network))
                shift = distribution_shift(baseline_welfare, welfare)
                status = "ok"
            except Exception as e:
                print(f"  FAILED: {e}")
                metrics = {k: None for k in baseline_metrics}
                welfare = pd.Series(dtype=float)
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
