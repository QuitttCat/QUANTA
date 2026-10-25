#!/usr/bin/env python3
"""Plot average RF distance of QUANTA, wQFM, wQMC and ASTRAL on the 37-taxon
simulated mammalian dataset.

Panel (a): varying ILS (0.5X, 1X, 2X) at 200 genes, 500 bp.
Panel (b): varying sequence length (250-1500 bp, true gene trees) at 200 genes, 1X ILS.
Panel (c): varying number of genes (25-800) at 500 bp, 1X ILS.
Bars are means over replicates with standard-error bars.

QUANTA (D-Wave QPU for partitions with n>20) and wQFM come from the benchmark
results CSV; wQMC and ASTRAL come from baselines/results/ (run_wqmc.py,
run_astral.py) on the same quartet files. plot() is shared with graph_solvers.py.
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
FILE_PATTERN = re.compile(r"^(noscale|scale2d|scale2u)\.(\d+)g\.(\d+b|true)_R\d+_weighted_quartets$")

PANELS = [
    ("(a)", "ILS Level", "Varying ILS (estimated gene trees)",
     [("0.5X", ("scale2d", 200, "500b")),
      ("1X", ("noscale", 200, "500b")),
      ("2X", ("scale2u", 200, "500b"))]),
    ("(b)", "Sequence Length", "Varying sequence lengths",
     [(label, ("noscale", 200, label)) for label in ["250b", "500b", "1000b", "1500b", "true"]]),
    ("(c)", "Number of genes", "Varying numbers of genes (estimated gene trees)",
     [(f"{g}g", ("noscale", g, "500b")) for g in [25, 50, 100, 200, 400, 800]]),
]
# (source, column, label, color). Colors are the first four slots of a
# colorblind-validated categorical palette, kept in this order so that
# neighbouring bars stay distinguishable.
SERIES = [
    ("results", "rf_quantum_wrt_base", "QUANTA (QPU, ours)", "#2a78d6"),
    ("results", "rf_wqfm_wrt_base", "wQFM", "#eb6834"),
    ("wqmc", "rf", "wQMC", "#1baf7a"),
    ("astral", "rf", "ASTRAL", "#eda100"),
]
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="results CSV from run_37_taxa_benchmark.sh")
    parser.add_argument("--wqmc-csv", default=REPO / "baselines" / "results" / "wqmc_results.csv")
    parser.add_argument("--astral-csv", default=REPO / "baselines" / "results" / "astral_results.csv")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def read_rows(path, name_column, group=None):
    with open(path, newline="") as handle:
        return {row[name_column]: row for row in csv.DictReader(handle)
                if group is None or row["group"] == group}


def group_values(sources, series):
    """Mean-able RF lists per (scale, genes, length) condition and series label.

    The first source defines the quartet files; every other source must have
    a result for each of them.
    """
    files = next(iter(sources.values()))
    groups = {}
    for name in files:
        match = FILE_PATTERN.match(name)
        if not match:
            raise ValueError(f"Unrecognised file name: {name}")
        key = (match.group(1), int(match.group(2)), match.group(3))
        bucket = groups.setdefault(key, {label: [] for _, _, label, _ in series})
        for source, column, label, _ in series:
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


def plot(groups, series, out, extra_panel=None):
    """Draw the three bar panels; extra_panel(ax), if given, draws a fourth, narrower one."""
    widths = [1] * len(PANELS) + ([0.8] if extra_panel else [])
    fig, axes = plt.subplots(1, len(widths), figsize=(18 + (5 if extra_panel else 0), 5.4),
                             gridspec_kw={"width_ratios": widths})
    bar_width = 0.8 / len(series)

    for ax, (letter, xlabel, caption, conditions) in zip(axes, PANELS):
        ax.set_facecolor("white")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side, spine in ax.spines.items():
            spine.set_visible(side == "bottom")
        ax.spines["bottom"].set_color(AXIS)

        positions = range(len(conditions))
        y_top = 0.0
        for offset_index, (_, _, label, color) in enumerate(series):
            offset = (offset_index - (len(series) - 1) / 2) * bar_width
            stats = []
            for tick, key in conditions:
                if key not in groups:
                    raise ValueError(f"No rows for condition {key} ({tick})")
                stats.append(mean_se(groups[key][label]))
            means = [m for m, _ in stats]
            errors = [e for _, e in stats]
            xs = [p + offset for p in positions]
            ax.bar(xs, means, width=bar_width, color=color, edgecolor="white",
                   linewidth=1.2, label=label, zorder=3)
            ax.errorbar(xs, means, yerr=errors, fmt="none", ecolor=MUTED,
                        elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
            y_top = max(y_top, max(m + e for m, e in stats))

        ax.set_ylim(0, y_top * 1.12)
        ax.set_xticks(list(positions))
        ax.set_xticklabels([tick for tick, _ in conditions], fontsize=14, color=INK)
        ax.set_xlabel(xlabel, fontsize=14, fontweight="bold", color=INK)
        ax.set_ylabel("Avg. Robinson–Foulds distance", fontsize=14, fontweight="bold", color=INK)
        ax.tick_params(axis="both", length=0, labelsize=14, labelcolor=INK)
        ax.text(-0.08, 1.03, letter, transform=ax.transAxes, ha="left",
                va="bottom", fontsize=20, fontweight="bold", color=INK)
        ax.text(0.5, -0.2, caption, transform=ax.transAxes, ha="center",
                va="top", fontsize=16, family="serif", color=INK)

    if extra_panel:
        extra_panel(axes[-1])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(series), frameon=False,
               fontsize=14, bbox_to_anchor=(0.5, 1.0), handlelength=1.4, columnspacing=1.6)
    fig.tight_layout(rect=[0, 0.04, 1, 0.92])
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


def main():
    args = parse_args()
    sources = {
        "results": read_rows(args.csv, "quartet_file_name"),
        "wqmc": read_rows(args.wqmc_csv, "input_file", group="37"),
        "astral": read_rows(args.astral_csv, "input_file", group="37"),
    }
    plot(group_values(sources, SERIES), SERIES, args.out)


if __name__ == "__main__":
    main()
