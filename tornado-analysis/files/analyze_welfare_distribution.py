"""
Plot how welfare shares by country change for a given parameter run,
compared to baseline. Use this after run_tornado.py to drill into
*which* countries gain/lose share for the parameters that showed up as
big movers in the tornado chart (welfare_distribution_shift).

Usage:
    python analyze_welfare_distribution.py --parameter "Gas price - DE" --direction high
"""

import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

from config import RESULTS_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameter", required=True,
                         help="Exact parameter name as it appears in welfare_by_country.csv "
                              "(country-scoped parameters are named '<name> - <country>')")
    parser.add_argument("--direction", choices=["low", "high"], required=True)
    parser.add_argument("--welfare-csv", default=os.path.join(RESULTS_DIR, "welfare_by_country.csv"))
    args = parser.parse_args()

    df = pd.read_csv(args.welfare_csv)

    baseline = df[df["direction"] == "baseline"].set_index("country")["welfare_share"]
    run = df[(df["parameter"] == args.parameter) & (df["direction"] == args.direction)]
    if run.empty:
        raise SystemExit(
            f"No rows found for parameter='{args.parameter}', direction='{args.direction}'. "
            f"Check the exact name in {args.welfare_csv}."
        )
    run = run.set_index("country")["welfare_share"]

    countries = baseline.index.union(run.index)
    baseline = baseline.reindex(countries, fill_value=0)
    run = run.reindex(countries, fill_value=0)

    x = range(len(countries))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], baseline.values, width, label="Baseline")
    ax.bar([i + width / 2 for i in x], run.values, width, label=f"{args.parameter} ({args.direction})")

    ax.set_xticks(list(x))
    ax.set_xticklabels(countries)
    ax.set_ylabel("Share of total system welfare")
    ax.set_title(f"Welfare distribution: baseline vs {args.parameter} [{args.direction}]")
    ax.legend()
    plt.tight_layout()

    safe_name = args.parameter.replace(" ", "_").replace("/", "_")
    out_path = os.path.join(RESULTS_DIR, f"welfare_dist_{safe_name}_{args.direction}.png")
    plt.savefig(out_path, dpi=150)
    print(f"Saved chart to {out_path}")


if __name__ == "__main__":
    main()
