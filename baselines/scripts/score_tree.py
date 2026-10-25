#!/usr/bin/env python3
"""Score one estimated tree the same way as the wQFM / wQ2A results.

- RF: normalized Robinson-Foulds distance to a reference tree, using
  QWQFM/benchmark/robinson_foulds.py (optional; only when --reference is given).
- Weighted quartet score: total weight of input quartets the tree displays,
  using the four-point test of QWQFM/benchmark/scripts/build_quartet_score_csvs.py.

Prints one JSON object with the scores.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QWQFM_BENCHMARK = REPO / "QWQFM" / "benchmark"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_tree(path):
    lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"empty tree file: {path}")
    return lines[-1] if lines[-1].endswith(";") else lines[-1] + ";"


def rf_distance(rf, reference, estimated):
    namespace = rf.dendropy.TaxonNamespace()
    ref = rf.dendropy.Tree.get(data=reference, schema="newick", taxon_namespace=namespace)
    est = rf.dendropy.Tree.get(data=estimated, schema="newick", taxon_namespace=namespace)
    ref_taxa = {leaf.taxon.label for leaf in ref.leaf_node_iter()}
    est_taxa = {leaf.taxon.label for leaf in est.leaf_node_iter()}
    if ref_taxa != est_taxa:
        raise ValueError(f"taxa differ from the reference: {sorted(ref_taxa ^ est_taxa)[:10]}")
    return rf.robinson_foulds_distance(ref, est)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, help="estimated tree file")
    parser.add_argument("--quartets", required=True, help="weighted quartet file the tree is scored on")
    parser.add_argument("--reference", help="reference tree file for RF (true species tree or input gene tree)")
    args = parser.parse_args()

    sys.path.insert(0, str(QWQFM_BENCHMARK / "scripts"))
    scorer = load_module("build_quartet_score_csvs", QWQFM_BENCHMARK / "scripts" / "build_quartet_score_csvs.py")

    tree = read_tree(args.tree)
    labels, distances = scorer.topological_distance_matrix(tree)
    with open(args.quartets) as handle:
        # dendropy reads unquoted underscores in tree labels as spaces
        # (e.g. the 144-taxon insect names), so match the quartet labels to that.
        lines = (line.replace("_", " ") for line in handle) if any(" " in label for label in labels) else handle
        count, total, score, _ = scorer.score_quartet_lines(lines, labels, distances, distances)

    result = {
        "tree": tree,
        "quartet_count": count,
        "total_quartet_weight": total,
        "weighted_quartet_score": score,
        "quartet_score_fraction": score / total if total else None,
    }
    if args.reference:
        rf = load_module("benchmark_robinson_foulds", QWQFM_BENCHMARK / "robinson_foulds.py")
        result["rf"] = rf_distance(rf, read_tree(args.reference), tree)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
