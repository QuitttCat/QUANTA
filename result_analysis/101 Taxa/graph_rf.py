#!/usr/bin/env python3
"""Plot average RF distance of QUANTA, wQFM, wQMC and ASTRAL on the 101-taxon
dataset (1000 true gene trees, 19 replicates).

Bars are means over replicates with standard-error bars, in the style of the
37- and 48-taxon figures. QUANTA (D-Wave QPU for partitions with n>20) and
wQFM come from the benchmark results CSV; wQMC and ASTRAL come from
baselines/results/ (run_wqmc.py, run_astral.py) on the same quartet files.
"""

import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
# (source, column, label, color), same order and colors as the other figures
SERIES = [
    ("results", "rf_quantum_wrt_base", "QUANTA\n(QPU, ours)", "#2a78d6"),
    ("results", "rf_wqfm_wrt_base", "wQFM", "#eb6834"),
    ("wqmc", "rf", "wQMC", "#1baf7a"),
    ("astral", "rf", "ASTRAL", "#eda100"),
]
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="results CSV from run_101_taxa_benchmark.sh")
    parser.add_argument("--wqmc-csv", default=REPO / "baselines" / "results" / "wqmc_results.csv")
    parser.add_argument("--astral-csv", default=REPO / "baselines" / "results" / "astral_results.csv")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def read_rows(path, name_column, group=None):
    with open(path, newline="") as handle:
        return {row[name_column]: row for row in csv.DictReader(handle)
                if group is None or row["group"] == group}


def mean_se(values):
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def main():
    args = parse_args()
    sources = {
        "results": read_rows(args.csv, "quartet_file_name"),
        "wqmc": read_rows(args.wqmc_csv, "input_file", group="101"),
        "astral": read_rows(args.astral_csv, "input_file", group="101"),
    }
    names = sorted(sources["results"])
    for source in ("wqmc", "astral"):
        missing = [n for n in names if n not in sources[source]]
        if missing:
            raise ValueError(f"{source} has no result for {missing}")

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.set_facecolor("white")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(AXIS)

    y_top = 0.0
    for x, (source, column, label, color) in enumerate(SERIES):
        mean, se = mean_se([float(sources[source][n][column]) for n in names])
        ax.bar(x, mean, width=0.62, color=color, edgecolor="white", linewidth=1.2, zorder=3)
        ax.errorbar(x, mean, yerr=se, fmt="none", ecolor=MUTED, elinewidth=1.0,
                    capsize=4, capthick=1.0, zorder=4)
        y_top = max(y_top, mean + se)

    ax.set_ylim(0, y_top * 1.15)
    ax.set_xticks(range(len(SERIES)))
    ax.set_xticklabels([label for _, _, label, _ in SERIES], fontsize=13, color=INK)
    ax.set_ylabel("Avg. Robinson–Foulds distance", fontsize=13, fontweight="bold", color=INK)
    ax.tick_params(axis="both", length=0, labelsize=12, labelcolor=INK)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out} ({len(names)} replicates)")


if __name__ == "__main__":
    main()
