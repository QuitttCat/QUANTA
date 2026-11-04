#!/usr/bin/env python3
"""Root bipartition of QUANTA's QUBO, built from gene trees, solved with
QUANTA's own solver routes, and scored against the true species tree.

For each dataset in data/<n>_taxa/:
  1. build the QUBO from the gene trees (gene_tree_qubo.py, no quartet list);
  2. solve it with one of
       sa           simulated annealing exactly as QUANTA's SA runs:
                    qaoa_classical.classical_annealing (dwave-samplers,
                    1000 reads, lowest-energy sample with at least two taxa
                    per side, balanced fallback)
       leap-hybrid  D-Wave as QUANTA does above 150 taxa:
                    qaoa.leap_hybrid_annealing (30 s). A dense QUBO of 200+
                    variables cannot be embedded on the QPU directly;
  3. compare the bipartition with every split of the true species tree:
     is it a true split, how many taxa are away from the nearest one, and its
     energy and quartet score (satisfied - violated, wQFM-TREE's objective)
     against the best true split.

--reference-only skips step 2.
Writes results/root_bipartition_<n>_taxa_<solver>.json and results/summary_<solver>.csv.
Usage: python solve_root.py [--taxa 200 500 1000] [--solver sa|leap-hybrid] [--reference-only]
"""

import argparse
import contextlib
import csv
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import dendropy
import numpy as np

from gene_tree_qubo import build_qubo, quartet_counts, read_gene_trees

HERE = Path(__file__).resolve().parent
import qaoa  # noqa: E402  (path added by gene_tree_qubo)

RESULT_KEY = {"sa": "simulated_annealing", "leap-hybrid": "quantum_annealing", "reference": None}


def species_splits(path, labels):
    """Non-trivial splits (both sides >= 2) of the unrooted species tree, as 0/1 rows."""
    index = {label: i for i, label in enumerate(labels)}
    n = len(labels)
    tree = dendropy.Tree.get(path=str(path), schema="newick", rooting="force-unrooted")
    leaves, seen, rows = {}, set(), []
    for node in tree.postorder_node_iter():
        if node.is_leaf():
            leaves[node] = [index[node.taxon.label]]
        else:
            leaves[node] = [i for c in node.child_nodes() for i in leaves[c]]
        if node is tree.seed_node or not 2 <= len(leaves[node]) <= n - 2:
            continue
        row = np.zeros(n, dtype=np.int8)
        row[leaves[node]] = 1
        if row[0]:
            row = 1 - row  # canonical side: the one without taxon 0
        key = row.tobytes()
        if key not in seen:
            seen.add(key)
            rows.append(row)
    return np.array(rows)


def energies(X, Q):
    X = X.astype(float)
    return ((X @ Q) * X).sum(axis=1)


def score(x, pair, cross, k):
    s, d, v = quartet_counts(x, pair, cross, k)
    return {"satisfied": s, "deferred": d, "violated": v, "s_minus_v": s - v,
            "satisfied_fraction_of_2_2": s / (s + v) if s + v else 0.0}


def captured(fn, *args, **kwargs):
    """Run a qaoa solver function, echoing and returning its log."""
    log = io.StringIO()
    start = time.time()
    with contextlib.redirect_stdout(log):
        x, energy = fn(*args, **kwargs)
    wall = time.time() - start
    sys.stdout.write(log.getvalue())
    return np.asarray(x, dtype=np.int8), float(energy), wall, log.getvalue()


def solve_leap_hybrid(Q, time_limit):
    x, energy, wall, text = captured(qaoa.leap_hybrid_annealing, Q, time_limit=time_limit, min_partition_size=2)
    timing = {}
    for key in ("qpu_access_time", "run_time", "charge_time"):
        match = re.search(rf"['\"]{key}['\"]\s*:\s*(\d+(?:\.\d+)?)", text)
        if match:
            timing[f"{key}_s"] = float(match.group(1)) / 1e6
    problem = re.search(r"LEAP_HYBRID problem ID: (\S+)", text)
    return x, energy, {"solver": "D-Wave Leap Hybrid BQM (qaoa.leap_hybrid_annealing, "
                                 f"time_limit={time_limit:g} s)",
                       "wall_s": round(wall, 3), **timing,
                       "problem_id": problem.group(1) if problem else None,
                       "fallback": "balanced fallback" in text}


def solve_sa(Q, reads):
    # qaoa_classical reads its settings from the environment when imported.
    os.environ["WQ2A_CLASSICAL_SOLVER"] = "sa"
    os.environ["WQ2A_CLASSICAL_READS"] = str(reads)
    import qaoa_classical

    x, energy, wall, text = captured(qaoa_classical.classical_annealing, Q, Q.shape[0])
    sampler_ns = re.search(r"SIMULATED_ANNEALING_TIME_NS n=\d+ duration_ns=(\d+)", text)
    rank = re.search(r"selected sample rank: (\d+)", text)
    return x, energy, {"solver": "simulated annealing (qaoa_classical.classical_annealing, dwave-samplers, "
                                 f"{reads} reads, 1000 sweeps)",
                       "wall_s": round(wall, 3),
                       "sampler_s": int(sampler_ns.group(1)) / 1e9 if sampler_ns else None,
                       "selected_sample_rank": int(rank.group(1)) if rank else None,
                       "fallback": "balanced fallback" in text}


