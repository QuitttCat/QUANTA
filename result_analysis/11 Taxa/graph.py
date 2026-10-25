#!/usr/bin/env python3
"""Plot average RF distance of QUANTA, wQFM, wQMC and ASTRAL on the 11-taxon dataset.

Panel (a): estimated gene trees, panel (b): true (simulated) gene trees,
each grouped by number of genes, with standard-error bars over replicates.

QUANTA and wQFM come from the benchmark results CSV (QUANTA = the brute-force
QUBO solution, column rf_bruteforce_wrt_base); wQMC and ASTRAL come from
baselines/results/ (run_wqmc.py, run_astral.py) on the same quartet files.
"""

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
FILE_PATTERN = re.compile(
    r"^(estimated|simulated)_Xgenes_strongILS_\1_(\d+)genes_strongILS_R\d+_weighted_quartets$"
)
GENE_COUNTS = [5, 15, 25, 50, 100]
PANELS = [
    ("estimated", "(a)", "Analysis of estimated gene trees."),
    ("simulated", "(b)", "Analysis of true gene trees."),
]
# (source, column, label, color). Colors are the first four slots of a
# colorblind-validated categorical palette, kept in this order so that
# neighbouring bars stay distinguishable.
SERIES = [
    ("results", "rf_bruteforce_wrt_base", "QUANTA (bruteforce, ours)", "#2a78d6"),
    ("results", "rf_wqfm_wrt_base", "wQFM", "#eb6834"),
    ("wqmc", "rf", "wQMC", "#1baf7a"),
    ("astral", "rf", "ASTRAL", "#eda100"),
]
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="results CSV from run_11_taxa_benchmark.sh")
    parser.add_argument("--wqmc-csv", default=REPO / "baselines" / "results" / "wqmc_results.csv")
    parser.add_argument("--astral-csv", default=REPO / "baselines" / "results" / "astral_results.csv")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def read_rows(path, name_column, group=None):
    with open(path, newline="") as handle:
        return {row[name_column]: row for row in csv.DictReader(handle)
                if group is None or row["group"] == group}


def load(args):
    sources = {
        "results": read_rows(args.csv, "quartet_file_name"),
        "wqmc": read_rows(args.wqmc_csv, "input_file", group="11"),
        "astral": read_rows(args.astral_csv, "input_file", group="11"),
    }
    groups = {}
    for name in sources["results"]:
        match = FILE_PATTERN.match(name)
        if not match:
            raise ValueError(f"Unrecognised file name: {name}")
        key = (match.group(1), int(match.group(2)))
        bucket = groups.setdefault(key, {label: [] for _, _, label, _ in SERIES})
        for source, column, label, _ in SERIES:
            if name not in sources[source]:
                raise ValueError(f"{source} has no result for {name}")
            bucket[label].append(float(sources[source][name][column]))
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
    groups = load(args)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
    bar_width = 0.2
    y_top = 0.0

    for ax, (mode, letter, title) in zip(axes, PANELS):
        ax.set_facecolor("white")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side, spine in ax.spines.items():
            spine.set_visible(side == "bottom")
        ax.spines["bottom"].set_color(AXIS)

        positions = range(len(GENE_COUNTS))
        for offset_index, (_, _, label, color) in enumerate(SERIES):
            offset = (offset_index - (len(SERIES) - 1) / 2) * bar_width
            stats = [mean_se(groups[(mode, g)][label]) for g in GENE_COUNTS]
            means = [m for m, _ in stats]
            errors = [e for _, e in stats]
            xs = [p + offset for p in positions]
            ax.bar(xs, means, width=bar_width, color=color, edgecolor="white",
                   linewidth=1.2, label=label, zorder=3)
            ax.errorbar(xs, means, yerr=errors, fmt="none", ecolor=MUTED,
                        elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
            y_top = max(y_top, max(m + e for m, e in stats))

        ax.set_xticks(list(positions))
        ax.set_xticklabels([f"{g}g" for g in GENE_COUNTS], fontsize=14, color=INK)
        ax.set_xlabel("No. of genes", fontsize=14, fontweight="bold", color=INK)
        ax.tick_params(axis="both", length=0, labelsize=14, labelcolor=INK)
        ax.text(-0.06, 1.03, letter, transform=ax.transAxes, ha="left",
                va="bottom", fontsize=20, fontweight="bold", color=INK)
        ax.text(0.5, -0.2, title, transform=ax.transAxes, ha="center",
                va="top", fontsize=16, family="serif", color=INK)

    axes[0].set_ylabel("Avg. Robinson–Foulds distance", fontsize=14, fontweight="bold", color=INK)
    axes[1].tick_params(labelleft=True)
    axes[0].set_ylim(0, max(y_top * 1.1, 0.05))

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(SERIES), frameon=False,
               fontsize=14, bbox_to_anchor=(0.5, 1.0), handlelength=1.4, columnspacing=1.6)
    fig.tight_layout(rect=[0, 0.04, 1, 0.92])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
