#!/usr/bin/env python3
"""Draw the end-to-end running time of wQFM and of QUANTA (quantum annealer and
simulated annealing) for every dataset, each bar broken down into its parts.

One panel per dataset (from timing_by_taxa.csv), side by side in one row and
ordered by taxon count, each labelled by its number of taxa and with its own
linear time axis, and three bars: wQFM, QUANTA with the quantum
annealer, and QUANTA with simulated annealing. A bar's height is the
end-to-end time; its segments are the division steps (for QUANTA split into
the solver itself, exhaustive search of partitions with at most 20 taxa, and
other overhead; at the 200-taxon root the whole D-Wave hybrid solver job,
classical part included, counts as solver time) and the rest of the run:
everything outside the timed division steps, i.e. reading the quartet file,
preparing each division step (sorting the quartets, computing wQFM's initial
bipartition) and merging the subtrees (about 0.03 s in total). wQFM's division
steps are almost entirely its core FM loop (97-99.9% where the logs time it
separately). Above each bar: the end-to-end time.

Simulated-annealing times come from classical_timing_per_file.csv
(classical_timing.py), averaged over the same samples per number of taxa.
Run from the repository root:
    python3 "result_analysis/running time analysis/graph_breakdown.py" \\
        --exclude-taxa 46 144 [--palette okabe-ito] --out "result_analysis/running time analysis/figure/running_time_breakdown.pdf"
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from graph import HERE, WQFM, QUANTA, SA, INK, GRID, AXIS, BRUTE_FORCE, unit_for, fmt, sa_by_taxa

# Colour palettes: wQFM, QUANTA with the quantum annealer, QUANTA with simulated
# annealing (a lighter step of the QUANTA colour), exact search, and other
# division-step costs (hatched).
PALETTES = {
    # the palette of the other figures in this repository
    "current": dict(wqfm=WQFM, wqfm_read="#f6b896", qpu=QUANTA, sa=SA, exact=BRUTE_FORCE[1], other_qpu="#d4e4f7", other_sa="#e7f0fb"),
    # Okabe & Ito, Color Universal Design (colour-blind safe)
    "okabe-ito": dict(wqfm="#D55E00", wqfm_read="#F0B48A", qpu="#0072B2", sa="#56B4E9", exact="#7a7a7a", other_qpu="#cce3f0", other_sa="#ddf0fb"),
    # Paul Tol, "bright" qualitative scheme (colour-blind safe)
    "tol-bright": dict(wqfm="#EE6677", wqfm_read="#F7B3BB", qpu="#4477AA", sa="#66CCEE", exact="#777777", other_qpu="#d9e4ee", other_sa="#e0f5fc"),
    # Nature Publishing Group style (ggsci "npg")
    "npg": dict(wqfm="#E64B35", wqfm_read="#F3A59A", qpu="#3C5488", sa="#4DBBD5", exact="#7E6148", other_qpu="#d8dde7", other_sa="#dbf1f7"),
    # Tableau 10 / 20
    "tableau": dict(wqfm="#F28E2B", wqfm_read="#FFBE7D", qpu="#4E79A7", sa="#A0CBE8", exact="#79706E", other_qpu="#dbe4ed", other_sa="#ecf5fa"),
}
OUTSIDE_LABEL = "Rest of the run (reading quartets, merging, etc.)"


def legend_entries(c):
    """(label, fill, hatch) per segment; labels are short and plain so the legend fits in two rows."""
    return [("wQFM: core FM step", c["wqfm"], None),
            ("QUANTA: quantum computer time", c["qpu"], None),
            ("QUANTA: simulated annealing time", c["sa"], None),
            ("Exact search (partitions $\\leq$20 taxa)", c["exact"], None),
            ("QUANTA (annealer): QUBO building + D-Wave access", c["other_qpu"], HATCH_QPU),
            ("QUANTA (sim. annealing): QUBO building", c["other_sa"], HATCH_SA),
            (OUTSIDE_LABEL, "white", None)]


# One outline and hatch colour for every segment, in the bars and in the legend,
# so each legend swatch looks exactly like the segment it names.
SEGMENT_EDGE, SEGMENT_LINE = "#52514e", 0.8
# The "other division-step costs" differ between the two QUANTA runs (only the quantum
# annealer talks to D-Wave), so they get their own tint and hatch.
HATCH_QPU, HATCH_SA = "//", "\\\\"
FONT_SCALE = 1.0  # all text is multiplied by this (--large sets 1.35)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default=HERE / "result" / "timing_by_taxa.csv", help="timing_by_taxa.csv")
    parser.add_argument("--classical", default=HERE / "result" / "classical_timing_per_file.csv",
                        help="classical_timing_per_file.csv from classical_timing.py")
    parser.add_argument("--exclude-taxa", type=int, nargs="*", default=[], help="numbers of taxa to leave out")
    parser.add_argument("--palette", choices=list(PALETTES), default="current", help="colour palette")
    parser.add_argument("--large", action="store_true",
                        help="bigger panels and text, and a two-column legend (for figures with few panels)")
    parser.add_argument("--broken-axis", action="store_true",
                        help="cut the time axis so the short QUANTA bars are drawn larger")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    return parser.parse_args()


def bar(ax, x, parts, end_to_end, division, scale, short):
    """One stacked bar of height end_to_end; parts are (seconds, fill, hatch) from the
    bottom, and the rest of end_to_end is drawn white on top."""
    bottom = 0.0
    for seconds, fill, hatch in parts + [(end_to_end - sum(p[0] for p in parts), "white", None)]:
        if seconds > 0:
            ax.bar(x, seconds / scale, width=0.72, bottom=bottom, color=fill, hatch=hatch,
                   edgecolor=SEGMENT_EDGE, linewidth=SEGMENT_LINE, zorder=3)
            bottom += seconds / scale
    ax.annotate(fmt(end_to_end / scale, short),
                (x, end_to_end / scale), textcoords="offset points", xytext=(0, 3),
                ha="center", va="bottom", fontsize=9 * FONT_SCALE, color=INK, linespacing=1.15)


def style_axis(ax, f):
    ax.set_facecolor("white")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(length=0, labelsize=10 * f, labelcolor=INK)


def draw_bars(ax, row, s, c, scale, short):
    """The three bars of one dataset: wQFM, QUANTA (quantum annealer), QUANTA (simulated annealing)."""
    get = lambda key: float(row[key])
    # wQFM: core FM (its division steps); the rest of the run (mostly reading the
    # quartet file) is drawn white, as for QUANTA
    bar(ax, 0, [(get("wqfm_division_seconds"), c["wqfm"], None)],
        get("wqfm_end_to_end_seconds"), get("wqfm_division_seconds"), scale, short)
    # the hybrid solver's classical part (200-taxon root) counts as solver time
    solver = get("wq2a_qpu_access_seconds") + get("wq2a_hybrid_solver_seconds")
    bar(ax, 1, [(solver, c["qpu"], None),
                (get("wq2a_bruteforce_seconds"), c["exact"], None),
                (get("wq2a_other_overhead_seconds"), c["other_qpu"], HATCH_QPU)],
        get("wq2a_end_to_end_seconds"), get("wq2a_division_seconds"), scale, short)
    other = s["division_seconds"] - s["sampler_seconds"] - s["bruteforce_seconds"]
    bar(ax, 2, [(s["sampler_seconds"], c["sa"], None),
                (s["bruteforce_seconds"], c["exact"], None),
                (other, c["other_sa"], HATCH_SA)],
        s["end_to_end_seconds"], s["division_seconds"], scale, short)


def break_marks(top, bottom, cut_bars=(0,), bar_width=0.72):
    """The standard broken-axis marks: the y axis is drawn as a line in both parts,
    with a pair of parallel slanted strokes where it is cut (bottom of the upper
    part, top of the lower part), and the same strokes on both edges of every bar
    that crosses the cut."""
    stroke = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=13, linestyle="none",
                  color=SEGMENT_EDGE, mec=SEGMENT_EDGE, mew=1.2, clip_on=False, zorder=5)
    for ax, y in ((top, 0), (bottom, 1)):
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(SEGMENT_EDGE)
        ax.plot([0], [y], transform=ax.transAxes, **stroke)
        edges = [x + side * bar_width / 2 for x in cut_bars for side in (-1, 1)]
        ax.plot(edges, [y] * len(edges), transform=ax.get_xaxis_transform(), **stroke)
    top.spines["bottom"].set_visible(False)
    bottom.spines["top"].set_visible(False)


def draw_panel(top, ax, row, s, c, f, label_x=-0.14):
    """One dataset's three bars on ax, or, with top given, on a cut axis: the lower
    axis reaches just above the QUANTA bars and the upper one shows the top of wQFM's."""
    wqfm_end = float(row["wqfm_end_to_end_seconds"])
    quanta_ends = [float(row["wq2a_end_to_end_seconds"]), s["end_to_end_seconds"]]
    scale, unit, short = unit_for(max([wqfm_end] + quanta_ends))
    for a in (top, ax):
        if a is not None:
            style_axis(a, f)
            draw_bars(a, row, s, c, scale, short)
    if top is None:
        ax.set_ylim(0, max([wqfm_end] + quanta_ends) / scale * 1.28)
    else:
        ax.set_ylim(0, max(quanta_ends) / scale * 1.3)
        top.set_ylim(wqfm_end / scale * 0.9, wqfm_end / scale * 1.07)
        top.set_xticks([])
        top.spines["bottom"].set_visible(False)
        top.yaxis.set_major_locator(plt.MaxNLocator(2))
        break_marks(top, ax)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["wQFM", "QUANTA\n(quantum\nannealer)", "QUANTA\n(simulated\nannealing)"],
                       fontsize=10.5 * f, color=INK)
    ax.set_ylabel(f"End-to-end time ({unit})", fontsize=11 * f, color=INK)
    if top is not None:
        ax.yaxis.set_label_coords(label_x, 0.66)
    ax.set_xlabel(f"{row['taxa']} taxa", fontsize=13 * f, fontweight="bold", color=INK, labelpad=8)


