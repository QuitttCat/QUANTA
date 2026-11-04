#!/usr/bin/env python3
"""Average RF distance on the 48- and 101-taxon datasets in one figure: the two
panels of "48 Taxa/graph.py" (first 10 available replicates) and the 101-taxon
result (19 replicates) as a third panel, with one shared legend.

Writes "48 Taxa/figure/results_48_101_taxa.pdf". Run from the repository root:
    QWQFM/.venv/bin/python result_analysis/graph_48_101_taxa.py
"""

import importlib.util, math
from pathlib import Path
import sys
R = Path(__file__).resolve().parent
OUT = sys.argv[1] if len(sys.argv) > 1 else R / "48 Taxa" / "figure" / "results_48_101_taxa.pdf"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
g48 = load(R / "48 Taxa" / "graph.py", "g48")
BASE = g48.REPO / "baselines" / "results"
s48 = {"results": g48.read_rows(R / "48 Taxa" / "result" / "results_48_taxa_z12_qpu_plus_bruteforce_n>20_10reps.csv", "quartet_file_name"),
       "wqmc": g48.read_rows(BASE / "wqmc_results.csv", "input_file", group="48"),
       "astral": g48.read_rows(BASE / "astral_results.csv", "input_file", group="48")}
s101 = {"results": g48.read_rows(R / "101 Taxa" / "result" / "results_101_taxa_qpu_plus_bruteforce.csv", "quartet_file_name"),
        "wqmc": g48.read_rows(BASE / "wqmc_results.csv", "input_file", group="101"),
        "astral": g48.read_rows(BASE / "astral_results.csv", "input_file", group="101")}
names = sorted(s101["results"])
def panel(ax):
    ax.set_facecolor("white"); ax.grid(axis="y", color=g48.GRID, linewidth=0.8); ax.set_axisbelow(True)
    for side, spine in ax.spines.items(): spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(g48.AXIS)
    width = 0.8 / len(g48.SERIES); top = 0
    for i, (source, column, label, color) in enumerate(g48.SERIES):
        vals = [float(s101[source][n][column]) for n in names]
        m, e = g48.mean_se(vals); x = (i - (len(g48.SERIES) - 1) / 2) * width
        print(f"101 taxa {label}: {m:.4f} ± {e:.4f} (n={len(vals)})")
        ax.bar(x, m, width=width, color=color, edgecolor="white", linewidth=1.2, zorder=3)
        ax.errorbar(x, m, yerr=e, fmt="none", ecolor=g48.MUTED, elinewidth=1.0, capsize=3, capthick=1.0, zorder=4)
        top = max(top, m + e)
    ax.set_ylim(0, top * 1.12); ax.set_xticks([0]); ax.set_xticklabels(["1000g"], fontsize=12, color=g48.INK)
    ax.set_xlim(-0.5, 0.5)
    ax.set_xlabel("Number of genes", fontsize=14, fontweight="bold", color=g48.INK)
    ax.set_ylabel("Avg. Robinson–Foulds distance", fontsize=14, fontweight="bold", color=g48.INK)
    ax.tick_params(axis="both", length=0, labelsize=13, labelcolor=g48.INK)
    ax.text(0.0, 1.04, "(c)", transform=ax.transAxes, ha="left", va="bottom", fontsize=20, fontweight="bold", color=g48.INK)
    ax.text(0.5, g48.CAPTION_Y_SHORT, "True gene trees (101 taxa)", transform=ax.transAxes, ha="center", va="top", fontsize=16, family="serif", color=g48.INK)
g48.PANEL_WIDTHS[:] = [3, 5]
g48.PANELS[0] = g48.PANELS[0][:2] + ("Varying ILS (48 taxa, 1000 genes, 500 bp)",) + g48.PANELS[0][3:]
g48.PANELS[1] = g48.PANELS[1][:2] + ("Varying numbers of genes (48 taxa, 1X ILS, 500 bp)",) + g48.PANELS[1][3:]
g48.plot(g48.group_values(s48, g48.SERIES), g48.SERIES, OUT, extra_panel=panel, replicate_labels=False, extra_width=1, extra_fig_width=2.4, equal_bars=True)
