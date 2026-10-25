#!/usr/bin/env python3
"""Curate wQFM vs wQ²A timing from benchmark run logs into two CSVs.

For every input file of every dataset below, it reads the wQFM log and the
wQ²A log of one run and records, in seconds:
  end-to-end        whole run ("Time taken = N ms")
  division          sum of all division (bipartition) steps, wall clock
  qpu_access        D-Wave qpu_access_time of every QPU and Leap Hybrid job
  bruteforce        brute-force solves of partitions with n <= 20
  hybrid_solver     Leap Hybrid run time minus its QPU access (classical part)
  other_overhead    division - qpu_access - bruteforce - hybrid_solver
                    (building the QUBO, network round trips, bookkeeping)

Writes timing_per_file.csv (one row per input file), timing_summary.csv (one
row per dataset: mean over its files) and timing_by_taxa.csv (one row per
number of taxa: mean over every sample with that many taxa, across datasets).
Paths are relative to the repository root.
"""

import argparse
import csv
import re
from pathlib import Path

BIO_CSV = "QWQFM/benchmark/output_csv/biological/results_biological_qpu_plus_bruteforce_n>20.csv"
BIO_RUN = "QWQFM/benchmark/work/biological_qpu_plus_bruteforce"

# Each dataset: which files (from a results CSV, optionally narrowed by name)
# and which run's logs supply the timing.
DATASETS = [
    dict(dataset="37 taxa (simulated)", taxa=37,
         files_from="QWQFM/benchmark/output_csv/results_37_taxa_qpu_plus_bruteforce_n>20.csv",
         run="QWQFM/benchmark/work/37_taxa_quantum_A1_B1_n_gt_20"),
    dict(dataset="37 taxa (mammals)", taxa=37, files_from=BIO_CSV, only=["mamalian.weighted_quartets"], run=BIO_RUN),
    dict(dataset="46 taxa (angiosperm)", taxa=46, files_from=BIO_CSV, only=["angiosperm.weighted_quartets"], run=BIO_RUN),
    dict(dataset="48 taxa (avian, all)", taxa=48, files_from=BIO_CSV, only=["avian-all.weighted_quartets"], run=BIO_RUN),
    dict(dataset="48 taxa (avian, exon)", taxa=48, files_from=BIO_CSV, only=["avian-exon.weighted_quartets"], run=BIO_RUN),
    dict(dataset="48 taxa (avian, intron)", taxa=48, files_from=BIO_CSV, only=["avian-intron.weighted_quartets"], run=BIO_RUN),
    dict(dataset="48 taxa (avian, UCE)", taxa=48, files_from=BIO_CSV, only=["avian-uce.weighted_quartets"], run=BIO_RUN),
    # Excluded until wQFM is rerun on the server: the Z12 run kept no wQFM logs,
    # and the local rerun's machine is ~3.3x slower than the server used for wQ²A.
    # dict(dataset="48 taxa (simulated)", taxa=48,
    #      files_from="QWQFM/benchmark/output_csv/results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv",
    #      run="QWQFM/benchmark/work/48_taxa_z12_qpu_plus_bruteforce_n_gt_20",
    #      wqfm_run="QWQFM/benchmark/work/48_taxa_wqfm_only_server"),
    dict(dataset="101 taxa (simulated)", taxa=101,
         files_from="QWQFM/benchmark/output_csv/results_101_taxa_qpu_plus_bruteforce.csv",
         run="QWQFM/benchmark/work/101_taxa_qpu_plus_bruteforce"),
    dict(dataset="144 taxa (insect)", taxa=144,
         files_from="QWQFM/benchmark/output_csv/biological/results_insect_single_gene_144_taxa.csv",
         run="QWQFM/benchmark/work/insect_single_gene_144_taxa"),
    # The 200-taxon run keeps its logs directly in the run directory.
    dict(dataset="200 taxa (simulated)", taxa=200,
         single_run="QWQFM/benchmark/work/200_taxa_full",
         wqfm_log="algorithm1_wqfm.log", wq2a_log="algorithm2_quantum.log"),
]

