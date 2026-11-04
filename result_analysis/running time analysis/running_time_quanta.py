#!/usr/bin/env python3
"""Running time of QUANTA and wQFM.

(a) Solving time of each bipartition with more than 20 taxa, across all
    simulated and biological runs (partition_solving_time.py): wQFM's FM
    heuristic against QUANTA's quantum annealer (QPU access time only), one
    point per partition against its size, log scale, with the median per
    10-taxon bin. The 200-taxon root partition ran on D-Wave's Leap Hybrid
    solver; its point is the QPU access time of that job.
(b) Total time of the division steps (wall clock), by number of taxa.
(c) End-to-end running time.
Panels (b) and (c) use timing_summary.csv (curate_timing.py): each dataset is
a point and lines join the means at each number of taxa.

Writes figure/running_time_quanta.pdf (all three panels) and one PDF per panel.
Run from the repository root:
    python3 "result_analysis/running time analysis/running_time_quanta.py"

--exclude-dataset leaves a dataset out of every panel, and --panels draws only
the panels named, side by side, into --out. For example, panels (a) and (c)
without the 144-taxon dataset:
    python3 "result_analysis/running time analysis/running_time_quanta.py" \\
        --exclude-dataset "144 taxa (insect)" --panels solving end_to_end \\
        --out running_time_comparison.pdf
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter

HERE = Path(__file__).resolve().parent
QUANTA, WQFM = "#2a78d6", "#eb6834"
# QUANTA with simulated annealing: the same blue at a lighter step, as in the
# solver-comparison figures (classical_timing.py).
CLASSICAL = [("simulated_annealing", "QUANTA (simulated annealing)", "#86b6ef", "^")]
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
ZERO_GAP_MM = 5


EXCLUDED = set()  # datasets left out of every panel (--exclude-dataset)
SHOW_COUNTS = True  # number of partitions in the legend of panel (a) (--no-partition-counts)
REPLICATE_POINTS = False  # one point per replicate in the time-by-taxa panels (--replicate-points)
# horizontal offsets (taxa) of the replicate points, so the three methods do not hide each other
REPLICATE_OFFSET = {WQFM: -4.0, QUANTA: -4.0}


def read(name):
    with open(HERE / "result" / name, newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("dataset") not in EXCLUDED]


def human(seconds):
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} h"
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f} s"


def style(ax, taxa, xlabel=True):
    ax.set_facecolor("white")
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side, spine in ax.spines.items():
        spine.set_visible(side == "bottom")
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(length=0, labelsize=13, labelcolor=INK)
    if taxa:
        # 46 and 48 are too close to both carry labels; 46 keeps an unlabeled tick.
        ax.set_xticks([t for t in taxa if t != 46])
        ax.set_xticks([t for t in taxa if t == 46], minor=True)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlim(min(taxa) - 10, max(taxa) + 32)
    if xlabel:
        ax.set_xlabel("Number of taxa", fontsize=14, fontweight="bold", color=INK)


def lift_zero(ax):
    """Lift zero a fixed distance above the axis so points at ~0 stay visible."""
    top = ax.get_ylim()[1]
    height_mm = ax.get_position().height * ax.figure.get_figheight() * 25.4
    gap = ZERO_GAP_MM / height_mm
    ax.set_ylim(-top * gap / (1 - gap), top)


def series_minutes(ax, rows, key, label, color, marker, annotate=True, replicates=None):
    """Dataset means (one marker each), joined at each number of taxa; with
    replicates=(rows, key), also one small point per replicate."""
    if replicates:
        rep_rows, rep_key = replicates
        offset = REPLICATE_OFFSET.get(color, 4.0)
        ax.scatter([int(r["taxa"]) + offset for r in rep_rows], [float(r[rep_key]) / 60 for r in rep_rows],
                   color=color, marker=marker, s=24, alpha=0.55, linewidth=0, zorder=2)
    by_taxa = defaultdict(list)
    for row in rows:
        by_taxa[int(row["taxa"])].append(float(row[key]))
    xs = sorted(by_taxa)
    means = [sum(by_taxa[x]) / len(by_taxa[x]) for x in xs]
    ax.scatter([int(r["taxa"]) for r in rows], [float(r[key]) / 60 for r in rows], color=color,
               marker=marker, s=60, edgecolor="white", linewidth=1.2, zorder=4)
    ax.plot(xs, [m / 60 for m in means], color=color, linewidth=2.2, label=label, zorder=3)
    if annotate:
        ax.annotate(human(means[-1]), (xs[-1], means[-1] / 60), textcoords="offset points",
                    xytext=(8, 0), va="center", fontsize=12, color=INK)


def classical_by_dataset(solver):
    """Per-dataset means of the classical-solver runs, in the shape of timing_summary.csv."""
    groups = defaultdict(list)
    for row in read("classical_timing_per_file.csv"):
        if row["solver"] == solver:
            groups[(row["dataset"], row["taxa"])].append(row)
    return [{"dataset": dataset, "taxa": taxa,
             **{key: sum(float(r[key]) for r in rows) / len(rows)
                for key in ("end_to_end_seconds", "division_seconds")}}
            for (dataset, taxa), rows in groups.items()]


def binned_medians(points, width=10):
    """Median time per bin of partition sizes (21-30, 31-40, ...), at the bin's mean size."""
    bins = defaultdict(list)
    for size, seconds in points:
        bins[(size - 21) // width].append((size, seconds))
    xs, ys = [], []
    for key in sorted(bins):
        members = bins[key]
        xs.append(sum(s for s, _ in members) / len(members))
        ys.append(sorted(t for _, t in members)[len(members) // 2])
    return xs, ys


def panel_solving(ax):
    """One point per division step with more than 20 taxa, across all runs."""
    rows = read("partition_solving_times.csv")
    fm = [(int(r["partition_taxa"]), float(r["seconds"])) for r in rows if r["method"] == "wQFM"]
    # The 200-taxon root ran on the Leap Hybrid solver; its QPU access time is
    # treated like the other QPU calls (stated in the figure caption).
    qpu = [(int(r["partition_taxa"]), float(r["seconds"])) for r in rows if r["method"] == "QUANTA"]
    classical = read("classical_partition_times.csv")
    count = lambda points: f" ({len(points)} partitions)" if SHOW_COUNTS else ""
    series = [(fm, WQFM, "o", f"wQFM, FM heuristic{count(fm)}"),
              (qpu, QUANTA, "s", f"QUANTA, quantum annealer{count(qpu)}")]
    for solver, label, color, marker in CLASSICAL:
        points = [(int(r["partition_taxa"]), float(r["seconds"])) for r in classical if r["solver"] == solver]
        series.append((points, color, marker, f"{label.replace(' (', ', ').rstrip(')')}{count(points)}"))
    for points, color, marker, label in series:
        ax.scatter([s for s, _ in points], [t for _, t in points], color=color, marker=marker, s=20,
                   alpha=0.35, linewidth=0, zorder=3)
        xs, ys = binned_medians(points)
        ax.plot(xs, ys, color=color, linewidth=2.2, marker=marker, markersize=6, markeredgecolor="white",
                label=label, zorder=4)
    ax.set_yscale("log")
    ax.set_ylim(0.03, 3e4)
    ax.set_ylabel("Solving time per bipartition (s)", fontsize=14, fontweight="bold", color=INK)
    sizes = [s for s, _ in fm + qpu]
    style(ax, [], xlabel=False)
    ax.set_xticks([25, 50, 75, 100, 125, 150, 175, 200])
    ax.set_xlim(15, max(sizes) + 12)
    ax.set_xlabel("Partition size (number of taxa)", fontsize=14, fontweight="bold", color=INK)
    return sizes


def replicate_rows(solver=None):
    """Per-replicate rows for the time-by-taxa panels, or None without --replicate-points."""
    if not REPLICATE_POINTS:
        return None
    if solver is None:
        return read("timing_per_file.csv")
    return [r for r in read("classical_timing_per_file.csv") if r["solver"] == solver]


def panel_division(ax):
    rows = read("timing_summary.csv")
    reps = replicate_rows()
    series_minutes(ax, rows, "wqfm_division_seconds", "wQFM", WQFM, "o",
                   replicates=reps and (reps, "wqfm_division_seconds"))
    series_minutes(ax, rows, "wq2a_division_seconds", "QUANTA (quantum annealer)", QUANTA, "s",
                   replicates=reps and (reps, "wq2a_division_seconds"))
    for solver, label, color, marker in CLASSICAL:
        sreps = replicate_rows(solver)
        series_minutes(ax, classical_by_dataset(solver), "division_seconds", label, color, marker, annotate=False,
                       replicates=sreps and (sreps, "division_seconds"))
    ax.set_ylabel("Total division-step time (min)", fontsize=14, fontweight="bold", color=INK)
    taxa = sorted({int(r["taxa"]) for r in rows})
    style(ax, taxa)
    return taxa


def panel_end_to_end(ax):
    rows = read("timing_summary.csv")
    reps = replicate_rows()
    series_minutes(ax, rows, "wqfm_end_to_end_seconds", "wQFM", WQFM, "o",
                   replicates=reps and (reps, "wqfm_end_to_end_seconds"))
    series_minutes(ax, rows, "wq2a_end_to_end_seconds", "QUANTA (quantum annealer)", QUANTA, "s",
                   replicates=reps and (reps, "wq2a_end_to_end_seconds"))
    for solver, label, color, marker in CLASSICAL:
        sreps = replicate_rows(solver)
        series_minutes(ax, classical_by_dataset(solver), "end_to_end_seconds", label, color, marker, annotate=False,
                       replicates=sreps and (sreps, "end_to_end_seconds"))
    ax.set_ylabel("End-to-end time (min)", fontsize=14, fontweight="bold", color=INK)
    taxa = sorted({int(r["taxa"]) for r in rows})
    style(ax, taxa)
    return taxa


PANELS = [
    ("solving", panel_solving, "Solving time of each bipartition.", False),
    ("division", panel_division, "Total time of the division steps.", True),
    ("end_to_end", panel_end_to_end, "End-to-end running time.", True),
]


def finish(ax, letter, caption, linear):
    if linear:
        lift_zero(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    if letter:
        ax.text(0.0, 1.03, letter, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=20, fontweight="bold", color=INK)
    ax.text(0.5, -0.17, caption, transform=ax.transAxes, ha="center", va="top",
            fontsize=16, family="serif", color=INK)


def save(fig, name):
    out = HERE / "figure" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Figure saved: {out}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude-dataset", action="append", default=[],
                        help='dataset to leave out, as named in the result CSVs, e.g. "144 taxa (insect)"')
    parser.add_argument("--panels", nargs="+", choices=[name for name, *_ in PANELS],
                        help="draw only these panels, side by side, into --out")
    parser.add_argument("--out", default="running_time_selected.pdf", help="file name in figure/ (with --panels)")
    parser.add_argument("--no-partition-counts", action="store_true",
                        help="leave the number of partitions out of the legend of panel (a)")
    parser.add_argument("--replicate-points", action="store_true",
                        help="also show one point per replicate in the time-by-taxa panels")
    return parser.parse_args()


def draw_panels(panels, name):
    fig, axes = plt.subplots(1, len(panels), figsize=(7.5 * len(panels) - 0.5 * (len(panels) - 1), 6))
    for ax, (_, draw, _caption, _linear) in zip(axes, panels):
        draw(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    for ax, letter, (_, _draw, caption, linear) in zip(axes, ["(a)", "(b)", "(c)"], panels):
        finish(ax, letter, caption, linear)
    save(fig, name)


def main():
    args = parse_args()
    EXCLUDED.update(args.exclude_dataset)
    global SHOW_COUNTS, REPLICATE_POINTS
    SHOW_COUNTS = not args.no_partition_counts
    REPLICATE_POINTS = args.replicate_points
    if args.panels:
        draw_panels([panel for panel in PANELS if panel[0] in args.panels], args.out)
        return

    draw_panels(PANELS, "running_time_quanta.pdf")

    for name, draw, caption, linear in PANELS:
        fig, ax = plt.subplots(figsize=(7.5, 6))
        draw(ax)
        fig.tight_layout(rect=[0, 0.04, 1, 1])
        finish(ax, None, caption, linear)
        save(fig, f"running_time_{name}.pdf")


if __name__ == "__main__":
    main()
