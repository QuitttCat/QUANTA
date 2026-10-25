#!/usr/bin/env python3
"""Draw running time against number of taxa from timing_summary.csv.

Panel (a): end-to-end time. Panel (b): total division-step time, with wQ²A
shown as wall clock and as solve time only (QPU access + brute force + Leap
Hybrid solver). Each dataset is a point; lines join the mean at each taxon count.
Both axes are linear; time is in minutes.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter

WQFM = "#eb6834"
WQ2A = "#2a78d6"
WQ2A_SOLVE = "#0d3b7a"
ZERO_GAP_MM = 5


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="timing_summary.csv from curate_timing.py")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def human(seconds):
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} h"
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f} s"


def plot_series(ax, rows, value, label, color, marker, linestyle="-"):
    by_taxa = defaultdict(list)
    for row in rows:
        by_taxa[int(row["taxa"])].append(value(row))
    xs = sorted(by_taxa)
    ax.scatter([int(r["taxa"]) for r in rows], [value(r) / 60 for r in rows], color=color,
               marker=marker, s=60, edgecolor="white", linewidth=1.2, zorder=4)
    means = [sum(by_taxa[x]) / len(by_taxa[x]) for x in xs]
    ax.plot(xs, [m / 60 for m in means], color=color, linewidth=2.2, linestyle=linestyle,
            label=label, zorder=3)
    ax.annotate(human(means[-1]), (xs[-1], means[-1] / 60), textcoords="offset points",
                xytext=(8, 0), va="center", fontsize=10, color=color)


def style(ax, taxa):
    ax.set_facecolor("#ebebeb")
    ax.grid(color="white", linewidth=1.1)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelsize=11)
    # Lift zero a fixed distance above the bottom so points at ~0 stay visible.
    top = ax.get_ylim()[1]
    height_mm = ax.get_position().height * ax.figure.get_figheight() * 25.4
    gap = ZERO_GAP_MM / height_mm
    ax.set_ylim(-top * gap / (1 - gap), top)
    # 46 and 48 are too close to both carry labels; 46 keeps an unlabeled tick.
    ax.set_xticks([t for t in taxa if t != 46])
    ax.set_xticks([t for t in taxa if t == 46], minor=True)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("Number of taxa", fontsize=12, fontweight="bold")
    ax.set_xlim(min(taxa) - 10, max(taxa) + 30)


def main():
    args = parse_args()
    with open(args.summary, newline="") as handle:
        rows = list(csv.DictReader(handle))
    f = lambda key: (lambda r: float(r[key]))
    taxa = sorted({int(r["taxa"]) for r in rows})

    fig, (ax_e2e, ax_div) = plt.subplots(1, 2, figsize=(15, 5.8))

    plot_series(ax_e2e, rows, f("wqfm_end_to_end_seconds"), "wQFM", WQFM, "o")
    plot_series(ax_e2e, rows, f("wq2a_end_to_end_seconds"), r"wQ$^2$A", WQ2A, "s")
    ax_e2e.set_ylabel("End-to-end time (minutes)", fontsize=12, fontweight="bold")

    solve = lambda r: (float(r["wq2a_qpu_access_seconds"]) + float(r["wq2a_bruteforce_seconds"])
                       + float(r["wq2a_hybrid_solver_seconds"]))
    plot_series(ax_div, rows, f("wqfm_division_seconds"), "wQFM", WQFM, "o")
    plot_series(ax_div, rows, f("wq2a_division_seconds"), r"wQ$^2$A (wall clock)", WQ2A, "s")
    plot_series(ax_div, rows, solve, r"wQ$^2$A (solve only: QPU access + brute force + Leap Hybrid)",
                WQ2A_SOLVE, "^", linestyle="--")
    ax_div.set_ylabel("Total division-step time (minutes)", fontsize=12, fontweight="bold")

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    for ax, letter, caption in [(ax_e2e, "(a)", "End-to-end running time."),
                                (ax_div, "(b)", "Sum of division-step times.")]:
        style(ax, taxa)
        ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="white", fontsize=10)
        ax.text(-0.02, 1.03, letter, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=20, fontweight="bold")
        ax.text(0.5, -0.17, caption, transform=ax.transAxes, ha="center", va="top",
                fontsize=14, family="serif")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