END_TO_END = re.compile(r"Time taken = (\d+) ms")
DIVISION = r"BENCHMARK_BIPARTITION_TIME_NS\s+algorithm={algo}\b[^\n]*?duration_ns=(\d+)"
QPU_ACCESS = re.compile(r"['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)")
BRUTE_FORCE = re.compile(r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)")
HYBRID = re.compile(r"LEAP_HYBRID timing:.*?['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)"
                    r".*?['\"]run_time['\"]\s*:\s*(\d+(?:\.\d+)?)")

TIMES = [
    "wqfm_end_to_end_seconds",
    "wq2a_end_to_end_seconds",
    "wqfm_division_seconds",
    "wq2a_division_seconds",
    "wq2a_qpu_access_seconds",
    "wq2a_bruteforce_seconds",
    "wq2a_hybrid_solver_seconds",
    "wq2a_other_overhead_seconds",
]
PER_FILE_FIELDS = ["dataset", "taxa", "quartet_file_name", "wqfm_log", "wq2a_log"] + TIMES
SUMMARY_FIELDS = ["dataset", "taxa", "files", "end_to_end_files"] + TIMES + ["note"]
END_TO_END_TIMES = ["wqfm_end_to_end_seconds", "wq2a_end_to_end_seconds"]


def average(rows):
    """Mean of each time. End-to-end times use only rows where both methods have one."""
    paired = [r for r in rows if all(r[k] is not None for k in END_TO_END_TIMES)]
    means = {}
    for key in TIMES:
        pool = paired if key in END_TO_END_TIMES else rows
        means[key] = f"{sum(r[key] for r in pool) / len(pool):.6f}" if pool else ""
    return {"files": len(rows), "end_to_end_files": len(paired), **means}


def fmt(value):
    return "" if value is None else f"{value:.6f}"


def group_label(taxa, datasets):
    """e.g. '48 taxa (avian ×4, simulated)' from the datasets sharing a taxon count."""
    kinds = {}
    for name in datasets:
        kind = name.split("(", 1)[1].rstrip(")").split(",")[0].strip()
        kinds[kind] = kinds.get(kind, 0) + 1
    parts = [f"{kind} ×{count}" if count > 1 else kind for kind, count in kinds.items()]
    return f"{taxa} taxa ({', '.join(parts)})"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--out-dir", required=True, help="directory for the timing CSVs")
    return parser.parse_args()


def required(pattern, text, path, what):
    values = pattern.findall(text) if hasattr(pattern, "findall") else re.findall(pattern, text)
    if not values:
        raise ValueError(f"No {what} in {path}")
    return values


def timing(wqfm_path, wq2a_path, wqfm_division=None):
    """Timing for one file. Without a wQFM log (wqfm_path None), the wQFM
    division time must be given and wQFM end-to-end is unknown (None)."""
    wq2a = wq2a_path.read_text(errors="replace")
    if wqfm_path is None:
        wqfm_end_to_end = None
    else:
        wqfm = wqfm_path.read_text(errors="replace")
        wqfm_end_to_end = int(required(END_TO_END, wqfm, wqfm_path, "'Time taken' line")[-1]) / 1000
        wqfm_division = sum(int(v) for v in required(DIVISION.format(algo=1), wqfm, wqfm_path,
                                                     "division markers")) / 1e9
    division_wq2a = sum(int(v) for v in required(DIVISION.format(algo=2), wq2a, wq2a_path, "division markers")) / 1e9
    # D-Wave reports times in microseconds.
    qpu_access = sum(float(v) for v in QPU_ACCESS.findall(wq2a)) / 1e6
    bruteforce = sum(int(v) for v in BRUTE_FORCE.findall(wq2a)) / 1e9
    hybrid_solver = sum(float(run) - float(qpu) for qpu, run in HYBRID.findall(wq2a)) / 1e6
    overhead = division_wq2a - qpu_access - bruteforce - hybrid_solver
    if overhead < -1e-6:
        raise ValueError(f"Division time smaller than its measured parts in {wq2a_path}")
    return {
        "wqfm_end_to_end_seconds": wqfm_end_to_end,
        "wq2a_end_to_end_seconds": int(required(END_TO_END, wq2a, wq2a_path, "'Time taken' line")[-1]) / 1000,
        "wqfm_division_seconds": wqfm_division,
        "wq2a_division_seconds": division_wq2a,
        "wq2a_qpu_access_seconds": qpu_access,
        "wq2a_bruteforce_seconds": bruteforce,
        "wq2a_hybrid_solver_seconds": hybrid_solver,
        "wq2a_other_overhead_seconds": max(overhead, 0.0),
    }


