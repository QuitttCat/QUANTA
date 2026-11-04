#!/usr/bin/env python3
"""Running time of QUANTA and wQFM in one figure, without the 144-taxon dataset.

(a) Solving time of each bipartition against partition size (the "solving"
    panel of running_time_quanta.py).
(b) End-to-end running time by number of taxa (its "end_to_end" panel).
(c), (d) End-to-end time of wQFM, QUANTA (quantum annealer) and QUANTA
    (simulated annealing) on the 101- and 200-taxon datasets, each bar broken
    down into its parts on a cut time axis (graph_breakdown.py).

Writes figure/running_time_combined.pdf (2 x 2 panels) or, with --row,
figure/running_time_combined_row.pdf (the four panels side by side). Run from
the repository root:
    python3 "result_analysis/running time analysis/running_time_combined.py" [--row]
"""

import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import graph_breakdown as breakdown
import running_time_quanta as rtq

EXCLUDED = "144 taxa (insect)"
BAR_TAXA = [101, 200]
BAR_FONT_SCALE = 1.25  # text of panels (c) and (d), to match panels (a) and (b)
ROW_TEXT_SCALE = 1.3  # extra text size for the 1 x 4 layout


def letter(ax, text):
    ax.text(0.0, 1.03, text, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=20, fontweight="bold", color=rtq.INK)


def main(row=None):
    if row is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--row", action="store_true", help="the four panels side by side (1 x 4)")
        row = parser.parse_args().row
    rtq.EXCLUDED.add(EXCLUDED)
    rtq.SHOW_COUNTS = False
    breakdown.FONT_SCALE = BAR_FONT_SCALE

    if row:
        fig = plt.figure(figsize=(24, 6.8))
        outer = GridSpec(1, 4, figure=fig, wspace=0.34, left=0.05, right=0.99, top=0.91, bottom=0.31)
        cells = [outer[0, 0], outer[0, 1], outer[0, 2], outer[0, 3]]
    else:
        fig = plt.figure(figsize=(16, 13.4))
        outer = GridSpec(2, 2, figure=fig, height_ratios=[1, 1.15], hspace=0.24, wspace=0.26,
                         left=0.07, right=0.98, top=0.97, bottom=0.14)
        cells = [outer[0, 0], outer[0, 1], outer[1, 0], outer[1, 1]]

    # (a), (b): line panels
    line_axes = []
    for cell, (name, draw, caption, linear), label in zip(
            cells[:2],
            [p for p in rtq.PANELS if p[0] in ("solving", "end_to_end")], ("(a)", "(b)")):
        ax = fig.add_subplot(cell)
        line_axes.append(ax)
        draw(ax)
        rtq.finish(ax, label, "", linear)  # no caption under the panel; the figure caption describes it

    # (c), (d): breakdown bars on a cut time axis
    with open(breakdown.HERE / "result" / "timing_by_taxa.csv", newline="") as handle:
        rows = {int(r["taxa"]): r for r in csv.DictReader(handle)}
    sa = breakdown.sa_by_taxa(breakdown.HERE / "result" / "classical_timing_per_file.csv")
    c = breakdown.PALETTES["current"]
    for col, (taxa, label) in enumerate(zip(BAR_TAXA, ("(c)", "(d)"))):
        inner = cells[2 + col].subgridspec(2, 1, height_ratios=[1, 3], hspace=0.06)
        top, ax = fig.add_subplot(inner[0]), fig.add_subplot(inner[1])
        breakdown.draw_panel(top, ax, rows[taxa], sa[taxa], c, BAR_FONT_SCALE, label_x=-0.11)
        letter(top, label)

    # legend entries side by side (4 columns, 2 rows) to save vertical space
    fig.legend(handles=breakdown.legend_handles(c), loc="lower center", ncol=4, frameon=False,
               fontsize=11.5, bbox_to_anchor=(0.5, 0.0), handlelength=1.8, handleheight=1.1,
               columnspacing=1.0, handletextpad=0.5)
    if row:
        # one row is printed much smaller than the 2 x 2 layout: enlarge the text,
        # except the legends inside (a) and (b), which would cover the data; and
        # thin out the x ticks that would collide
        keep = {t for ax in line_axes for t in ax.get_legend().get_texts()}
        for text in fig.findobj(matplotlib.text.Text):
            if text not in keep:
                text.set_fontsize(text.get_fontsize() * ROW_TEXT_SCALE)
        line_axes[0].set_xticks([25, 50, 100, 150, 200])
        line_axes[1].set_xticks([37, 101, 200])
        line_axes[1].set_xticks([46, 48], minor=True)
    out = rtq.HERE / "figure" / ("running_time_combined_row.pdf" if row else "running_time_combined.pdf")
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")
    return fig


if __name__ == "__main__":
    main()
