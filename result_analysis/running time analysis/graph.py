#!/usr/bin/env python3
"""Draw wQFM vs wQ²A running time for every dataset from timing_summary.csv.

One panel per dataset, ordered by taxon count, each with its own linear time
axis. In every panel: end-to-end time (wQFM, wQ²A) and total division-step
time (wQFM, wQ²A split into QPU access, brute force, Leap Hybrid solver and
other overhead).
"""

import argparse
import csv
import math
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

WQFM = "#eb6834"
WQ2A = "#2a78d6"
SEGMENTS = [
    ("wq2a_qpu_access_seconds", "QPU access", "#0d3b7a", None),
    ("wq2a_bruteforce_seconds", "Brute force (n ≤ 20)", "#5aa8f0", None),
    ("wq2a_hybrid_solver_seconds", "Leap Hybrid solver (classical part)", "#a8cdf5", None),
    ("wq2a_other_overhead_seconds", "Other overhead (QUBO building, network, bookkeeping)", "#e4eefa", "//"),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="timing_summary.csv from curate_timing.py")
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


def main():
    args = parse_args()
    with open(args.summary, newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda r: int(r["taxa"]))

    cols = len(rows) if len(rows) <= 5 else math.ceil(len(rows) / 2)
    nrows = math.ceil(len(rows) / cols)
    fig, axes = plt.subplots(nrows, cols, figsize=(4.0 * cols, 4.6 * nrows))
    axes = list(axes.flat) if nrows * cols > 1 else [axes]

    for ax, row in zip(axes, rows):
        get = lambda key: float(row[key])
        largest = max(get("wqfm_end_to_end_seconds"), get("wq2a_end_to_end_seconds"),
                      get("wqfm_division_seconds"), get("wq2a_division_seconds"))
        scale, unit, short = unit_for(largest)

        ax.set_facecolor("#ebebeb")
        ax.grid(axis="y", color="white", linewidth=1.2)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0, labelsize=10)

        width = 0.8
        simple = [(0.0, get("wqfm_end_to_end_seconds"), WQFM),
                  (1.0, get("wq2a_end_to_end_seconds"), WQ2A),
                  (2.6, get("wqfm_division_seconds"), WQFM)]
        for x, value, color in simple:
            ax.bar(x, value / scale, width=width, color=color, edgecolor="black", linewidth=0.7, zorder=3)
            ax.annotate(fmt(value / scale, short), (x, value / scale), textcoords="offset points",
                        xytext=(0, 3), ha="center", va="bottom", fontsize=9)

        bottom = 0.0
        for key, _, color, hatch in SEGMENTS:
            value = get(key) / scale
            if value > 0:
                ax.bar(3.6, value, width=width, bottom=bottom, color=color, edgecolor="black",
                       linewidth=0.7, hatch=hatch, zorder=3)
                bottom += value
        ax.annotate(fmt(get("wq2a_division_seconds") / scale, short), (3.6, bottom),
                    textcoords="offset points", xytext=(0, 3), ha="center", va="bottom", fontsize=9)

        ax.set_ylim(0, largest / scale * (1.4 if row.get("note") else 1.18))
        ax.set_xticks([0.5, 3.1])
        files, paired = int(row["files"]), int(row["end_to_end_files"])
        samples = lambda n: f"{n} sample" + ("s" if n != 1 else "")
        if paired != files:
            ax.set_xticklabels([f"End-to-end\n({samples(paired)})", f"Division steps\n({samples(files)})"],
                               fontsize=10)
        else:
            ax.set_xticklabels(["End-to-end", "Division steps"], fontsize=10)
        ax.set_ylabel(f"Time ({unit})", fontsize=10)
        detail = f"avg. over {files} samples" if files > 1 else "1 sample"
        ax.set_title(f"{row['dataset']}\n({detail})", fontsize=11)
        if row.get("note"):
            ax.text(0.5, 0.97, textwrap.fill(f"* {row['note']}", 42), transform=ax.transAxes,
                    ha="center", va="top", fontsize=8.5, style="italic", color="#52514e",
                    bbox=dict(boxstyle="square,pad=0.2", facecolor="#ebebeb", edgecolor="none"))

    for ax in axes[len(rows):]:
        ax.axis("off")

    handles = [Patch(facecolor=WQFM, edgecolor="black", label="wQFM"),
               Patch(facecolor=WQ2A, edgecolor="black", label=r"wQ$^2$A (end-to-end)")]
    handles += [Patch(facecolor=color, edgecolor="black", hatch=hatch, label=f"wQ$^2$A division: {label}")
                for _, label, color, hatch in SEGMENTS]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=11,
               bbox_to_anchor=(0.5, -0.06))
    fig.suptitle(r"Running time of wQFM and wQ$^2$A across datasets (ordered by number of taxa)",
                 fontsize=15, family="serif", y=1.01)

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
