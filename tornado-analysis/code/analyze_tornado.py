"""
Build a tornado chart from the results produced by run_tornado.py.

Usage:
    python analyze_tornado.py --metric total_system_cost
"""

import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

from config import RESULTS_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", default="welfare_distribution_shift",
                         help="Output metric column to build the tornado chart for "
                              "(e.g. 'welfare_distribution_shift', 'total_system_cost', "
                              "'avg_electricity_price')")
    parser.add_argument("--results-csv",
                         default=os.path.join(RESULTS_DIR, "tornado_results.csv"))
    args = parser.parse_args()

    df = pd.read_csv(args.results_csv)
    baseline_value = df.loc[df["direction"] == "baseline", args.metric].iloc[0]

    pivot = df[df["direction"].isin(["low", "high"])].pivot(
        index="parameter", columns="direction", values=args.metric
    )
    pivot["delta_low"] = pivot["low"] - baseline_value
    pivot["delta_high"] = pivot["high"] - baseline_value
    pivot["range"] = (pivot["high"] - pivot["low"]).abs()
    pivot = pivot.sort_values("range")  # largest impact at top when plotted

    fig, ax = plt.subplots(figsize=(9, 0.5 * len(pivot) + 2))

    for i, (_, row) in enumerate(pivot.iterrows()):
        left = min(row["delta_low"], row["delta_high"])
        width = abs(row["delta_high"] - row["delta_low"])
        ax.barh(i, width, left=left, color="#4C72B0", alpha=0.85)

    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(pivot.index)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel(f"Change in {args.metric} vs baseline ({baseline_value:.2f})")
    ax.set_title(f"Tornado chart: {args.metric}")
    plt.tight_layout()

    out_path = os.path.join(RESULTS_DIR, f"tornado_{args.metric}.png")
    plt.savefig(out_path, dpi=150)
    print(f"Saved chart to {out_path}")


if __name__ == "__main__":
    main()
