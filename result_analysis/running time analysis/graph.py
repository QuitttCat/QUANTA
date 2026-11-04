#!/usr/bin/env python3
"""Draw the running time of wQFM and of QUANTA, with the quantum annealer and
with simulated annealing, for every dataset.

One panel per dataset (from timing_summary.csv or timing_by_taxa.csv), ordered
by taxon count, each with its own linear time axis. In every panel: end-to-end
time and total division-step time of wQFM, QUANTA (quantum annealer) and
QUANTA (simulated annealing). Both QUANTA division-step bars are split into
the solver itself (QPU access or simulated annealing), exhaustive search of
partitions with at most 20 taxa, the classical part of D-Wave's hybrid solver
(200 taxa only), and other overhead (building QUBOs, network, bookkeeping).
Simulated-annealing times come from classical_timing_per_file.csv
(classical_timing.py), averaged over the same samples per number of taxa.
"""

import argparse
import csv
import math
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
WQFM, QUANTA, SA = "#eb6834", "#2a78d6", "#86b6ef"
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
# Parts of a QUANTA division-step bar shared by both solvers (neutral, so the
# solver segment keeps the method colour).
BRUTE_FORCE = ("Exhaustive search (partitions with $\\leq$ 20 taxa)", "#898781", None)
HYBRID = ("D-Wave hybrid solver, classical part (200 taxa)", "#c3c2b7", None)
OVERHEAD = ("Other overhead (building QUBOs, network, bookkeeping)", "#f0efec", "//")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="timing_by_taxa.csv or timing_summary.csv")
    parser.add_argument("--classical", default=HERE / "result" / "classical_timing_per_file.csv",
                        help="classical_timing_per_file.csv from classical_timing.py")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def unit_for(seconds):
    if seconds >= 3 * 3600:
        return 3600.0, "hours", "h"
    if seconds >= 180:
        return 60.0, "minutes", "min"
    return 1.0, "seconds", "s"


def fmt(value, short):
    return f"{value:.1f} {short}" if value < 100 else f"{value:.0f} {short}"


def sa_by_taxa(path):
    """Mean simulated-annealing timings per number of taxa."""
    groups = defaultdict(list)
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            if row["solver"] == "simulated_annealing":
                groups[int(row["taxa"])].append(row)
    keys = ("end_to_end_seconds", "division_seconds", "sampler_seconds", "bruteforce_seconds")
    return {taxa: {k: sum(float(r[k]) for r in rows) / len(rows) for k in keys}
            for taxa, rows in groups.items()}


def stacked(ax, x, width, parts, total, scale, short, edge):
    bottom = 0.0
    for value, color, hatch in parts:
        if value > 0:
            ax.bar(x, value / scale, width=width, bottom=bottom, color=color, hatch=hatch,
                   edgecolor=edge, linewidth=1.2, zorder=3)
            bottom += value / scale
    ax.annotate(fmt(total / scale, short), (x, total / scale), textcoords="offset points",
                xytext=(0, 3), ha="center", va="bottom", fontsize=8.5, color=INK)


def main():
    args = parse_args()
    with open(args.summary, newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda r: int(r["taxa"]))
    sa = sa_by_taxa(args.classical)

    cols = len(rows) if len(rows) <= 5 else math.ceil(len(rows) / 2)
    nrows = math.ceil(len(rows) / cols)
    fig, axes = plt.subplots(nrows, cols, figsize=(4.8 * cols, 4.8 * nrows))
    axes = list(axes.flat) if nrows * cols > 1 else [axes]
    width = 0.85

    for ax, row in zip(axes, rows):
        get = lambda key: float(row[key])
        s = sa.get(int(row["taxa"]))
        candidates = [get("wqfm_end_to_end_seconds"), get("wq2a_end_to_end_seconds"),
                      get("wqfm_division_seconds"), get("wq2a_division_seconds")]
        if s:
            candidates += [s["end_to_end_seconds"], s["division_seconds"]]
        largest = max(candidates)
        scale, unit, short = unit_for(largest)

        ax.set_facecolor("white")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side, spine in ax.spines.items():
            spine.set_visible(side == "bottom")
        ax.spines["bottom"].set_color(AXIS)
        ax.tick_params(length=0, labelsize=10, labelcolor=INK)

        # End-to-end: wQFM, QUANTA (quantum annealer), QUANTA (simulated annealing).
        ends = [(0.0, get("wqfm_end_to_end_seconds"), WQFM), (1.0, get("wq2a_end_to_end_seconds"), QUANTA)]
        if s:
            ends.append((2.0, s["end_to_end_seconds"], SA))
        for x, value, color in ends:
            stacked(ax, x, width, [(value, color, None)], value, scale, short, "white")

        # Division steps.
        stacked(ax, 3.5, width, [(get("wqfm_division_seconds"), WQFM, None)],
                get("wqfm_division_seconds"), scale, short, "white")
        stacked(ax, 4.5, width,
                [(get("wq2a_qpu_access_seconds"), QUANTA, None),
                 (get("wq2a_bruteforce_seconds"), BRUTE_FORCE[1], BRUTE_FORCE[2]),
                 (get("wq2a_hybrid_solver_seconds"), HYBRID[1], HYBRID[2]),
                 (get("wq2a_other_overhead_seconds"), OVERHEAD[1], OVERHEAD[2])],
                get("wq2a_division_seconds"), scale, short, QUANTA)
        if s:
            other = s["division_seconds"] - s["sampler_seconds"] - s["bruteforce_seconds"]
            stacked(ax, 5.5, width,
                    [(s["sampler_seconds"], SA, None),
                     (s["bruteforce_seconds"], BRUTE_FORCE[1], BRUTE_FORCE[2]),
                     (other, OVERHEAD[1], OVERHEAD[2])],
                    s["division_seconds"], scale, short, SA)

        ax.set_ylim(0, largest / scale * (1.4 if row.get("note") else 1.18))
        ax.set_xticks([1.0, 4.5])
        ax.set_xticklabels(["End-to-end", "Division steps"], fontsize=11, color=INK)
        ax.set_ylabel(f"Time ({unit})", fontsize=11, color=INK)
        files = int(row["files"])
        detail = f"avg. over {files} samples" if files > 1 else "1 sample"
        ax.set_title(f"{row['dataset']}\n({detail})", fontsize=11.5, color=INK)
        if row.get("note"):
            ax.text(0.5, 0.97, textwrap.fill(f"* {row['note']}", 42), transform=ax.transAxes,
                    ha="center", va="top", fontsize=8.5, style="italic", color=MUTED)

    for ax in axes[len(rows):]:
        ax.axis("off")

    handles = [Patch(facecolor=WQFM, label="wQFM"),
               Patch(facecolor=QUANTA, label="QUANTA, quantum annealer (division: QPU time)"),
               Patch(facecolor=SA, label="QUANTA, simulated annealing (division: solver time)")]
    handles += [Patch(facecolor=color, edgecolor=MUTED, hatch=hatch, label=f"QUANTA division: {label}")
                for label, color, hatch in (BRUTE_FORCE, HYBRID, OVERHEAD)]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=11,
               bbox_to_anchor=(0.5, -0.09))

    fig.tight_layout(h_pad=2.5)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
