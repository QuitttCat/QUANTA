#!/usr/bin/env python3
"""Plot average RF distance of wQFM vs wQ²A on the 11-taxon dataset.

Panel (a): estimated gene trees, panel (b): true (simulated) gene trees,
each grouped by number of genes, with standard-error bars over replicates.
"""

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FILE_PATTERN = re.compile(
    r"^(estimated|simulated)_Xgenes_strongILS_\1_(\d+)genes_strongILS_R\d+_weighted_quartets$"
)
GENE_COUNTS = [5, 15, 25, 50, 100]
PANELS = [
    ("estimated", "(a)", "Analysis of estimated gene trees."),
    ("simulated", "(b)", "Analysis of true gene trees."),
]
SERIES = [
    ("rf_wqfm_wrt_base", "wQFM", "#eb6834"),
    ("rf_bruteforce_wrt_base", r"wQ$^2$A (bruteforce)", "#2a78d6"),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="results CSV from run_11_taxa_benchmark.sh")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def load(csv_path):
    groups = {}
    with open(csv_path, newline="") as handle:
        for row in csv.DictReader(handle):
            match = FILE_PATTERN.match(row["quartet_file_name"])
            if not match:
                raise ValueError(f"Unrecognised file name: {row['quartet_file_name']}")
            key = (match.group(1), int(match.group(2)))
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

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharey=True)
    bar_width = 0.36
    y_top = 0.0

    for ax, (mode, letter, title) in zip(axes, PANELS):
        ax.set_facecolor("#ebebeb")
        ax.grid(axis="y", color="white", linewidth=1.2)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)

        positions = range(len(GENE_COUNTS))
        for offset_index, (column, label, color) in enumerate(SERIES):
            offset = (offset_index - (len(SERIES) - 1) / 2) * bar_width
            stats = [mean_se(groups.get((mode, g), {}).get(column, [0.0])) for g in GENE_COUNTS]
            means = [m for m, _ in stats]
            errors = [e for _, e in stats]
            xs = [p + offset for p in positions]
            ax.bar(xs, means, width=bar_width, color=color, edgecolor="black",
                   linewidth=0.8, label=label, zorder=3)
            ax.errorbar(xs, means, yerr=errors, fmt="none", ecolor="black",
                        elinewidth=1.1, capsize=4, capthick=1.1, zorder=4)
            y_top = max(y_top, max(m + e for m, e in stats))

        ax.set_xticks(list(positions))
        ax.set_xticklabels([f"{g}g" for g in GENE_COUNTS], fontsize=11)
        ax.set_xlabel("No. of genes", fontsize=11, fontweight="bold")
        ax.tick_params(length=0, labelsize=11)
        ax.legend(loc="upper right", frameon=True, facecolor="white",
                  edgecolor="white", fontsize=11)
        ax.text(-0.06, 1.04, letter, transform=ax.transAxes, ha="left",
                va="bottom", fontsize=20, fontweight="bold")
        ax.text(0.5, -0.2, title, transform=ax.transAxes, ha="center",
                va="top", fontsize=15, family="serif")

    axes[0].set_ylabel("Avg. Robinson–Foulds distance", fontsize=11, fontweight="bold")
    axes[1].tick_params(labelleft=True)
    axes[0].set_ylim(0, max(y_top * 1.15, 0.05))

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
