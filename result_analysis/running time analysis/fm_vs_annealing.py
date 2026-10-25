#!/usr/bin/env python3
"""Compare the solving time of wQFM's Fiduccia-Mattheyses (FM) heuristic with
the quantum annealer time of wQ2A, per number of taxa.

For each run, both times are summed over all division steps; the table then
averages these per-run totals over all runs with the same number of taxa.

- FM solving: BENCHMARK_CORE_DIVISION_TIME_NS (FM only) where the log has it,
  otherwise BENCHMARK_BIPARTITION_TIME_NS algorithm=1 (FM is 99.7-99.9% of it).
- Annealing: D-Wave qpu_access_time of every QPU call, plus the QPU access
  time of the Leap Hybrid job (200 taxa only).

Run from the repository root:
    python3 "result_analysis/running time analysis/fm_vs_annealing.py"
"""

import csv
import glob
import os
import re
from pathlib import Path
from statistics import mean

WORK = "QWQFM/benchmark/work"
OUT = Path("result_analysis/running time analysis/result/fm_vs_annealing_solving_time.csv")

CORE = re.compile(r"BENCHMARK_CORE_DIVISION_TIME_NS algorithm=1.*?duration_ns=(\d+)")
BIP1 = re.compile(r"BENCHMARK_BIPARTITION_TIME_NS algorithm=1 .*?duration_ns=(\d+)")
QACC = re.compile(r"'qpu_access_time': ([\d.]+)")


def fm_seconds(path):
    text = open(path, errors="replace").read()
    times = CORE.findall(text) or BIP1.findall(text)
    return sum(int(t) for t in times) / 1e9


def anneal_seconds_and_calls(path):
    seconds, calls = 0.0, 0
    for line in open(path, errors="replace"):
        if line.startswith(("QPU timing", "LEAP_HYBRID timing")):
            match = QACC.search(line)
            if match:
                seconds += float(match.group(1)) / 1e6
                calls += 1
    return seconds, calls


def bio(name):
    d = f"{WORK}/biological_qpu_plus_bruteforce/{name}.weighted_quartets"
    return (f"{d}/wqfm.log", f"{d}/quantum.log")


GROUPS = {
    37: [(f"{d}/wqfm.log", f"{d}/quantum.log")
         for d in sorted(glob.glob(f"{WORK}/37_taxa_quantum_A1_B1_n_gt_20/*_weighted_quartets"))]
        + [bio("mamalian")],
    46: [bio("angiosperm")],
    48: [bio(f"avian-{v}") for v in ("all", "exon", "intron", "uce")],
    101: [(f"{d}/wqfm.log", f"{d}/quantum.log")
          for d in sorted(glob.glob(f"{WORK}/101_taxa_qpu_plus_bruteforce/*.true.wqrts"))],
    144: [(f"{WORK}/insect_single_gene_144_taxa/insect_gene_tree_0713.weighted_quartets/wqfm.log",
           f"{WORK}/insect_single_gene_144_taxa/insect_gene_tree_0713.weighted_quartets/quantum.log")],
    200: [(f"{WORK}/200_taxa_full/algorithm1_wqfm.log", f"{WORK}/200_taxa_full/algorithm2_quantum.log")],
}


def main():
    rows = []
    for taxa, pairs in GROUPS.items():
        runs = [(fm_seconds(w), *anneal_seconds_and_calls(q))
                for w, q in pairs if os.path.exists(w) and os.path.exists(q)]
        fm = mean(r[0] for r in runs)
        anneal = mean(r[1] for r in runs)
        rows.append({
            "taxa": taxa,
            "runs": len(runs),
            "fm_solving_seconds": f"{fm:.3f}",
            "annealing_qpu_seconds": f"{anneal:.3f}",
            "ratio_fm_over_annealing": f"{fm / anneal:.1f}",
            "annealer_calls_per_run": f"{mean(r[2] for r in runs):.2f}",
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
