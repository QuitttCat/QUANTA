#!/usr/bin/env python3
"""Average RF distance on the 11- and 15-taxon datasets in one figure, one row
per dataset with one shared legend.

(a), (b) 11 taxa, 5-100 estimated and true gene trees (20 replicates).
(c), (d) 15 taxa, 100 and 1000 genes (10 replicates).
Bars are means over replicates with standard-error bars. The data and colors
come from "11 Taxa/graph.py" and "15 Taxa/graph.py"; those figures are unchanged.

Writes "11 Taxa/figure/results_11_15_taxa.pdf". Run from the repository root:
    python3 result_analysis/graph_11_15_taxa.py
"""

import argparse
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def load_graph(folder):
    """Load <folder>/graph.py; both scripts are named graph, so not by a plain import."""
    spec = importlib.util.spec_from_file_location(f"graph_{folder.split()[0]}", HERE / folder / "graph.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def draw(ax, module, groups, keys, ticks, letter, caption):
    series = module.SERIES
    width = 0.2
    y_top = 0.0
    ax.set_facecolor("white")
    ax.grid(axis="y", color=module.GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(module.AXIS)
    for i, (_, _, label, color) in enumerate(series):
        offset = (i - (len(series) - 1) / 2) * width
        stats = [module.mean_se(groups[key][label]) for key in keys]
        xs = [p + offset for p in range(len(keys))]
        ax.bar(xs, [m for m, _ in stats], width=width, color=color, edgecolor="white", linewidth=1.2, label=label, zorder=3)
        ax.errorbar(xs, [m for m, _ in stats], yerr=[e for _, e in stats], fmt="none", ecolor=module.MUTED,
                    elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
        y_top = max(y_top, max(m + e for m, e in stats))
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(ticks, fontsize=14, color=module.INK)
    ax.tick_params(axis="both", length=0, labelsize=14, labelcolor=module.INK)
    ax.set_ylabel("Avg. Robinson–Foulds distance", fontsize=14, fontweight="bold", color=module.INK)
    # the panel title sits beside its letter, above the panel, to save vertical space
    ax.text(-0.06, 1.03, letter, transform=ax.transAxes, ha="left", va="baseline", fontsize=20, fontweight="bold", color=module.INK)
    ax.text(0.03, 1.03, caption, transform=ax.transAxes, ha="left", va="baseline", fontsize=16, family="serif", color=module.INK)
    return y_top


def args_for(module, csv_path, out):
    return argparse.Namespace(csv=csv_path, wqmc_csv=module.REPO / "baselines" / "results" / "wqmc_results.csv",
                              astral_csv=module.REPO / "baselines" / "results" / "astral_results.csv", out=out)


def main():
    out = HERE / "11 Taxa" / "figure" / "results_11_15_taxa.pdf"
    g11 = load_graph("11 Taxa")
    g15 = load_graph("15 Taxa")
    groups11 = g11.load(args_for(g11, HERE / "11 Taxa" / "result" / "results_11_taxa.csv", out))
    groups15 = g15.load(args_for(g15, HERE / "15 Taxa" / "result" / "results_15_taxa.csv", out))

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2))
    genes = g11.GENE_COUNTS
    tops = [
        draw(axes[0, 0], g11, groups11, [("estimated", g) for g in genes], [f"{g}g" for g in genes], "(a)",
             "11 taxa, estimated gene trees"),
        draw(axes[0, 1], g11, groups11, [("simulated", g) for g in genes], [f"{g}g" for g in genes], "(b)",
             "11 taxa, true gene trees"),
    ]
    for ax in axes[0]:
        ax.set_ylim(0, max(tops) * 1.1)
    tops = [
        draw(axes[1, col], g15, groups15, [(n, s) for s in g15.SOURCES], [s.replace("bp", " bp") for s in g15.SOURCES], letter,
             f"15 taxa, {n} genes")
        for col, (n, letter) in enumerate(((100, "(c)"), (1000, "(d)")))
    ]
    for ax in axes[1]:
        ax.set_ylim(0, max(tops) * 1.1)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(handles), frameon=False, fontsize=14,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.4, columnspacing=1.6)
    fig.tight_layout(rect=[0, 0, 1, 0.96], h_pad=1.5)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")
    return fig


if __name__ == "__main__":
    main()
