#!/usr/bin/env python3
"""Plot average RF distance of wQFM vs wQ²A on the 48-taxon simulated avian dataset.

Panel (a): varying ILS (0.5X, 1X, 2X) at 1000 genes, 500 bp.
Panel (b): varying number of genes (50-1000) at 1X ILS, 500 bp.
Bars are means over replicates with standard-error bars; the number of
replicates per condition is shown under each tick.
"""

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FILE_PATTERN = re.compile(r"^(0\.5X|1X|2X)-(\d+)-(\d+)_R\d+_weighted_quartets$")

PANELS = [
    ("(a)", "ILS Level", "Varying ILS (1000 genes, 500 bp)",
     [(ils, (ils, 1000, 500)) for ils in ["0.5X", "1X", "2X"]]),
    ("(b)", "Number of genes", "Varying numbers of genes (1X ILS, 500 bp)",
     [(f"{g}g", ("1X", g, 500)) for g in [50, 100, 200, 500, 1000]]),
]
SERIES = [
    ("rf_wqfm_wrt_base", "wQFM", "#eb6834"),
    ("rf_quantum_wrt_base", r"wQ$^2$A", "#2a78d6"),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="results CSV from run_48_taxa_z12_benchmark.sh")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def load(csv_path):
    groups = {}
    with open(csv_path, newline="") as handle:
        for row in csv.DictReader(handle):
            match = FILE_PATTERN.match(row["quartet_file_name"])
            if not match:
                raise ValueError(f"Unrecognised file name: {row['quartet_file_name']}")
            key = (match.group(1), int(match.group(2)), int(match.group(3)))
            bucket = groups.setdefault(key, {column: [] for column, _, _ in SERIES})
            for column, _, _ in SERIES:
                bucket[column].append(float(row[column]))
    return groups


def mean_se(values):
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def main():
    args = parse_args()
    groups = load(args.csv)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8), gridspec_kw={"width_ratios": [3, 5]})
    bar_width = 0.36

    for ax, (letter, xlabel, caption, conditions) in zip(axes, PANELS):
        ax.set_facecolor("#ebebeb")
        ax.grid(axis="y", color="white", linewidth=1.2)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)

        for key in (key for _, key in conditions):
            if key not in groups:
                raise ValueError(f"No rows for condition {key}")

        positions = range(len(conditions))
        y_top = 0.0
        for offset_index, (column, label, color) in enumerate(SERIES):
            offset = (offset_index - (len(SERIES) - 1) / 2) * bar_width
            stats = [mean_se(groups[key][column]) for _, key in conditions]
            means = [m for m, _ in stats]
            errors = [e for _, e in stats]
            xs = [p + offset for p in positions]
            ax.bar(xs, means, width=bar_width, color=color, edgecolor="black",
                   linewidth=0.8, label=label, zorder=3)
            ax.errorbar(xs, means, yerr=errors, fmt="none", ecolor="black",
                        elinewidth=1.1, capsize=4, capthick=1.1, zorder=4)
            y_top = max(y_top, max(m + e for m, e in stats))

        ax.set_ylim(0, y_top * 1.2)
        ax.set_xticks(list(positions))
        ax.set_xticklabels([f"{tick}\navg. over\n{len(groups[key][SERIES[0][0]])} replicates"
                            for tick, key in conditions], fontsize=10.5)
        ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
        ax.set_ylabel("Avg. Robinson–Foulds distance", fontsize=11, fontweight="bold")
        ax.tick_params(length=0, labelsize=11)
        ax.legend(loc="upper right", frameon=True, facecolor="white",
                  edgecolor="white", fontsize=11)
        ax.text(-0.04, 1.04, letter, transform=ax.transAxes, ha="right",
                va="bottom", fontsize=20, fontweight="bold")
        ax.text(0.5, -0.3, caption, transform=ax.transAxes, ha="center",
                va="top", fontsize=14, family="serif")

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
