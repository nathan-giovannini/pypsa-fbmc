"""Workflow steps called by the Snakefile (one function per rule)."""

import json
import os

import pandas as pd
import pypsa

from .baseline import prepare_baseline
from .model import run_model
from .perturb import apply_perturbation
from .welfare import WELFARE_COMPONENT_COLUMNS, bus_country_map, distribution_shift, welfare_shares

WELFARE_COLUMNS = WELFARE_COMPONENT_COLUMNS + ["total"]


def step_prepare_baseline(network_path, out_path, baseline_cfg, prefix_length):
    n = pypsa.Network(network_path)
    n = prepare_baseline(n, baseline_cfg, prefix_length)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n.export_to_netcdf(out_path)


def step_run_case(baseline_path, case, solver, prefix_length, voll, out_dir):
    """case=None runs the unperturbed baseline."""
    n = pypsa.Network(baseline_path)
    if case is not None:
        bus_country = bus_country_map(n, prefix_length=prefix_length)
        n = apply_perturbation(n, case, bus_country)
    result = run_model(n, solver, prefix_length, voll)
    os.makedirs(out_dir, exist_ok=True)
    welfare = pd.DataFrame.from_dict(result.pop("welfare_by_country"), orient="index")
    welfare = welfare.reindex(columns=WELFARE_COLUMNS, fill_value=0)
    welfare.index.name = "country"
    welfare.to_csv(os.path.join(out_dir, "welfare.csv"))
    meta = {"parameter": "baseline", "direction": "baseline"} if case is None else {
        "parameter": case["parameter"], "direction": case["direction"]}
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump({**meta, **result}, f, indent=2)


def step_aggregate(results_dir, case_ids, tornado_path, welfare_path):
    def load(case_dir):
        with open(os.path.join(case_dir, "metrics.json")) as f:
            metrics = json.load(f)
        return metrics, pd.read_csv(os.path.join(case_dir, "welfare.csv"), index_col="country")

    base_metrics, base_welfare = load(os.path.join(results_dir, "cases", "baseline"))
    base_total = base_welfare["total"]
    tornado, welfare_rows = [], []
    for case_id in ["baseline"] + list(case_ids):
        metrics, welfare = load(os.path.join(results_dir, "cases", case_id))
        shift = distribution_shift(base_total, welfare["total"])
        tornado.append({**metrics, "welfare_distribution_shift": shift})
        countries = welfare.index.union(base_welfare.index)
        w = welfare.reindex(countries, fill_value=0)
        b = base_welfare.reindex(countries, fill_value=0)
        share = welfare_shares(w["total"])
        base_share = welfare_shares(b["total"])
        for c in countries:
            welfare_rows.append({
                "parameter": metrics["parameter"], "direction": metrics["direction"], "country": c,
                **{col: w.loc[c, col] for col in WELFARE_COLUMNS},
                "welfare_share": share[c], "delta_share_vs_baseline": share[c] - base_share[c],
            })
    pd.DataFrame(tornado).to_csv(tornado_path, index=False)
    pd.DataFrame(welfare_rows).to_csv(welfare_path, index=False)


def step_plot_tornado(results_csv, metric, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(results_csv)
    base = df.loc[df["direction"] == "baseline", metric].iloc[0]
    pivot = df[df["direction"].isin(["down", "up"])].pivot(index="parameter", columns="direction", values=metric)
    for d in ("down", "up"):
        if d not in pivot:
            pivot[d] = base  # direction never run -> no change drawn
    pivot = pivot.fillna(base)
    pivot["delta_down"] = pivot["down"] - base
    pivot["delta_up"] = pivot["up"] - base
    pivot["span"] = (pivot["up"] - pivot["down"]).abs()
    pivot = pivot.sort_values("span")

    fig, ax = plt.subplots(figsize=(9, 0.5 * len(pivot) + 2))
    for i, (_, r) in enumerate(pivot.iterrows()):
        ax.barh(i, r["delta_down"], color="#C44E52", alpha=0.85, label="down" if i == 0 else None)
        ax.barh(i, r["delta_up"], color="#4C72B0", alpha=0.85, label="up" if i == 0 else None)
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(pivot.index)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel(f"Change in {metric} vs baseline ({base:.2f})")
    ax.set_title(f"Tornado chart: {metric}")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


def step_plot_welfare(welfare_csv, parameter, direction, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(welfare_csv)
    base = df[df["direction"] == "baseline"].set_index("country")["welfare_share"]
    run = df[(df["parameter"] == parameter) & (df["direction"] == direction)]
    if run.empty:
        raise SystemExit(f"No rows for parameter='{parameter}', direction='{direction}' in {welfare_csv}")
    run = run.set_index("country")["welfare_share"]
    countries = base.index.union(run.index)
    base, run = base.reindex(countries, fill_value=0), run.reindex(countries, fill_value=0)
    x = range(len(countries))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - 0.175 for i in x], base.values, 0.35, label="Baseline")
    ax.bar([i + 0.175 for i in x], run.values, 0.35, label=f"{parameter} ({direction})")
    ax.set_xticks(list(x))
    ax.set_xticklabels(countries)
    ax.set_ylabel("Share of total system welfare")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