def legend_handles(c):
    return [Patch(facecolor=fill, edgecolor=SEGMENT_EDGE, linewidth=SEGMENT_LINE, hatch=h, label=label)
            for label, fill, h in legend_entries(c)]


def main():
    args = parse_args()
    with open(args.summary, newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if int(r["taxa"]) not in args.exclude_taxa]
    rows.sort(key=lambda r: int(r["taxa"]))
    sa = sa_by_taxa(args.classical)
    c = PALETTES[args.palette]

    global FONT_SCALE
    FONT_SCALE = 1.35 if args.large else 1.0
    f = FONT_SCALE
    panel_w, panel_h = (6.2, 6.4) if args.large else (4.3, 5.2)
    if args.broken_axis:
        fig, grid = plt.subplots(2, len(rows), figsize=(panel_w * len(rows), panel_h),
                                 gridspec_kw={"height_ratios": [1, 3], "hspace": 0.06}, squeeze=False)
        panels = [(grid[0][i], grid[1][i]) for i in range(len(rows))]
    else:
        fig, axes = plt.subplots(1, len(rows), figsize=(panel_w * len(rows), panel_h), squeeze=False)
        panels = [(None, ax) for ax in axes[0]]

    for (top, ax), row in zip(panels, rows):
        draw_panel(top, ax, row, sa[int(row["taxa"])], c, f)

    handles = legend_handles(c)
    if args.broken_axis:
        # tight_layout cannot handle the cut axes; leave room below for the legend
        fig.set_figheight(panel_h + 2.1)
        fig.subplots_adjust(left=0.09, right=0.98, top=0.97, bottom=0.34, wspace=0.3, hspace=0.06)
    else:
        fig.tight_layout(w_pad=2.0, rect=[0, 0.27 if args.large else 0.16, 1, 1])
    fig.legend(handles=handles, loc="lower center", ncol=2 if args.large else 4, frameon=False, fontsize=11.5 * f,
               bbox_to_anchor=(0.5, 0.0), handlelength=2.0, handleheight=1.2, columnspacing=1.2)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
