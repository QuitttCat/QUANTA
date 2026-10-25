#!/usr/bin/env python3
"""Collect classical-solver runs (run_classical_benchmark.sh) into one CSV, in
the same layout as the QPU run's CSV.

RF distances use the benchmark scorer (score_benchmark_row.py) and the model
tree of the dataset's benchmark script (--model-tree-script). wQFM columns are
copied from the QPU run's CSV (wQFM is deterministic).
"""

import argparse
import csv
import importlib.util
import math
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
LABELS = {"sa": ("simulated_annealing", "SIMULATED_ANNEALING"), "tabu": ("tabu_search", "TABU_SEARCH")}


def load_scorer():
    spec = importlib.util.spec_from_file_location("score_benchmark_row", SCRIPTS / "score_benchmark_row.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_tree(script):
    text = Path(script).read_text()
    tree = re.search(r'MODEL_TREE="\$\{MODEL_TREE:-([^}]*)\}"', text).group(1).strip()
    return tree if tree.endswith(";") else tree + ";"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True, choices=sorted(LABELS))
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--model-tree-script", required=True,
                        help="benchmark script whose MODEL_TREE default is the true tree")
    parser.add_argument("--qpu-csv", required=True, help="QPU run CSV, for the wQFM columns")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    name, marker = LABELS[args.solver]
    scorer = load_scorer()
    rf_module = scorer.load_rf_module(SCRIPTS.parent / "robinson_foulds.py")
    model = model_tree(args.model_tree_script)
    with open(args.qpu_csv, newline="") as handle:
        wqfm = {row["quartet_file_name"]: row for row in csv.DictReader(handle)}

    rows = []
    for result_dir in sorted(Path(args.work_dir).iterdir()):
        if not (result_dir / "quantum.done").exists():
            continue
        tree = scorer.read_tree(result_dir / "quantum.tre")
        log = (result_dir / "quantum.log").read_text(errors="replace")
        sampler_ns = [int(v) for v in re.findall(rf"{marker}_TIME_NS n=\d+ duration_ns=(\d+)", log)]
        sampler_seconds = sum(sampler_ns) / 1e9
        bruteforce_seconds = scorer.sum_quantum_bruteforce_seconds(result_dir / "quantum.log")
        base = wqfm[result_dir.name]
        rf_wqfm = float(base["rf_wqfm_wrt_base"])
        rf = scorer.rf_distance(rf_module, model, tree)
        better = 0 if math.isclose(rf, rf_wqfm, abs_tol=1e-12) else (1 if rf < rf_wqfm else -1)
        rows.append({
            "quartet_file_name": result_dir.name,
            "wqfm_tree": base["wqfm_tree"],
            f"{name}_tree": tree,
            "rf_wqfm_wrt_base": base["rf_wqfm_wrt_base"],
            f"rf_{name}_wrt_base": f"{rf:.12f}",
            "better": str(better),
            "wqfm_bipartition_time_seconds": base["wqfm_bipartition_time_seconds"],
            f"{name}_sampler_time_seconds": f"{sampler_seconds:.9f}",
            f"{name}_bruteforce_time_seconds": f"{bruteforce_seconds:.9f}",
            f"{name}_time_seconds": f"{sampler_seconds + bruteforce_seconds:.9f}",
            f"{name}_sampler_calls": str(len(sampler_ns)),
            f"{name}_fallbacks": str(log.count("balanced fallback")),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