def write_summary(out_dir, solver):
    """Collect every dataset's JSON for this solver (runs may be separate processes)."""
    key = RESULT_KEY[solver]
    rows = []
    for path in sorted(out_dir.glob(f"root_bipartition_*_taxa_{solver}.json"),
                       key=lambda p: int(p.name.split("_")[2])):
        r = json.loads(path.read_text())
        s = r.get(key) or {}
        rows.append({
            "taxa": r["taxa"], "genes": r["genes"], "qubo_build_seconds": r["qubo_build_seconds"],
            "best_true_split_energy": f"{r['best_true_split']['energy']:.1f}",
            "best_true_split_sizes": "/".join(map(str, r["best_true_split"]["sizes"])),
            "best_true_split_satisfied_fraction": f"{r['best_true_split']['satisfied_fraction_of_2_2']:.4f}",
            "solver_energy": f"{s['energy']:.1f}" if s else "",
            "solver_sizes": "/".join(map(str, s["sizes"])) if s else "",
            "solver_is_true_split": s.get("is_true_species_split", ""),
            "solver_taxa_from_nearest_true_split": s.get("taxa_from_nearest_true_split", ""),
            "solver_energy_minus_best_true_split": f"{s['energy_minus_best_true_split']:.1f}" if s else "",
            "solver_satisfied_fraction": f"{s['satisfied_fraction_of_2_2']:.4f}" if s else "",
            "solver_wall_s": s.get("wall_s", ""),
            "solver_time_s": s.get("sampler_s", s.get("qpu_access_time_s", "")),
        })
    out = out_dir / f"summary_{solver}.csv"
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out} ({len(rows)} datasets)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxa", type=int, nargs="+", default=[200, 500, 1000])
    parser.add_argument("--solver", choices=["sa", "leap-hybrid"], default="sa")
    parser.add_argument("--reads", type=int, default=1000, help="SA reads, as in QUANTA's SA runs")
    parser.add_argument("--time-limit", type=float, default=30.0, help="Leap Hybrid time limit (s), as in QUANTA")
    parser.add_argument("--reference-only", action="store_true", help="no solver; species-tree reference only")
    args = parser.parse_args()
    solver = "reference" if args.reference_only else args.solver
    if solver == "leap-hybrid" and not os.environ.get("DWAVE_API_TOKEN"):
        sys.exit("Set DWAVE_API_TOKEN for --solver leap-hybrid")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    for n in args.taxa:
        data = HERE / "data" / f"{n}_taxa"
        start = time.time()
        trees, labels = read_gene_trees(data / "gene_trees.tre")
        Q, pair, cross = build_qubo(trees, labels)
        build_s = time.time() - start
        k = len(trees)

        splits = species_splits(data / "species_tree.tre", labels)
        split_energy = energies(splits, Q)
        best = int(np.argmin(split_energy))
        best_score = max((score(row, pair, cross, k) for row in splits), key=lambda s: s["s_minus_v"])
        result = {
            "taxa": n, "genes": k, "qubo_variables": n, "qubo_nonzero_couplings": int(np.count_nonzero(np.triu(Q, 1))),
            "qubo_build_seconds": round(build_s, 2),
            "species_tree_splits": len(splits),
            "best_true_split": {"energy": float(split_energy[best]),
                                "sizes": sorted([int(splits[best].sum()), int(n - splits[best].sum())]),
                                **score(splits[best], pair, cross, k)},
            "best_true_split_by_s_minus_v": best_score,
        }
        if solver != "reference":
            print(f"\n=== {n} taxa: {solver} ===", flush=True)
            if solver == "sa":
                x, energy, info = solve_sa(Q, args.reads)
            else:
                x, energy, info = solve_leap_hybrid(Q, args.time_limit)
            canonical = 1 - x if x[0] else x
            mismatches = (splits != canonical).sum(axis=1)
            nearest = int(np.minimum(mismatches, n - mismatches).min())
            result[RESULT_KEY[solver]] = {
                "solver": info.pop("solver"),
                "energy": energy, "energy_recomputed": float(x.astype(float) @ Q @ x.astype(float)),
                "sizes": sorted([int(x.sum()), int(n - x.sum())]),
                "is_true_species_split": nearest == 0,
                "taxa_from_nearest_true_split": nearest,
                "energy_minus_best_true_split": energy - float(split_energy[best]),
                **score(x, pair, cross, k), **info,
                "left": [labels[i] for i in range(n) if x[i] == 0],
                "right": [labels[i] for i in range(n) if x[i] == 1],
            }
        (out_dir / f"root_bipartition_{n}_taxa_{solver}.json").write_text(json.dumps(result, indent=2) + "\n")
        brief = {key: value for key, value in (result.get(RESULT_KEY[solver]) or {}).items()
                 if key not in ("left", "right")}
        print(json.dumps({"taxa": n, "qubo_build_seconds": result["qubo_build_seconds"],
                          "best_true_split": result["best_true_split"], "solver": brief}, indent=2), flush=True)
    write_summary(out_dir, solver)


if __name__ == "__main__":
    main()
