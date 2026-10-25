#!/usr/bin/env python3
"""Collect per-replicate timing from a 101-taxon benchmark work directory into a CSV.

Each replicate directory holds wqfm.log (Algorithm 1) and quantum.log (Algorithm 2, wQ²A).
Recorded per replicate, in seconds:
  *_end_to_end      whole run, from the "Time taken = N ms" line
  *_division        sum of all division (bipartition) steps, wall clock
  wq2a_qpu_access   sum of D-Wave qpu_access_time over all QPU calls
  wq2a_bruteforce   sum of brute-force solves (partitions with n <= 20)
"""

import argparse
import csv
import re
from pathlib import Path

END_TO_END = re.compile(r"Time taken = (\d+) ms")
DIVISION = r"BENCHMARK_BIPARTITION_TIME_NS\s+algorithm={algo}\b[^\n]*?duration_ns=(\d+)"
QPU_ACCESS = re.compile(r"['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
BRUTE_FORCE = re.compile(r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)")
QPU_CALL = re.compile(r"QPU timing:")

FIELDNAMES = [
    "quartet_file_name",
    "wqfm_end_to_end_seconds",
    "wq2a_end_to_end_seconds",
    "wqfm_division_seconds",
    "wq2a_division_seconds",
    "wq2a_qpu_access_seconds",
    "wq2a_bruteforce_seconds",
    "wq2a_qpu_calls",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True, help="benchmark checkpoint directory")
    parser.add_argument("--out", required=True, help="timing CSV to write")
    return parser.parse_args()


def end_to_end_seconds(text, path):
    match = END_TO_END.search(text)
    if not match:
        raise ValueError(f"No 'Time taken' line in {path}")
    return int(match.group(1)) / 1000.0


def division_seconds(text, algo, path):
    values = re.findall(DIVISION.format(algo=algo), text)
    if not values:
        raise ValueError(f"No division-step timing markers in {path}")
    return sum(int(v) for v in values) / 1e9


def main():
    args = parse_args()
    rows = []
    for replicate in sorted(Path(args.work_dir).iterdir()):
        wqfm_log, wq2a_log = replicate / "wqfm.log", replicate / "quantum.log"
        if not (wqfm_log.is_file() and wq2a_log.is_file()):
            continue
        wqfm, wq2a = wqfm_log.read_text(errors="replace"), wq2a_log.read_text(errors="replace")
        rows.append({
            "quartet_file_name": replicate.name,
            "wqfm_end_to_end_seconds": f"{end_to_end_seconds(wqfm, wqfm_log):.3f}",
            "wq2a_end_to_end_seconds": f"{end_to_end_seconds(wq2a, wq2a_log):.3f}",
            "wqfm_division_seconds": f"{division_seconds(wqfm, 1, wqfm_log):.3f}",
            "wq2a_division_seconds": f"{division_seconds(wq2a, 2, wq2a_log):.3f}",
            # D-Wave reports qpu_access_time in microseconds.
            "wq2a_qpu_access_seconds": f"{sum(float(v) for v in QPU_ACCESS.findall(wq2a)) / 1e6:.6f}",
            "wq2a_bruteforce_seconds": f"{sum(int(v) for v in BRUTE_FORCE.findall(wq2a)) / 1e9:.6f}",
            "wq2a_qpu_calls": str(len(QPU_CALL.findall(wq2a))),
        })
    if not rows:
        raise SystemExit(f"Error: no replicate with both wqfm.log and quantum.log in {args.work_dir}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Timing for {len(rows)} replicates saved: {out}")


if __name__ == "__main__":
    main()
