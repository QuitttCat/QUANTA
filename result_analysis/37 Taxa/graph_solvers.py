#!/usr/bin/env python3
"""Plot average RF distance of QUANTA on the 37-taxon dataset with three QUBO
solvers for partitions with n>20 taxa: the D-Wave QPU, simulated annealing and
tabu search (smaller partitions are always solved by brute force).

Panels (a)-(c) are the bar panels of graph.py. Panel (d) is a donut of the
per-input outcome: whether all three solvers give the same RF distance, or
which one alone gives the lowest. The QPU results come from the benchmark
results CSV, the SA and tabu results from run_37_taxa_classical.sh. All three
are QUANTA, so they share its blue hue at three lightness steps.
"""

import argparse
import math

from graph import INK, MUTED, plot, group_values, read_rows

SERIES = [
    ("qpu", "rf_quantum_wrt_base", "QUANTA (D-Wave QPU)", "#2a78d6"),
    ("sa", "rf_simulated_annealing_wrt_base", "QUANTA (simulated annealing)", "#86b6ef"),
    ("tabu", "rf_tabu_search_wrt_base", "QUANTA (tabu search)", "#104281"),
]
SHORT = {"qpu": "QPU", "sa": "SA", "tabu": "Tabu"}
TIE_COLOR, PARTIAL_TIE_COLOR = "#c3c2b7", "#898781"


def outcomes(sources):
    """Count inputs by outcome: all solvers tie, one solver alone lowest, or a partial tie."""
    counts = {"All solvers tie": 0}
    counts.update({f"{SHORT[s]} better": 0 for s, _, _, _ in SERIES})
    counts["Two tie for best"] = 0
    for name in sources["qpu"]:
        rf = {s: float(sources[s][name][column]) for s, column, _, _ in SERIES}
        best = [s for s in rf if rf[s] == min(rf.values())]
        if len(best) == len(SERIES):
            counts["All solvers tie"] += 1
        elif len(best) == 1:
            counts[f"{SHORT[best[0]]} better"] += 1
        else:
            counts["Two tie for best"] += 1
    return counts


def outcome_donut(ax, counts):
    colors = {"All solvers tie": TIE_COLOR, "Two tie for best": PARTIAL_TIE_COLOR}
    colors.update({f"{SHORT[s]} better": color for s, _, _, color in SERIES})
    total = sum(counts.values())
    shown = [(label, n) for label, n in counts.items() if n]
    # No wedge outline: a white edge would hide a slice of a few degrees.
    radius = 1.25
    wedges, _ = ax.pie([n for _, n in shown], colors=[colors[label] for label, _ in shown],
                       startangle=90, counterclock=False, radius=radius,
                       wedgeprops={"width": 0.45, "linewidth": 0})
    ax.set_xlim(-1.35, 2.0)
    ax.set_ylim(-1.35, 1.6)
    ax.set_aspect("equal")
    tie = counts["All solvers tie"]
    ax.text(0, 0.1, f"{100 * tie / total:.1f}%", ha="center", va="center",
            fontsize=22, fontweight="bold", color=INK)
    ax.text(0, -0.2, "all solvers tie", ha="center", va="center", fontsize=13, color=MUTED)
    # Small slices are too thin to read, so each gets a labelled leader line.
    for wedge, (label, n) in zip(wedges, shown):
        if label == "All solvers tie":
            continue
        angle = (wedge.theta1 + wedge.theta2) / 2
        x, y = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        ax.annotate(f"{label}\n{n} input{'s' * (n != 1)} ({100 * n / total:.1f}%)",
                    xy=(1.02 * radius * x, 1.02 * radius * y),
                    xytext=(radius * x + 0.3, radius * y + 0.3),
                    ha="left", va="center", fontsize=12, color=INK,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 1.0})
    zero = [label for label, n in counts.items() if not n and label != "Two tie for best"]
    if zero:
        ax.text(0, -radius - 0.12, " · ".join(f"{label}: 0" for label in zero),
                ha="center", va="top", fontsize=12, color=MUTED)
    ax.text(-0.02, 1.03, "(d)", transform=ax.transAxes, ha="left", va="bottom",
            fontsize=20, fontweight="bold", color=INK)
    ax.text(0.5, -0.2, f"Per-input outcome ({total} inputs)", transform=ax.transAxes,
            ha="center", va="top", fontsize=16, family="serif", color=INK)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qpu-csv", required=True, help="QPU results CSV from run_37_taxa_benchmark.sh")
    parser.add_argument("--sa-csv", required=True, help="simulated-annealing CSV from run_37_taxa_classical.sh")
    parser.add_argument("--tabu-csv", required=True, help="tabu-search CSV from run_37_taxa_classical.sh")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    args = parser.parse_args()

    sources = {
        "qpu": read_rows(args.qpu_csv, "quartet_file_name"),
        "sa": read_rows(args.sa_csv, "quartet_file_name"),
        "tabu": read_rows(args.tabu_csv, "quartet_file_name"),
    }
    counts = outcomes(sources)
    plot(group_values(sources, SERIES), SERIES, args.out,
         extra_panel=lambda ax: outcome_donut(ax, counts))


if __name__ == "__main__":
    main()
