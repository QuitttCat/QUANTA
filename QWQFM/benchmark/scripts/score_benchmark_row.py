#!/usr/bin/env python3
"""Score one WQFM/quantum benchmark pair and atomically upsert its CSV row."""

import argparse
import csv
import importlib.util
import math
import os
from pathlib import Path
import re
import tempfile


FIELDNAMES = [
    "quartet_file_name",
    "wqfm_tree",
    "quantum_annealing_tree",
    "rf_wqfm_wrt_base",
    "rf_quantum_wrt_base",
    "better",
    "wqfm_bipartition_time_seconds",
    "quantum_qpu_access_time_seconds",
    "quantum_bruteforce_time_seconds",
    "quantum_time_seconds",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quartet-file", required=True)
    model = parser.add_mutually_exclusive_group(required=True)
    model.add_argument("--model-tree")
    model.add_argument("--model-tree-file")
    parser.add_argument("--wqfm-tree", required=True)
    parser.add_argument("--quantum-tree", required=True)
    parser.add_argument("--wqfm-log", required=True)
    parser.add_argument("--quantum-log", required=True)
    parser.add_argument("--rf-script", required=True)
    parser.add_argument("--output-csv", required=True)
    return parser.parse_args()


def load_rf_module(path):
    spec = importlib.util.spec_from_file_location("benchmark_robinson_foulds", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load RF module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_tree(path):
    lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Tree file is empty: {path}")
    tree = lines[0]
    return tree if tree.endswith(";") else tree + ";"


def leaf_labels(tree):
    return {leaf.taxon.label for leaf in tree.leaf_node_iter()}


def rf_distance(rf_module, model_newick, candidate_newick):
    namespace = rf_module.dendropy.TaxonNamespace()
    model = rf_module.dendropy.Tree.get(
        data=model_newick, schema="newick", taxon_namespace=namespace
    )
    candidate = rf_module.dendropy.Tree.get(
        data=candidate_newick, schema="newick", taxon_namespace=namespace
    )
    model_taxa = leaf_labels(model)
    candidate_taxa = leaf_labels(candidate)
    if model_taxa != candidate_taxa:
        missing = sorted(model_taxa - candidate_taxa)
        extra = sorted(candidate_taxa - model_taxa)
        raise ValueError(
            f"Tree taxa differ from base tree; missing={missing}, extra={extra}"
        )
    return rf_module.robinson_foulds_distance(model, candidate)


def sum_wqfm_bipartition_seconds(log_path):
    text = Path(log_path).read_text(errors="replace")
    values = re.findall(
        r"BENCHMARK_BIPARTITION_TIME_NS\s+algorithm=1\b[^\r\n]*?duration_ns=(\d+)",
        text,
    )
    if not values:
        raise ValueError(f"No Algorithm 1 bipartition timing markers in {log_path}")
    return sum(int(value) for value in values) / 1_000_000_000.0


def sum_quantum_qpu_seconds(log_path):
    text = Path(log_path).read_text(errors="replace")
    values = re.findall(r"['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)", text)
    if not values:
        raise ValueError(f"No D-Wave qpu_access_time values in {log_path}")
    # D-Wave reports qpu_access_time in microseconds.
    return sum(float(value) for value in values) / 1_000_000.0


def sum_quantum_bruteforce_seconds(log_path):
    text = Path(log_path).read_text(errors="replace")
    values = re.findall(
        r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)", text
    )
    if not values:
        raise ValueError(f"No Algorithm 2 brute-force timing markers in {log_path}")
    return sum(int(value) for value in values) / 1_000_000_000.0


def upsert_csv(output_path, row):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if output.exists() and output.stat().st_size:
        with output.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDNAMES:
                raise ValueError(
                    f"Unexpected CSV columns in {output}: {reader.fieldnames}"
                )
            rows = list(reader)

    rows = [item for item in rows if item["quartet_file_name"] != row["quartet_file_name"]]
    rows.append(row)
    rows.sort(key=lambda item: item["quartet_file_name"])

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


def main():
    args = parse_args()
    rf_module = load_rf_module(args.rf_script)
    if args.model_tree_file:
        # Species-tree files may include branch lengths. DendroPy parses those
        # lengths, while Robinson-Foulds comparison uses topology only.
        model_tree = read_tree(args.model_tree_file)
    else:
        model_tree = args.model_tree.strip()
        if not model_tree.endswith(";"):
            model_tree += ";"
    wqfm_tree = read_tree(args.wqfm_tree)
    quantum_tree = read_tree(args.quantum_tree)

    rf_wqfm = rf_distance(rf_module, model_tree, wqfm_tree)
    rf_quantum = rf_distance(rf_module, model_tree, quantum_tree)
    if math.isclose(rf_wqfm, rf_quantum, rel_tol=0.0, abs_tol=1e-12):
        better = 0
    elif rf_quantum < rf_wqfm:
        better = 1
    else:
        better = -1

    quantum_qpu_seconds = sum_quantum_qpu_seconds(args.quantum_log)
    quantum_bruteforce_seconds = sum_quantum_bruteforce_seconds(args.quantum_log)
    quantum_seconds = quantum_qpu_seconds + quantum_bruteforce_seconds

    row = {
        "quartet_file_name": Path(args.quartet_file).name,
        "wqfm_tree": wqfm_tree,
        "quantum_annealing_tree": quantum_tree,
        "rf_wqfm_wrt_base": f"{rf_wqfm:.12f}",
        "rf_quantum_wrt_base": f"{rf_quantum:.12f}",
        "better": str(better),
        "wqfm_bipartition_time_seconds": f"{sum_wqfm_bipartition_seconds(args.wqfm_log):.9f}",
        "quantum_qpu_access_time_seconds": f"{quantum_qpu_seconds:.9f}",
        "quantum_bruteforce_time_seconds": f"{quantum_bruteforce_seconds:.9f}",
        "quantum_time_seconds": f"{quantum_seconds:.9f}",
    }
    upsert_csv(args.output_csv, row)
    print(
        f"  CSV row: RF WQFM={rf_wqfm:.6f}, RF quantum={rf_quantum:.6f}, "
        f"better={better}"
    )


if __name__ == "__main__":
    main()
