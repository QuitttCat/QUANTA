#!/usr/bin/env python3
"""Score one wQFM / wQ²A (simulated annealing) pair and upsert its CSV row:
both trees, both RF distances to the true tree, both end-to-end times."""

import argparse
import csv
import importlib.util
import os
import re
import tempfile
from pathlib import Path

FIELDNAMES = [
    "quartet_file_name",
    "wqfm_tree",
    "wq2a_sa_tree",
    "rf_wqfm_wrt_base",
    "rf_wq2a_sa_wrt_base",
    "wqfm_end_to_end_seconds",
    "wq2a_sa_end_to_end_seconds",
]
END_TO_END = re.compile(r"Time taken = (\d+) ms")


def parse_args():
    parser = argparse.ArgumentParser()
    for name in ["quartet-file", "model-tree-file", "wqfm-tree", "sa-tree",
                 "wqfm-log", "sa-log", "rf-script", "output-csv"]:
        parser.add_argument(f"--{name}", required=True)
    return parser.parse_args()


def read_tree(path):
    lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Tree file is empty: {path}")
    return lines[0] if lines[0].endswith(";") else lines[0] + ";"


def end_to_end_seconds(log_path):
    matches = END_TO_END.findall(Path(log_path).read_text(errors="replace"))
    if not matches:
        raise ValueError(f"No 'Time taken' line in {log_path}")
    return int(matches[-1]) / 1000


def rf_distance(rf, model_newick, candidate_newick):
    namespace = rf.dendropy.TaxonNamespace()
    model = rf.dendropy.Tree.get(data=model_newick, schema="newick", taxon_namespace=namespace)
    candidate = rf.dendropy.Tree.get(data=candidate_newick, schema="newick", taxon_namespace=namespace)
    model_taxa = {leaf.taxon.label for leaf in model.leaf_node_iter()}
    candidate_taxa = {leaf.taxon.label for leaf in candidate.leaf_node_iter()}
    if model_taxa != candidate_taxa:
        raise ValueError(f"Tree taxa differ from the true tree: {sorted(model_taxa ^ candidate_taxa)}")
    return rf.robinson_foulds_distance(model, candidate)


def upsert_csv(output_path, row):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if output.exists() and output.stat().st_size:
        with output.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDNAMES:
                raise ValueError(f"Unexpected CSV columns in {output}: {reader.fieldnames}")
            rows = list(reader)
    rows = [r for r in rows if r["quartet_file_name"] != row["quartet_file_name"]] + [row]
    rows.sort(key=lambda r: r["quartet_file_name"])
    fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, output)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main():
    args = parse_args()
    spec = importlib.util.spec_from_file_location("benchmark_robinson_foulds", args.rf_script)
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)

    model = read_tree(args.model_tree_file)
    wqfm_tree, sa_tree = read_tree(args.wqfm_tree), read_tree(args.sa_tree)
    row = {
        "quartet_file_name": Path(args.quartet_file).name,
        "wqfm_tree": wqfm_tree,
        "wq2a_sa_tree": sa_tree,
        "rf_wqfm_wrt_base": f"{rf_distance(rf, model, wqfm_tree):.12f}",
        "rf_wq2a_sa_wrt_base": f"{rf_distance(rf, model, sa_tree):.12f}",
        "wqfm_end_to_end_seconds": f"{end_to_end_seconds(args.wqfm_log):.3f}",
        "wq2a_sa_end_to_end_seconds": f"{end_to_end_seconds(args.sa_log):.3f}",
    }
    upsert_csv(args.output_csv, row)
    print(f"  CSV row: RF wQFM={float(row['rf_wqfm_wrt_base']):.4f}, RF wQ2A-SA={float(row['rf_wq2a_sa_wrt_base']):.4f}, "
          f"time wQFM={row['wqfm_end_to_end_seconds']}s, wQ2A-SA={row['wq2a_sa_end_to_end_seconds']}s")


if __name__ == "__main__":
    main()