def rows_of(spec, root):
    """Rows of the dataset's results CSV, narrowed to the selected files."""
    with open(root / spec["files_from"], newline="") as handle:
        rows = list(csv.DictReader(handle))
    if "only" in spec:
        rows = [r for r in rows if r["quartet_file_name"] in spec["only"]]
    if not rows:
        raise ValueError(f"No files selected for {spec['dataset']}")
    return rows


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    per_file, summary = [], []
    by_taxa = {}

    for spec in DATASETS:
        # jobs: (file name, wQFM log or None, wQ²A log, wQFM division time if no wQFM log)
        if "single_run" in spec:
            run = root / spec["single_run"]
            jobs = [(run.name, run / spec["wqfm_log"], run / spec["wq2a_log"], None)]
        else:
            run = root / spec["run"]
            wqfm_run = root / spec.get("wqfm_run", spec["run"])
            column = spec.get("wqfm_division_from_csv")
            jobs = [(r["quartet_file_name"],
                     None if column else wqfm_run / r["quartet_file_name"] / "wqfm.log",
                     run / r["quartet_file_name"] / "quantum.log",
                     float(r[column]) if column else None)
                    for r in rows_of(spec, root)]

        rows = []
        for name, wqfm_log, wq2a_log, wqfm_division in jobs:
            for log in (wqfm_log, wq2a_log):
                if log is not None and not log.is_file():
                    raise FileNotFoundError(f"Missing log for {spec['dataset']} / {name}: {log}")
            rows.append(timing(wqfm_log, wq2a_log, wqfm_division))
            wqfm_source = (str(wqfm_log.relative_to(root)) if wqfm_log else
                           f"{spec['files_from']} ({spec['wqfm_division_from_csv']}; no end-to-end)")
            per_file.append({"dataset": spec["dataset"], "taxa": spec["taxa"], "quartet_file_name": name,
                             "wqfm_log": wqfm_source, "wq2a_log": str(wq2a_log.relative_to(root)),
                             **{k: fmt(rows[-1][k]) for k in TIMES}})
        group = by_taxa.setdefault(spec["taxa"], {"datasets": [], "rows": [], "notes": []})
        group["datasets"].append(spec["dataset"])
        group["rows"].extend(rows)
        if spec.get("note"):
            group["notes"].append(spec["note"])

        summary.append({"dataset": spec["dataset"], "taxa": spec["taxa"], **average(rows),
                        "note": spec.get("note", "")})
        print(f"{spec['dataset']:26s} files={len(rows):3d} (end-to-end for {summary[-1]['end_to_end_files']})")

    # Pool every sample with the same number of taxa, across datasets.
    grouped = [{"dataset": group_label(taxa, g["datasets"]), "taxa": taxa, **average(g["rows"]),
                "note": "; ".join(g["notes"])}
               for taxa, g in sorted(by_taxa.items())]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fields, rows in [("timing_per_file.csv", PER_FILE_FIELDS, per_file),
                               ("timing_summary.csv", SUMMARY_FIELDS, summary),
                               ("timing_by_taxa.csv", SUMMARY_FIELDS, grouped)]:
        with (out_dir / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved: {out_dir / name}")


if __name__ == "__main__":
    main()
