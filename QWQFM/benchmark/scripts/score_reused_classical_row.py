#!/usr/bin/env python3
"""Score a quantum tree while reusing classical results from another CSV."""

import argparse
import csv
import math
import os
from pathlib import Path
import tempfile

import score_benchmark_row as common


FIELDNAMES = [
    "quartet_file_name",
    "wqfm_tree",
    "quantum_annealing_tree",
    "quantum_solver",
    "quantum_topology",
    "rf_wqfm_wrt_base",
    "rf_quantum_wrt_base",
    "better",
    "wqfm_bipartition_time_seconds",
    "quantum_qpu_access_time_seconds",
    "quantum_bruteforce_time_seconds",
    "quantum_time_seconds",
]

CLASSICAL_FIELDS = [
    "quartet_file_name",
    "wqfm_tree",
    "rf_wqfm_wrt_base",
    "wqfm_bipartition_time_seconds",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--quartet-file")
    parser.add_argument("--model-tree")
    parser.add_argument("--quantum-tree")
    parser.add_argument("--quantum-log")
    parser.add_argument("--rf-script")
    parser.add_argument("--quantum-solver", default="Advantage2_system1")
    parser.add_argument("--quantum-topology", default="zephyr_z12")
    args = parser.parse_args()

    if not args.initialize:
        required = {
            "--quartet-file": args.quartet_file,
            "--model-tree": args.model_tree,
            "--quantum-tree": args.quantum_tree,
            "--quantum-log": args.quantum_log,
            "--rf-script": args.rf_script,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            parser.error("missing required arguments: " + ", ".join(missing))
    return args


def read_csv(path):
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return reader.fieldnames, rows


def write_csv_atomic(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(fd, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def source_rows(path):
    fieldnames, rows = read_csv(path)
    missing = [name for name in CLASSICAL_FIELDS if name not in (fieldnames or [])]
    if missing:
        raise ValueError(f"Source CSV lacks classical columns: {missing}")
    return rows


def initialize_output(source_path, output_path):
    source = source_rows(source_path)
    completed = {}
    output = Path(output_path)
    if output.exists() and output.stat().st_size:
        fieldnames, existing = read_csv(output)
        if fieldnames != FIELDNAMES:
            raise ValueError(
                f"Unexpected CSV columns in {output}: {fieldnames}"
            )
        completed = {
            row["quartet_file_name"]: row
            for row in existing
            if row.get("quantum_annealing_tree")
        }

    rows = []
    for source_row in source:
        name = source_row["quartet_file_name"]
        if name in completed:
            row = completed[name]
            for field in CLASSICAL_FIELDS:
                row[field] = source_row[field]
        else:
            row = {field: "" for field in FIELDNAMES}
            for field in CLASSICAL_FIELDS:
                row[field] = source_row[field]
        rows.append(row)

    rows.sort(key=lambda row: row["quartet_file_name"])
    write_csv_atomic(output_path, rows)
    print(
        f"Initialized {output_path} with {len(rows)} classical rows; "
        f"{len(completed)} quantum rows already complete"
    )


def find_source_row(path, quartet_name):
    matches = [
        row
        for row in source_rows(path)
        if row["quartet_file_name"] == quartet_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one source row for {quartet_name}, found "
            f"{len(matches)}"
        )
    return matches[0]


def upsert_output(path, row):
    fieldnames, rows = read_csv(path)
    if fieldnames != FIELDNAMES:
        raise ValueError(f"Unexpected CSV columns in {path}: {fieldnames}")
    rows = [
        existing
        for existing in rows
        if existing["quartet_file_name"] != row["quartet_file_name"]
    ]
    rows.append(row)
    rows.sort(key=lambda item: item["quartet_file_name"])
    write_csv_atomic(path, rows)


def score_row(args):
    quartet_name = Path(args.quartet_file).name
    source = find_source_row(args.source_csv, quartet_name)
    model_tree = args.model_tree.strip()
    if not model_tree.endswith(";"):
        model_tree += ";"

    quantum_tree = common.read_tree(args.quantum_tree)
    rf_module = common.load_rf_module(args.rf_script)
    rf_quantum = common.rf_distance(rf_module, model_tree, quantum_tree)
    rf_wqfm = float(source["rf_wqfm_wrt_base"])

    if math.isclose(rf_wqfm, rf_quantum, rel_tol=0.0, abs_tol=1e-12):
        better = 0
    elif rf_quantum < rf_wqfm:
        better = 1
    else:
        better = -1

    qpu_seconds = common.sum_quantum_qpu_seconds(args.quantum_log)
    brute_force_seconds = common.sum_quantum_bruteforce_seconds(args.quantum_log)
    row = {
        "quartet_file_name": quartet_name,
        "wqfm_tree": source["wqfm_tree"],
        "quantum_annealing_tree": quantum_tree,
        "quantum_solver": args.quantum_solver,
        "quantum_topology": args.quantum_topology,
        "rf_wqfm_wrt_base": source["rf_wqfm_wrt_base"],
        "rf_quantum_wrt_base": f"{rf_quantum:.12f}",
        "better": str(better),
        "wqfm_bipartition_time_seconds": source[
            "wqfm_bipartition_time_seconds"
        ],
        "quantum_qpu_access_time_seconds": f"{qpu_seconds:.9f}",
        "quantum_bruteforce_time_seconds": f"{brute_force_seconds:.9f}",
        "quantum_time_seconds": f"{qpu_seconds + brute_force_seconds:.9f}",
    }
    upsert_output(args.output_csv, row)
    print(
        f"  CSV row: RF WQFM={rf_wqfm:.6f}, "
        f"RF Z12={rf_quantum:.6f}, better={better}"
    )


def main():
    args = parse_args()
    if args.initialize:
        initialize_output(args.source_csv, args.output_csv)
    else:
        score_row(args)


if __name__ == "__main__":
    main()
