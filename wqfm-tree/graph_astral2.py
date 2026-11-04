#!/usr/bin/env python3
"""Average RF distance on the ASTRAL-II 500- and 1000-taxon datasets (1000
estimated gene trees, polytomies resolved for QUANTA-Tree and wQFM-TREE), as
grouped bars in one graph, in the style of the 11- and 15-taxon figure. The RF
bars labelled ASTRAL are from the published ASTRAL-II trees.

QUANTA's trees come from runs/a2r (astral2.py run --resolved); the other trees
are the ones published in official/results/Astral_2_datasets. RF is recomputed
from the trees. At 1000 taxa, replicates 04 and 11 are left out and replaced by
13 and 14, because QUANTA failed on them (see results/astral2_resolved_runs.csv).

Also draws the running times: QUANTA-Tree as measured here, the others as
published, on a different computer.

Writes results/astral2_500_1000_rf.pdf and results/astral2_500_1000_time.pdf.
Usage: python graph_astral2.py [--out path] [--time-out path]
       python graph_astral2.py --merged-out results/astral2_500_1000_rf_time.pdf
"""

import argparse
import csv
import math
from pathlib import Path
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import compare

HERE = Path(__file__).resolve().parent
OFFICIAL = HERE / "official" / "results" / "Astral_2_datasets"
REPS = {500: [f"{i:02d}" for i in range(1, 11)],
        1000: ["01", "02", "03", "05", "07", "09", "10", "12", "13", "14"]}
SERIES = [("QUANTA-Tree (simulated annealing, ours)", None, "#2a78d6"),
          ("wQFM-TREE", "ewqfm-with-resolved-gene-trees-tree.txt", "#eb6834"),
          ("ASTRAL", "astral2-tree.txt", "#eda100")]
# mean and SD in seconds, 1000 genes (wQFM-TREE supplement, section 4.5; 10 replicates at 500 taxa, 5 at 1000)
PUBLISHED_TIME = {"wQFM-TREE": {500: (2451.9, 19.2), 1000: (11680.4, 69.9)},
                  "ASTRAL": {500: (1509.4, 34.4), 1000: (7336.9, 71.4)}}
GROUP_SPACING = 0.6  # distance between the 500- and 1000-taxon bar groups (bars span 0.4)
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def rf_values(taxa, tree_file):
    model = f"model.{taxa}.2000000.0.000001"
    values = []
    for rep in REPS[taxa]:
        species = OFFICIAL / "true-species-trees" / model / rep / "sp-cleaned"
        tree = HERE / "runs" / "a2r" / f"m{taxa}" / rep / "g1000" / "quanta.tre" if tree_file is None \
            else OFFICIAL / "outputs" / model / rep / tree_file
        values.append(compare.rf(species, tree))
    return values


def style(ax):
    ax.set_facecolor("white")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(AXIS)
    ax.set_xlim(-0.3, (len(REPS) - 1) * GROUP_SPACING + 0.3)  # little empty space around the bar groups
    ax.set_xticks([g * GROUP_SPACING for g in range(len(REPS))])
    ax.set_xticklabels([f"{taxa} taxa\n(1000 genes)" for taxa in REPS], fontsize=13, color=INK)
    ax.tick_params(axis="both", length=0, labelsize=14, labelcolor=INK)


def finish(fig, ax, out):
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", ncol=len(SERIES), frameon=False, fontsize=11.5,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.2, handletextpad=0.5, columnspacing=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


def rf_panel(ax):
    style(ax)
    width = 0.4 / len(SERIES)
    for i, (label, tree_file, color) in enumerate(SERIES):
        offset = (i - (len(SERIES) - 1) / 2) * width
        stats = []
        for taxa in REPS:
            values = rf_values(taxa, tree_file)
            stats.append((mean(values), stdev(values) / math.sqrt(len(values))))
            print(f"{taxa} taxa, {label}: mean RF {stats[-1][0]:.4f}, SE {stats[-1][1]:.4f}")
        xs = [g * GROUP_SPACING + offset for g in range(len(REPS))]
        ax.bar(xs, [m for m, _ in stats], width=width, color=color, edgecolor="white", linewidth=1.2, label=label, zorder=3)
        ax.errorbar(xs, [m for m, _ in stats], yerr=[e for _, e in stats], fmt="none", ecolor=MUTED,
                    elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
    ax.set_ylabel("Avg. RF distance", fontsize=14, fontweight="bold", color=INK)


def draw_rf(out):
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    rf_panel(ax)
    finish(fig, ax, out)


def time_panel(ax):
    """QUANTA-Tree as measured here; the others as published (wQFM-TREE supplement, section 4.5)."""
    with (HERE / "results" / "astral2_resolved_runs.csv").open() as handle:
        wall = {(int(r["taxa"]), r["rep"]): float(r["wall_s"]) for r in csv.DictReader(handle)}
    style(ax)
    width = 0.4 / len(SERIES)
    for i, (label, _, color) in enumerate(SERIES):
        offset = (i - (len(SERIES) - 1) / 2) * width
        stats = []
        for taxa in REPS:
            if i == 0:
                values = [wall[(taxa, rep)] for rep in REPS[taxa]]
                stats.append((mean(values), stdev(values)))
            else:
                stats.append(PUBLISHED_TIME[label][taxa])
            print(f"{taxa} taxa, {label}: {stats[-1][0]:.1f} s, SD {stats[-1][1]:.1f} s")
        xs = [g * GROUP_SPACING + offset for g in range(len(REPS))]
        minutes = [m / 60 for m, _ in stats]
        ax.bar(xs, minutes, width=width, color=color, edgecolor="white", linewidth=1.2, label=label, zorder=3)
        ax.errorbar(xs, minutes, yerr=[e / 60 for _, e in stats], fmt="none", ecolor=MUTED,
                    elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
        for x, value in zip(xs, minutes):
            ax.annotate(f"{value:.1f}" if value < 100 else f"{value:.0f}", (x, value), textcoords="offset points",
                        xytext=(0, 5), ha="center", fontsize=11, color=INK)
    ax.set_ylabel("Running time (minutes)", fontsize=14, fontweight="bold", color=INK)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.08)


def draw_time(out):
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    time_panel(ax)
    finish(fig, ax, out)


def draw_merged(out):
    """RF and running time side by side, with one legend."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.5, 3.9))
    rf_panel(left)
    time_panel(right)
    for ax, letter in ((left, "(a)"), (right, "(b)")):
        ax.text(0.0, 1.03, letter, transform=ax.transAxes, ha="left", va="bottom", fontsize=20, fontweight="bold", color=INK)
    handles, labels = right.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(handles), frameon=False, fontsize=13,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.2, handletextpad=0.5, columnspacing=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.91], w_pad=1.5)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="RF figure path")
    parser.add_argument("--time-out", help="timing figure path")
    parser.add_argument("--merged-out", help="draw only the merged RF and timing figure, to this path")
    args = parser.parse_args()
    if args.merged_out:
        draw_merged(args.merged_out)
        return
    if not args.time_out:
        draw_rf(args.out or HERE / "results" / "astral2_500_1000_rf.pdf")
    if args.time_out or not args.out:
        draw_time(args.time_out or HERE / "results" / "astral2_500_1000_time.pdf")


if __name__ == "__main__":
    main()
