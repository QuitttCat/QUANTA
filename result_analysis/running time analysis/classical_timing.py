#!/usr/bin/env python3
"""Running times of QUANTA with the classical QUBO solvers (simulated
annealing and tabu search) in place of the quantum annealer, on the same
datasets as timing_summary.csv (curate_timing.py).

Reads the classical-solver runs (QWQFM/benchmark/work/<group>_<solver>_n_gt_20/,
written by run_classical_benchmark.sh) and writes:

  result/classical_timing_per_file.csv   one row per run: end-to-end time,
                                         total division-step time, sampler time
                                         and brute-force time
  result/classical_partition_times.csv   one row per partition with more than
                                         20 taxa: the sampler time of that call

The 200-taxon classical runs were made on another machine; their logs were
copied into the same work folders. Run from the repository root:
    python3 "result_analysis/running time analysis/classical_timing.py"
"""

import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1] / "QWQFM" / "benchmark" / "work"
SOLVERS = {"simulated_annealing": "SIMULATED_ANNEALING", "tabu_search": "TABU_SEARCH"}
# (dataset label in timing_summary.csv, number of taxa, run folder, input file or None for all)
RUNS = [
    ("37 taxa (simulated)", 37, "37_taxa_{solver}_n_gt_20", None),
    ("37 taxa (mammals)", 37, "biological_{solver}_n_gt_20", "mamalian.weighted_quartets"),
    ("46 taxa (angiosperm)", 46, "biological_{solver}_n_gt_20", "angiosperm.weighted_quartets"),
    ("48 taxa (avian, all)", 48, "biological_{solver}_n_gt_20", "avian-all.weighted_quartets"),
    ("48 taxa (avian, exon)", 48, "biological_{solver}_n_gt_20", "avian-exon.weighted_quartets"),
    ("48 taxa (avian, intron)", 48, "biological_{solver}_n_gt_20", "avian-intron.weighted_quartets"),
    ("48 taxa (avian, UCE)", 48, "biological_{solver}_n_gt_20", "avian-uce.weighted_quartets"),
    ("101 taxa (simulated)", 101, "101_{solver}_n_gt_20", None),
    ("144 taxa (insect)", 144, "144_{solver}_n_gt_20", None),
    ("200 taxa (simulated)", 200, "200_{solver}_n_gt_20", None),
]
END_TO_END = re.compile(r"Time taken = (\d+) ms")
DIVISION = re.compile(r"BENCHMARK_BIPARTITION_TIME_NS\s+algorithm=2\b[^\n]*?duration_ns=(\d+)")
BRUTE_FORCE = re.compile(r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)")


def main():
    files, partitions = [], []
    for solver, marker in SOLVERS.items():
        sampler = re.compile(rf"{marker}_TIME_NS n=(\d+) duration_ns=(\d+)")
        for dataset, taxa, folder, only in RUNS:
            run_dir = WORK / folder.format(solver=solver)
            for result_dir in sorted(run_dir.iterdir()):
                if only and result_dir.name != only:
                    continue
                if not (result_dir / "quantum.done").exists():
                    continue
                text = (result_dir / "quantum.log").read_text(errors="replace")
                calls = [(int(n), int(ns) / 1e9) for n, ns in sampler.findall(text)]
                base = {"solver": solver, "dataset": dataset, "taxa": taxa, "quartet_file_name": result_dir.name}
                files.append({
                    **base,
                    "end_to_end_seconds": f"{int(END_TO_END.search(text).group(1)) / 1000:.3f}",
                    "division_seconds": f"{sum(int(v) for v in DIVISION.findall(text)) / 1e9:.6f}",
                    "sampler_seconds": f"{sum(s for _, s in calls):.6f}",
                    "bruteforce_seconds": f"{sum(int(v) for v in BRUTE_FORCE.findall(text)) / 1e9:.6f}",
                })
                partitions += [{**base, "partition_taxa": n, "seconds": f"{s:.6f}"} for n, s in calls]

    for name, rows in [("classical_timing_per_file.csv", files), ("classical_partition_times.csv", partitions)]:
        out = HERE / "result" / name
        with out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
