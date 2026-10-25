#!/usr/bin/env python3
"""Score one WQFM/bruteforce pair for the 11-taxon dataset and upsert its CSV row.

Unlike the 37/48-taxa scorer, this dataset never crosses the n>20 QPU
threshold (max partition size is 11), so Algorithm 2 is pure brute force --
there is no QPU timing to record and no D-Wave token involved. The CSV only
carries the tree topologies and their RF distances to the true tree.
"""

import argparse
import csv
import importlib.util
import os
from pathlib import Path
import tempfile


FIELDNAMES = [
    "quartet_file_name",
    "wqfm_tree",
    "bruteforce_tree",
    "rf_wqfm_wrt_base",
    "rf_bruteforce_wrt_base",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quartet-file", required=True)
    parser.add_argument("--model-tree-file", required=True)
    parser.add_argument("--wqfm-tree", required=True)
    parser.add_argument("--bruteforce-tree", required=True)
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

    model_tree = read_tree(args.model_tree_file)
    wqfm_tree = read_tree(args.wqfm_tree)
    bruteforce_tree = read_tree(args.bruteforce_tree)

    rf_wqfm = rf_distance(rf_module, model_tree, wqfm_tree)
    rf_bruteforce = rf_distance(rf_module, model_tree, bruteforce_tree)

    row = {
        "quartet_file_name": Path(args.quartet_file).name,
        "wqfm_tree": wqfm_tree,
        "bruteforce_tree": bruteforce_tree,
        "rf_wqfm_wrt_base": f"{rf_wqfm:.12f}",
        "rf_bruteforce_wrt_base": f"{rf_bruteforce:.12f}",
    }
    upsert_csv(args.output_csv, row)
    print(f"  CSV row: RF WQFM={rf_wqfm:.6f}, RF bruteforce={rf_bruteforce:.6f}")


if __name__ == "__main__":
    main()
