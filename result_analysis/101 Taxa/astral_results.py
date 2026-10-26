#!/usr/bin/env python3
"""Collect the ASTRAL (ASTER astral4) results on the 101-taxon dataset.

ASTRAL runs on each replicate's 1000 true gene trees (ASTRAL-III S100), the
trees the weighted quartets were counted from, and its tree is scored
against the replicate's weighted-quartet file.

Reads the 101-taxon rows of baselines/results/astral_results.csv (written by
baselines/scripts/run_astral.py or run_astral_queued.py --only 101), adds the
wQFM and wQ²A RF distances of the same replicate from the QPU results CSV,
and writes:

  result/astral_101_taxa.csv          one row per replicate
  result/astral_101_taxa_summary.csv  mean and standard error over replicates

RF is the normalized Robinson-Foulds distance to each replicate's true
species tree. Run from the repository root:
    QWQFM/.venv/bin/python "result_analysis/101 Taxa/astral_results.py"
"""

import argparse
import csv
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def mean_se(values):
    n = len(values)
    if n == 0:
        return "", ""
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    return mean, math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1) / n)


def fmt(value):
    return "" if value == "" else f"{value:.6f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--astral-csv", default=REPO / "baselines" / "results" / "astral_results.csv")
    parser.add_argument("--qpu-csv", default=HERE / "result" / "results_101_taxa_qpu_plus_bruteforce.csv")
    parser.add_argument("--out-dir", default=HERE / "result")
    args = parser.parse_args()

    with open(args.qpu_csv, newline="") as handle:
        others = {r["quartet_file_name"]: r for r in csv.DictReader(handle)}

    rows = []
    with open(args.astral_csv, newline="") as handle:
        for r in csv.DictReader(handle):
            if r["group"] != "101":
                continue
            other = others.get(r["input_file"], {})
            rows.append({
                "quartet_file_name": r["input_file"], "replicate": r["input_file"].split(".")[0],
                "astral_method": r["method"], "astral_tree": r["astral_tree"],
                "rf_astral_wrt_base": r["rf"],
                "rf_wqfm_wrt_base": other.get("rf_wqfm_wrt_base", ""),
                "rf_quantum_wrt_base": other.get("rf_quantum_wrt_base", ""),
                "astral_weighted_quartet_score": r["weighted_quartet_score"],
                "total_quartet_weight": r["total_quartet_weight"],
                "astral_quartet_score_fraction": r["quartet_score_fraction"],
                "astral_end_to_end_seconds": r["end_to_end_seconds"],
                "astral_max_rss_mb": r["max_rss_mb"],
                "threads": r["threads"], "aster_version": r["aster_version"],
            })
    if not rows:
        raise SystemExit("no 101-taxon rows in " + str(args.astral_csv))
    rows.sort(key=lambda r: r["replicate"])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_file = out_dir / "astral_101_taxa.csv"
    with per_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {"replicates": len(rows)}
    for name, label in [("rf_astral_wrt_base", "rf_astral"), ("rf_wqfm_wrt_base", "rf_wqfm"),
                        ("rf_quantum_wrt_base", "rf_wq2a"),
                        ("astral_quartet_score_fraction", "astral_quartet_score_fraction")]:
        mean, se = mean_se([float(r[name]) for r in rows if r[name] != ""])
        summary[f"{label}_mean"], summary[f"{label}_se"] = fmt(mean), fmt(se)
    summary_file = out_dir / "astral_101_taxa_summary.csv"
    with summary_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary))
        writer.writeheader()
        writer.writerow(summary)

    print(f"{len(rows)} replicates")
    print(f"Saved {per_file}")
    print(f"Saved {summary_file}")


if __name__ == "__main__":
    main()
