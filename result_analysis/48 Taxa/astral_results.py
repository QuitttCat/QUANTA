#!/usr/bin/env python3
"""Collect the ASTRAL (ASTER wastral) results on the 48-taxon dataset.

Reads the 48-taxon rows of baselines/results/astral_results.csv (written by
baselines/scripts/run_astral.py --only 48), adds the wQFM and wQ²A RF distances
of the same input file from the Z12 results CSV, and writes:

  result/astral_48_taxa.csv          one row per input file
  result/astral_48_taxa_summary.csv  one row per condition (mean and standard error)

Run from the repository root:
    QWQFM/.venv/bin/python "result_analysis/48 Taxa/astral_results.py"
"""

import argparse
import csv
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FILE_PATTERN = re.compile(r"^(0\.5X|1X|2X)-(\d+)-(\d+)_R(\d+)_weighted_quartets$")
ILS_ORDER = {"0.5X": 0, "1X": 1, "2X": 2}


def mean_se(values):
    n = len(values)
    if n == 0:
        return "", ""
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def fmt(value, digits=6):
    return "" if value == "" else f"{value:.{digits}f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--astral-csv", default=REPO / "baselines" / "results" / "astral_results.csv")
    parser.add_argument("--z12-csv", default=HERE / "result" / "results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv")
    parser.add_argument("--out-dir", default=HERE / "result")
    args = parser.parse_args()

    with open(args.z12_csv, newline="") as handle:
        others = {r["quartet_file_name"]: r for r in csv.DictReader(handle)}

    rows = []
    with open(args.astral_csv, newline="") as handle:
        for r in csv.DictReader(handle):
            if r["group"] != "48":
                continue
            ils, genes, bp, rep = FILE_PATTERN.match(r["input_file"]).groups()
            other = others.get(r["input_file"], {})
            rows.append({
                "quartet_file_name": r["input_file"], "ils": ils, "genes": int(genes), "bp": int(bp),
                "replicate": int(rep), "astral_tree": r["astral_tree"],
                "rf_astral_wrt_base": r["rf"],
                "rf_wqfm_wrt_base": other.get("rf_wqfm_wrt_base", ""),
                "rf_quantum_wrt_base": other.get("rf_quantum_wrt_base", ""),
                "astral_weighted_quartet_score": r["weighted_quartet_score"],
                "total_quartet_weight": r["total_quartet_weight"],
                "astral_quartet_score_fraction": r["quartet_score_fraction"],
                "astral_end_to_end_seconds": r["end_to_end_seconds"],
                "astral_conversion_seconds": r["conversion_seconds"],
                "astral_max_rss_mb": r["max_rss_mb"],
                "threads": r["threads"], "aster_version": r["aster_version"],
            })
    rows.sort(key=lambda r: (ILS_ORDER[r["ils"]], r["genes"], r["bp"], r["replicate"]))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_file = out_dir / "astral_48_taxa.csv"
    with per_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    conditions = {}
    for r in rows:
        conditions.setdefault((r["ils"], r["genes"], r["bp"]), []).append(r)
    summary = []
    for (ils, genes, bp), group in sorted(conditions.items(), key=lambda kv: (ILS_ORDER[kv[0][0]], kv[0][1], kv[0][2])):
        def column(name):
            return [float(r[name]) for r in group if r[name] != ""]
        line = {"condition": f"{ils}-{genes}-{bp}", "ils": ils, "genes": genes, "bp": bp, "replicates": len(group)}
        for name, label in [("rf_astral_wrt_base", "rf_astral"), ("rf_wqfm_wrt_base", "rf_wqfm"),
                            ("rf_quantum_wrt_base", "rf_wq2a"),
                            ("astral_quartet_score_fraction", "astral_quartet_score_fraction"),
                            ("astral_end_to_end_seconds", "astral_seconds")]:
            mean, se = mean_se(column(name))
            line[f"{label}_mean"], line[f"{label}_se"] = fmt(mean), fmt(se)
        summary.append(line)
    summary_file = out_dir / "astral_48_taxa_summary.csv"
    with summary_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print(f"{len(rows)} files, {len(summary)} conditions")
    print(f"Saved {per_file}")
    print(f"Saved {summary_file}")


if __name__ == "__main__":
    main()
