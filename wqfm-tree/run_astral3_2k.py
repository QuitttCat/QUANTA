#!/usr/bin/env python3
"""QUANTA in wQFM-TREE (and optionally wQFM-TREE) on the ASTRAL-III 2000-taxon
dataset used by the wQFM-TREE paper: replicate 2k.01, 2001 taxa, 1000 true
gene trees (data/astral3_2k_rep01, prepared from large.tar.gz of
gitlab.com/esayyari/ASTRALIII).

The archive has no true species tree, so RF is measured against ASTRAL-III's
estimated tree for the same replicate. Runs go to runs/astral3_2k_rep01/,
results to results/compare_astral3_2k.csv.
Usage: python run_astral3_2k.py [--methods quanta wqfm-tree]
"""

import argparse
import csv
import shutil

import compare

NAME = "astral3_2k_rep01"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", nargs="+", choices=["quanta", "wqfm-tree"], default=["quanta"])
    args = parser.parse_args()
    data = compare.HERE / "data" / NAME
    run_dir = compare.HERE / "runs" / NAME
    run_dir.mkdir(parents=True, exist_ok=True)
    genes = run_dir / "gene_trees.tre"
    if not genes.exists():
        shutil.copy(data / "gene_trees.tre", genes)
    reference = data / "astral3_tree.tre"

    out = compare.HERE / "results" / "compare_astral3_2k.csv"
    existing = {}
    if out.exists():
        with out.open() as handle:
            existing = {r["method"]: r for r in csv.DictReader(handle)}
    for method in args.methods:
        runner = compare.run_quanta if method == "quanta" else compare.run_wqfm_tree
        for row in runner(2001, run_dir, genes, reference):
            row["rf_to_astral3"] = row.pop("rf")
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
            existing[row["method"]] = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()}
        fields = ["taxa", "method", "rf_to_astral3", "wall_s", "core_s", "peak_mem_mb", "subproblems",
                  "qubo_build_s", "sa_s", "exhaustive_s", "sa_calls", "fallbacks", "note"]
        with out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing.values())
        print(f"Saved {out}", flush=True)


if __name__ == "__main__":
    main()
