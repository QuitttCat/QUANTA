#!/usr/bin/env python3
"""Solving time of the division steps: wQFM's FM heuristic against QUANTA's
quantum annealer, on the same runs as timing_per_file.csv (curate_timing.py).

Both are summed over the partitions with more than 20 taxa, the ones QUANTA
sends to the quantum annealer, so the two columns compare the same kind of
work (QUANTA solves smaller partitions by brute force, wQFM by FM; both are
reported separately). Per run, then averaged over runs with the same number
of taxa.

- FM:  BENCHMARK_CORE_DIVISION_TIME_NS (FM only) where the log has it,
       otherwise BENCHMARK_BIPARTITION_TIME_NS algorithm=1 (FM is 99.7-99.9%).
- QPU: D-Wave qpu_access_time of every QPU call and of the Leap Hybrid job.
- Leap Hybrid run time (200 taxa only): the full hybrid job, mostly classical.

Writes result/solving_time_by_taxa.csv. Run from the repository root:
    python3 "result_analysis/running time analysis/solving_time.py"
"""

import csv
import re
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PER_FILE = HERE / "result" / "timing_per_file.csv"
OUT = HERE / "result" / "solving_time_by_taxa.csv"
THRESHOLD = 20

CORE = re.compile(r"BENCHMARK_CORE_DIVISION_TIME_NS algorithm=1\b[^\n]*?taxa=(\d+) duration_ns=(\d+)")
BIPARTITION = re.compile(r"BENCHMARK_BIPARTITION_TIME_NS algorithm=1\b[^\n]*?taxa=(\d+) duration_ns=(\d+)")
QPU_ACCESS = re.compile(r"['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
HYBRID_RUN = re.compile(r"LEAP_HYBRID timing:.*?['\"]run_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
HYBRID_QPU = re.compile(r"LEAP_HYBRID timing:.*?['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
BRUTE_FORCE = re.compile(r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)")


def fm_seconds(path):
    text = (ROOT / path).read_text(errors="replace")
    steps = [(int(n), int(ns)) for n, ns in (CORE.findall(text) or BIPARTITION.findall(text))]
    large = sum(ns for n, ns in steps if n > THRESHOLD) / 1e9
    small = sum(ns for n, ns in steps if n <= THRESHOLD) / 1e9
    return large, small


def quanta_seconds(path):
    text = (ROOT / path).read_text(errors="replace")
    qpu = sum(float(v) for v in QPU_ACCESS.findall(text)) / 1e6
    hybrid_run = sum(float(v) for v in HYBRID_RUN.findall(text)) / 1e6
    hybrid_qpu = sum(float(v) for v in HYBRID_QPU.findall(text)) / 1e6
    bruteforce = sum(int(v) for v in BRUTE_FORCE.findall(text)) / 1e9
    # QPU access with the Leap Hybrid job counted by its full run time instead
    # of its QPU share (the hybrid QPU access is already part of `qpu`).
    with_hybrid = qpu - hybrid_qpu + hybrid_run
    return qpu, with_hybrid, bruteforce


def main():
    with PER_FILE.open(newline="") as handle:
        files = list(csv.DictReader(handle))
    groups = {}
    for row in files:
        fm_large, fm_small = fm_seconds(row["wqfm_log"])
        qpu, with_hybrid, bruteforce = quanta_seconds(row["wq2a_log"])
        groups.setdefault(int(row["taxa"]), []).append((fm_large, fm_small, qpu, with_hybrid, bruteforce))

    rows = []
    for taxa in sorted(groups):
        runs = groups[taxa]
        fm_large, fm_small, qpu, with_hybrid, bruteforce = (mean(r[i] for r in runs) for i in range(5))
        rows.append({
            "taxa": taxa,
            "runs": len(runs),
            "wqfm_fm_seconds_gt20": f"{fm_large:.6f}",
            "quanta_qpu_access_seconds_gt20": f"{qpu:.6f}",
            "speedup_fm_over_qpu": f"{fm_large / qpu:.1f}",
            "quanta_with_leap_hybrid_run_seconds_gt20": f"{with_hybrid:.6f}",
            "speedup_fm_over_with_hybrid": f"{fm_large / with_hybrid:.1f}",
            "wqfm_fm_seconds_le20": f"{fm_small:.6f}",
            "quanta_bruteforce_seconds_le20": f"{bruteforce:.6f}",
        })
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {OUT}")
    for row in rows:
        print("  " + ", ".join(f"{k}={v}" for k, v in row.items()))


if __name__ == "__main__":
    main()
