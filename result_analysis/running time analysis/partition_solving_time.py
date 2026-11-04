#!/usr/bin/env python3
"""Solving time of every division step with more than 20 taxa, one row per
partition, for wQFM's FM heuristic and QUANTA's quantum annealer.

Reads the same runs as timing_per_file.csv (curate_timing.py), simulated and
biological. For wQFM, each BENCHMARK_CORE_DIVISION_TIME_NS line (FM only), or
BENCHMARK_BIPARTITION_TIME_NS algorithm=1 where the log has no core lines
(FM is 99.7-99.9% of it), gives one partition and its time. For QUANTA, each
QPU call's qpu_access_time is paired with the division step that follows it
in the log, which gives the partition size; the 200-taxon root partition ran
on the Leap Hybrid solver and is marked as such (its QPU access time, with
the job's full run time alongside).

Writes result/partition_solving_times.csv. Run from the repository root:
    python3 "result_analysis/running time analysis/partition_solving_time.py"
"""

import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PER_FILE = HERE / "result" / "timing_per_file.csv"
OUT = HERE / "result" / "partition_solving_times.csv"
THRESHOLD = 20

CORE = re.compile(r"BENCHMARK_CORE_DIVISION_TIME_NS algorithm=1\b[^\n]*?taxa=(\d+) duration_ns=(\d+)")
BIPARTITION_1 = re.compile(r"BENCHMARK_BIPARTITION_TIME_NS algorithm=1\b[^\n]*?taxa=(\d+) duration_ns=(\d+)")
STEP_2 = re.compile(r"BENCHMARK_BIPARTITION_TIME_NS algorithm=2\b[^\n]*?taxa=(\d+)")
QPU = re.compile(r"QPU timing:.*?['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
HYBRID = re.compile(r"LEAP_HYBRID timing:.*?['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)"
                    r"(?:.*?['\"]run_time['\"]\s*:\s*(\d+(?:\.\d+)?))?")
FIELDS = ["method", "dataset", "taxa", "quartet_file_name", "partition_taxa", "seconds", "solver",
          "hybrid_run_seconds"]


def wqfm_rows(row):
    text = (ROOT / row["wqfm_log"]).read_text(errors="replace")
    for n, ns in CORE.findall(text) or BIPARTITION_1.findall(text):
        if int(n) > THRESHOLD:
            yield {"method": "wQFM", "partition_taxa": int(n), "seconds": int(ns) / 1e9,
                   "solver": "FM", "hybrid_run_seconds": ""}


def quanta_rows(row):
    pending = None
    for line in (ROOT / row["wq2a_log"]).read_text(errors="replace").splitlines():
        match = QPU.search(line)
        if match:
            pending = ("QPU", float(match.group(1)) / 1e6, "")
            continue
        match = HYBRID.search(line)
        if match:
            run = float(match.group(2)) / 1e6 if match.group(2) else ""
            pending = ("Leap Hybrid (QPU part)", float(match.group(1)) / 1e6, run)
            continue
        match = STEP_2.search(line)
        if match and pending is not None:
            solver, seconds, run = pending
            pending = None
            if int(match.group(1)) > THRESHOLD:
                yield {"method": "QUANTA", "partition_taxa": int(match.group(1)), "seconds": seconds,
                       "solver": solver, "hybrid_run_seconds": run}


def main():
    with PER_FILE.open(newline="") as handle:
        files = list(csv.DictReader(handle))
    rows = []
    for row in files:
        base = {"dataset": row["dataset"], "taxa": row["taxa"], "quartet_file_name": row["quartet_file_name"]}
        for part in list(wqfm_rows(row)) + list(quanta_rows(row)):
            rows.append({**base, **part})
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    for method in ("wQFM", "QUANTA"):
        sizes = [r["partition_taxa"] for r in rows if r["method"] == method]
        print(f"{method}: {len(sizes)} partitions with >{THRESHOLD} taxa, sizes {min(sizes)}-{max(sizes)}")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
