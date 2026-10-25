#!/usr/bin/env python3
"""Recover the true species trees used to score the 11-, 15-, 37- and 48-taxon
wQFM / wQ2A runs, and verify them against the stored RF values.

- 37 and 48 taxa: the true tree is the MODEL_TREE default in the benchmark scripts.
- 11 and 15 taxa: a wQFM tree with stored RF = 0 is the true tree (RF 0 means
  identical unrooted topology). 11-taxon estimated_* and simulated_* files use
  different taxon labels, so each gets its own tree.

Every candidate is accepted only if recomputing RF for every stored wQFM tree
reproduces the stored RF value. Writes baselines/references/<name>.tre.
"""

import csv
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "baselines" / "references"
RESULTS = REPO / "result_analysis"
SCRIPTS = REPO / "QWQFM" / "benchmark" / "scripts"

spec = importlib.util.spec_from_file_location("rf", REPO / "QWQFM" / "benchmark" / "robinson_foulds.py")
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)


def rf_distance(a, b):
    ns = rf.dendropy.TaxonNamespace()
    ta = rf.dendropy.Tree.get(data=a, schema="newick", taxon_namespace=ns)
    tb = rf.dendropy.Tree.get(data=b, schema="newick", taxon_namespace=ns)
    return rf.robinson_foulds_distance(ta, tb)


def script_model_tree(script):
    match = re.search(r'MODEL_TREE="\$\{MODEL_TREE:-([^}]*)\}"', (SCRIPTS / script).read_text())
    tree = match.group(1).strip()
    return tree if tree.endswith(";") else tree + ";"


def rows(csv_path):
    with open(csv_path) as handle:
        return list(csv.DictReader(handle))


def from_zero_rf(table, prefix=""):
    zero = [r["wqfm_tree"] for r in table
            if r["quartet_file_name"].startswith(prefix) and float(r["rf_wqfm_wrt_base"]) == 0]
    if not zero:
        raise SystemExit(f"no RF-0 wQFM tree with prefix {prefix!r}")
    return zero[0] if zero[0].endswith(";") else zero[0] + ";"


def verify(name, reference, table, prefix=""):
    checked = 0
    for r in table:
        if not r["quartet_file_name"].startswith(prefix):
            continue
        tree = r["wqfm_tree"] if r["wqfm_tree"].endswith(";") else r["wqfm_tree"] + ";"
        if abs(rf_distance(reference, tree) - float(r["rf_wqfm_wrt_base"])) > 1e-9:
            raise SystemExit(f"{name}: RF mismatch for {r['quartet_file_name']}")
        checked += 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.tre").write_text(reference + "\n")
    print(f"{name}: verified against {checked} stored RF values -> {OUT / (name + '.tre')}")


def main():
    t11 = rows(RESULTS / "11 Taxa" / "result" / "results_11_taxa.csv")
    verify("11_estimated", from_zero_rf(t11, "estimated_"), t11, "estimated_")
    verify("11_simulated", from_zero_rf(t11, "simulated_"), t11, "simulated_")
    t15 = rows(RESULTS / "15 Taxa" / "result" / "results_15_taxa.csv")
    verify("15", from_zero_rf(t15), t15)
    verify("37", script_model_tree("run_37_taxa_benchmark.sh"),
           rows(RESULTS / "37 Taxa" / "result" / "results_37_taxa_qpu_plus_bruteforce_n>20.csv"))
    verify("48", script_model_tree("run_48_taxa_z12_benchmark.sh"),
           rows(RESULTS / "48 Taxa" / "result" / "results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv"))


if __name__ == "__main__":
    main()
