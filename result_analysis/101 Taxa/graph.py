#!/usr/bin/env python3
"""Plot wQFM vs wQ²A on the 101-taxon dataset (true gene trees).

Panel (a): average RF distance.
Panel (b): end-to-end running time.
Panel (c): total time of the division (bipartition) steps, log scale; wQ²A is
shown both as wall clock and as compute only (QPU access + brute force).
Every bar is the mean over replicates with standard-error bars.
"""

import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WQFM = "#eb6834"
WQ2A = "#2a78d6"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-csv", required=True, help="results CSV from run_101_taxa_benchmark.sh")
    parser.add_argument("--timing-csv", required=True, help="timing CSV from collect_timing.py")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def read(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def mean_se(values):
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def style(ax):
    ax.set_facecolor("#ebebeb")
    ax.grid(axis="y", color="white", linewidth=1.2, which="both")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelsize=11)


def bars(ax, specs, fmt):
    """specs: (label, values, color, hatch). Draws mean ± SE bars with value labels."""
    width = 0.6
    tops = []
    for i, (label, values, color, hatch) in enumerate(specs):
        mean, se = mean_se(values)
        ax.bar([i], [mean], width=width, color=color, edgecolor="black", linewidth=0.8,
               hatch=hatch, label=label, zorder=3)
        ax.errorbar([i], [mean], yerr=[se], fmt="none", ecolor="black",
                    elinewidth=1.1, capsize=5, capthick=1.1, zorder=4)
        ax.annotate(fmt(mean), (i, mean + se), textcoords="offset points", xytext=(0, 5),
                    ha="center", va="bottom", fontsize=11)
        tops.append(mean + se)
    ax.set_xticks(range(len(specs)))
    ax.set_xticklabels([label for label, *_ in specs], fontsize=11)
    ax.set_xlim(-0.6, len(specs) - 0.4)
    return max(tops)


def main():
    args = parse_args()
    results = read(args.results_csv)
    timing = read(args.timing_csv)
    n = len(timing)

    fig, (ax_rf, ax_total, ax_div) = plt.subplots(
        1, 3, figsize=(17, 5.8), gridspec_kw={"width_ratios": [1, 1, 1.35]}
    )
    for ax in (ax_rf, ax_total, ax_div):
        style(ax)

    top = bars(ax_rf, [
        ("wQFM", [float(r["rf_wqfm_wrt_base"]) for r in results], WQFM, None),
        (r"wQ$^2$A", [float(r["rf_quantum_wrt_base"]) for r in results], WQ2A, None),
    ], lambda v: f"{v:.4f}")
    ax_rf.set_ylim(0, top * 1.3)
    ax_rf.set_ylabel("Avg. Robinson–Foulds distance", fontsize=11, fontweight="bold")

    top = bars(ax_total, [
        ("wQFM", [float(r["wqfm_end_to_end_seconds"]) / 60 for r in timing], WQFM, None),
        (r"wQ$^2$A", [float(r["wq2a_end_to_end_seconds"]) / 60 for r in timing], WQ2A, None),
    ], lambda v: f"{v:.1f} min")
    ax_total.set_ylim(0, top * 1.2)
    ax_total.set_ylabel("Avg. end-to-end time (minutes)", fontsize=11, fontweight="bold")

    bars(ax_div, [
        ("wQFM", [float(r["wqfm_division_seconds"]) for r in timing], WQFM, None),
        (r"wQ$^2$A" "\n(wall clock)", [float(r["wq2a_division_seconds"]) for r in timing], WQ2A, None),
        (r"wQ$^2$A" "\n(QPU access +\nbrute force)",
         [float(r["wq2a_qpu_access_seconds"]) + float(r["wq2a_bruteforce_seconds"]) for r in timing],
         "#9ec2ee", "//"),
    ], lambda v: f"{v:.1f} s")
    ax_div.set_yscale("log")
    ax_div.set_ylim(1, 1e4)
    ax_div.set_ylabel("Avg. total division-step time (s, log scale)", fontsize=11, fontweight="bold")

    for ax, letter, caption in [
        (ax_rf, "(a)", "Accuracy."),
        (ax_total, "(b)", "End-to-end running time."),
        (ax_div, "(c)", "Sum of division-step times."),
    ]:
        ax.text(-0.02, 1.04, letter, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=20, fontweight="bold")
        ax.text(0.5, -0.2, caption, transform=ax.transAxes, ha="center", va="top",
                fontsize=14, family="serif")

    fig.suptitle(f"101 taxa, true gene trees — mean ± SE over {n} replicates",
                 fontsize=14, family="serif", y=1.04)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
