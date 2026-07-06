#!/usr/bin/env python3
"""
Generate boxplot comparing ICA-JH13 vs ICAWeights13 MLU from batch results.

Usage:
    python3 gen_boxplot_icajh13.py [batch_result_icajh13.csv]

Output: icajh13_vs_icaweights13_boxplot.png
"""

import csv, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(SCRIPT_DIR, "batch_result_icajh13.csv")
OUT_PNG     = os.path.join(SCRIPT_DIR, "icajh13_vs_icaweights13_boxplot.png")

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV


def load_data(csv_path):
    data = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp  = row["experiment"]
            mlu  = float(row["measured_mlu"])
            data.setdefault(exp, []).append(mlu)
    return data


def main():
    data = load_data(CSV_PATH)

    # Fixed display order: ICA-JH first, then ECMP baseline
    order = ["ICAJH13", "ICAWeights13"]
    labels = [
        "ICA-JH13\n(SRv6 waypoints)",
        "ICAWeights13\n(ECMP, no SRv6)",
    ]

    plot_data  = [data.get(k, []) for k in order]
    plot_ticks = list(range(1, len(order) + 1))

    fig, ax = plt.subplots(figsize=(7, 5))
    bp = ax.boxplot(
        plot_data,
        positions=plot_ticks,
        vert=True,
        patch_artist=True,
        widths=0.4,
        boxprops=dict(facecolor="steelblue", color="navy"),
        medianprops=dict(color="red", linewidth=2),
        whiskerprops=dict(color="navy"),
        capprops=dict(color="navy"),
        flierprops=dict(marker="o", color="navy", markersize=4),
    )

    ax.set_xticks(plot_ticks)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Maximum Link Utilization (MLU)", fontsize=12)
    ax.set_title(
        "Phase 2: ICA-JH13 vs ICAWeights13\n"
        "13-node topology, gateway node 4, four demands, TIME=120s, NSTREAMS=8",
        fontsize=11,
    )
    ax.set_ylim(0, max(max(d) for d in plot_data if d) * 1.2 + 0.1)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    # Annotate with sample count
    for i, (pos, d) in enumerate(zip(plot_ticks, plot_data)):
        ax.text(pos, ax.get_ylim()[0] + 0.02, f"n={len(d)}",
                ha="center", fontsize=9, color="gray")

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
