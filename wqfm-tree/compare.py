#!/usr/bin/env python3
"""wQFM-TREE (official) vs QUANTA's QUBO inside wQFM-TREE, from gene trees to
species tree, on data/<n>_taxa.

  wqfm-tree  official/wQFM-TREE/run.sh: tree cleaning, PAUP* greedy consensus
             (initial bipartitions), FM bipartitions
  quanta     quanta-tree (wQFM-TREE source + QFMQubo): the same divide and
             conquer, each bipartition from QUANTA's QUBO built from the gene
             trees, solved by exhaustive search (<= 20 units) or simulated
             annealing (> 20 units, 1000 reads); no consensus, no FM

Both are single-threaded. Wall-clock time and peak memory come from
/usr/bin/time; RF is the normalised Robinson-Foulds distance to the true
species tree. Finished runs are reused. Writes results/compare.csv.
Usage: python compare.py [--taxa 200 500 1000]
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
from pathlib import Path

import dendropy
from dendropy.calculate import treecompare

HERE = Path(__file__).resolve().parent
PYTHON = HERE.parent / "QWQFM" / ".venv" / "bin" / "python"
OFFICIAL = HERE / "official" / "wQFM-TREE"
QUANTA = HERE / "quanta-tree"
# JVM options for both methods; None keeps the defaults (run.sh's own, -Xmx4g for QUANTA)
JAVA_OPTS = None


def timed(cmd, cwd, log, env=None):
    time_file = log.with_suffix(".time")
    with log.open("w") as handle:
        subprocess.run(["/usr/bin/time", "-f", "%e %M", "-o", str(time_file), *cmd], cwd=cwd,
                       stdout=handle, stderr=subprocess.STDOUT, check=True, env=env)
    wall, rss_kb = time_file.read_text().split()[-2:]
    return float(wall), int(rss_kb) / 1024


def rf(species_path, tree_path):
    taxa = dendropy.TaxonNamespace()
    true = dendropy.Tree.get(path=str(species_path), schema="newick", taxon_namespace=taxa, rooting="force-unrooted")
    est = dendropy.Tree.get(path=str(tree_path), schema="newick", taxon_namespace=taxa, rooting="force-unrooted")
    n = len(true.leaf_nodes())
    if len(est.leaf_nodes()) != n:
        raise ValueError(f"{tree_path} has {len(est.leaf_nodes())} leaves, expected {n}")
    return treecompare.symmetric_difference(true, est) / (2 * (n - 3))


def run(n, methods):
    run_dir = HERE / "runs" / f"{n}_taxa"
    run_dir.mkdir(parents=True, exist_ok=True)
    genes = run_dir / "gene_trees.tre"
    if not genes.exists():
        shutil.copy(HERE / "data" / f"{n}_taxa" / "gene_trees.tre", genes)
    species = HERE / "data" / f"{n}_taxa" / "species_tree.tre"
    rows = []
    if "quanta" in methods:
        rows += run_quanta(n, run_dir, genes, species)
    if "wqfm-tree" in methods:
        rows += run_wqfm_tree(n, run_dir, genes, species)
    for row in rows:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    return rows


def run_wqfm_tree(n, run_dir, genes, species):
    out = run_dir / "wqfmtree.tre"
    log = run_dir / "wqfmtree.log"
    if not out.exists():
        print(f"[{n}] wQFM-TREE ...", flush=True)
        env = dict(os.environ, JAVA_TOOL_OPTIONS=" ".join(JAVA_OPTS)) if JAVA_OPTS else None
        timed(["bash", "run.sh", str(genes), str(out)], OFFICIAL, log, env=env)
    wall, rss = map(float, (log.with_suffix(".time")).read_text().split()[-2:])
    java_ms = int(re.search(r"Elapsed Time taken = (\d+) ms", log.read_text()).group(1))
    return [{"taxa": n, "method": "wQFM-TREE (FM)", "rf": rf(species, out), "wall_s": wall,
             "core_s": java_ms / 1000, "peak_mem_mb": rss / 1024,
             "note": "wall = cleaning + PAUP* consensus + Java; core = Java (FM divide and conquer)"}]


def run_quanta(n, run_dir, genes, species):
    out = run_dir / "quanta.tre"
    log = run_dir / "quanta.log"
    if not out.exists():
        print(f"[{n}] QUANTA in wQFM-TREE ...", flush=True)
        env = dict(os.environ, QUBO_SOLVER_PYTHON=str(PYTHON), QUBO_SOLVER_SCRIPT=str(QUANTA / "qubo_solver.py"),
                   QUBO_SOLVER_LOG=str(run_dir / "quanta_solver.log"), OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        timed(["java", *(JAVA_OPTS or ["-Xmx4g"]), "-cp", str(QUANTA / "build"), "src.Main", str(genes), "-", str(out),
               "A", "QUBO"],
              QUANTA, log, env=env)
    wall, rss = map(float, (log.with_suffix(".time")).read_text().split()[-2:])
    summary = dict(re.findall(r"(\w+)=([\d.]+)", re.search(r"QUBO_SUMMARY .*", log.read_text()).group(0)))
    solver_log = (run_dir / "quanta_solver.log").read_text()
    sa_s = sum(int(v) for v in re.findall(r"SIMULATED_ANNEALING_TIME_NS n=\d+ duration_ns=(\d+)", solver_log)) / 1e9
    bf_s = sum(int(v) for v in re.findall(r"QUANTUM_BRUTE_FORCE_TIME_NS n=\d+ duration_ns=(\d+)", solver_log)) / 1e9
    return [{"taxa": n, "method": "QUANTA in wQFM-TREE (QUBO: SA / exhaustive)", "rf": rf(species, out),
             "wall_s": wall, "core_s": float(summary["elapsed_s"]), "peak_mem_mb": rss / 1024,
             "subproblems": summary["subproblems"], "qubo_build_s": summary["qubo_build_s"],
             "sa_s": round(sa_s, 3), "exhaustive_s": round(bf_s, 3),
             "sa_calls": solver_log.count("SIMULATED_ANNEALING_TIME_NS"),
             "fallbacks": solver_log.count("balanced fallback"),
             "note": "wall = Java + Python solver process (peak memory of the Java process)"}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxa", type=int, nargs="+", default=[200, 500, 1000])
    parser.add_argument("--methods", nargs="+", choices=["quanta", "wqfm-tree"], default=["quanta", "wqfm-tree"])
    args = parser.parse_args()
    out = HERE / "results" / "compare.csv"
    existing = {}
    if out.exists():
        with out.open() as handle:
            existing = {(r["taxa"], r["method"]): r for r in csv.DictReader(handle)}
    fields = ["taxa", "method", "rf", "wall_s", "core_s", "peak_mem_mb", "subproblems", "qubo_build_s",
              "sa_s", "exhaustive_s", "sa_calls", "fallbacks", "note"]
    out.parent.mkdir(exist_ok=True)
    for n in args.taxa:
        for row in run(n, args.methods):
            existing[(str(row["taxa"]), row["method"])] = {k: (f"{v:.4f}" if isinstance(v, float) else v)
                                                            for k, v in row.items()}
        # saved after every dataset, so a stopped run keeps the finished ones
        rows = sorted(existing.values(), key=lambda r: (int(r["taxa"]), r["method"]))
        with out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {out}", flush=True)


if __name__ == "__main__":
    main()
