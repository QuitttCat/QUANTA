#!/usr/bin/env python3
"""Recreate the wQFM-TREE paper's ASTRAL-II results (medium ILS, 200 / 500 /
1000 taxa; 50, 200 and 1000 estimated gene trees) with QUANTA in wQFM-TREE,
and compare with wQFM-TREE.

  published  RF of the trees published in official/results/Astral_2_datasets
             (wQFM-TREE, TREE-QMC, ASTRAL-II) against the true species trees
             there, per replicate -> results/astral2_published.csv
  run        QUANTA in wQFM-TREE (and/or wQFM-TREE re-run here) on the
             ASTRAL-II estimated gene trees -> results/astral2_runs.csv
             (RF, wall time, peak memory, and QUANTA's time breakdown)

Gene trees are ASTRAL-II's estimated gene trees (Dryad doi:10.6076/D10C7C), as
cleaned and split into 50-, 200- and 1000-gene sets by the QUANTA group:
data/astral2_extracted/<taxa>-taxon/estimated-genetrees/<model>/<genes>-gt/R<i>/gt-cleaned.
Replicate R<i> is replicate <i> of the true species trees. Many gene trees have
polytomies; both methods get them unchanged, and comparing the wQFM-TREE
re-runs here with the published wQFM-TREE trees checks the setup.
Finished runs are reused, so the script can be stopped and restarted.

Usage:
  python astral2.py published
  python astral2.py run --methods quanta --jobs 3
  python astral2.py run --methods wqfm-tree --reps 01 02 03
  python astral2.py run --methods wqfm-tree quanta --taxa 500 --genes 1000 --jobs 1 \
      --reps 01 02 03 04 05 06 07 08 09 10 --java-opt=-Xmx5g --java-opt=-XX:+UseSerialGC
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import compare

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE / "official" / "results" / "Astral_2_datasets"
DATA = HERE / "data" / "astral2_extracted"
# short on purpose: PAUP* (wQFM-TREE's consensus step) rejects long file paths
RUNS = HERE / "runs" / "a2"
RESOLVED = False  # --resolved: polytomies resolved first, in runs/a2r, results in astral2_resolved_*.csv
MODELS = {200: "model.200.2000000.0.000001", 500: "model.500.2000000.0.000001",
          1000: "model.1000.2000000.0.000001"}
GENES = [1000, 200, 50]
# published output file per method and gene count
PUBLISHED_FILES = {
    ("wQFM-TREE", 1000): "ewqfm-paup-nq-A-tree.txt", ("wQFM-TREE", 200): "ewqfm-200-tree.txt",
    ("wQFM-TREE", 50): "ewqfm-50-tree.txt",
    ("TREE-QMC", 1000): "treeqmc-tree.txt", ("TREE-QMC", 200): "treeqmc-200-tree.txt",
    ("TREE-QMC", 50): "treeqmc-50-tree.txt",
    ("wQFM-TREE resolved", 1000): "ewqfm-with-resolved-gene-trees-tree.txt",
    ("wQFM-TREE resolved", 200): "ewqfm-200-resolved-tree.txt",
    ("wQFM-TREE resolved", 50): "ewqfm-50-resolved-tree.txt",
    ("ASTRAL-II", 1000): "astral2-tree.txt", ("ASTRAL-II", 200): "astral2-200-tree.txt",
    ("ASTRAL-II", 50): "astral2-50-tree.txt",
}


def replicates(model):
    return sorted(p.name for p in (PUBLISHED / "true-species-trees" / model).iterdir())


def species_tree(model, rep):
    return PUBLISHED / "true-species-trees" / model / rep / "sp-cleaned"


def write_csv(path, rows, fields):
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def published():
    rows = []
    for taxa, model in MODELS.items():
        for rep in replicates(model):
            for (method, genes), name in PUBLISHED_FILES.items():
                tree = PUBLISHED / "outputs" / model / rep / name
                if tree.exists():
                    rows.append({"taxa": taxa, "model": model, "rep": rep, "genes": genes, "method": method,
                                 "rf": f"{compare.rf(species_tree(model, rep), tree):.6f}"})
    write_csv(HERE / "results" / "astral2_published.csv", rows, ["taxa", "model", "rep", "genes", "method", "rf"])
    print(f"{len(rows)} published trees scored -> results/astral2_published.csv")


def gene_tree_source(taxa, model, rep, genes):
    """The replicate's estimated gene trees: <taxa>-taxon/estimated-genetrees/<model>/<genes>-gt/R<i>/gt-cleaned."""
    path = DATA / f"{taxa}-taxon" / "estimated-genetrees" / model / f"{genes}-gt" / f"R{int(rep)}" / "gt-cleaned"
    if not path.exists():
        raise FileNotFoundError(f"no estimated gene trees at {path}")
    return path


def prepare(taxa, model, rep, genes):
    """runs/a2[r]/m<taxa>/<rep>/g<genes>/gene_trees.tre: the gene trees, unchanged (polytomies kept) or,
    with --resolved, through the official pipeline of runResolvingPolytomy.sh (clean, resolve, clean)."""
    run_dir = RUNS / f"m{taxa}" / rep / f"g{genes}"
    target = run_dir / "gene_trees.tre"
    if target.exists():
        return run_dir, target
    run_dir.mkdir(parents=True, exist_ok=True)
    source = gene_tree_source(taxa, model, rep, genes)
    if RESOLVED:
        cleaned = run_dir / "input-cleaned"
        resolved = run_dir / "input-cleaned.resolved"
        with source.open() as stdin, cleaned.open("w") as stdout:
            subprocess.run(["python3", "./treeCleaner.py"], cwd=compare.OFFICIAL, stdin=stdin, stdout=stdout, check=True)
        start = time.time()
        subprocess.run([str(compare.PYTHON), "arb_resolve_polytomies.py", str(cleaned)], cwd=compare.OFFICIAL,
                       stdout=subprocess.DEVNULL, check=True)
        (run_dir / "resolve_seconds.txt").write_text(f"{time.time() - start:.1f}\n")
        tmp = target.with_suffix(".tmp")
        with resolved.open() as stdin, tmp.open("w") as stdout:
            subprocess.run(["python3", "./treeCleaner.py"], cwd=compare.OFFICIAL, stdin=stdin, stdout=stdout, check=True)
        lines = [line for line in tmp.read_text().splitlines() if line.strip()]
        cleaned.unlink()
        resolved.unlink()
        leaves = lines[0].count(",") + 1
        bad = [i for i, line in enumerate(lines) if line.count(",") + 1 != leaves or line.count("(") != leaves - 1]
        if bad:
            raise ValueError(f"{model}/{rep}: {len(bad)} trees are not fully resolved after resolving")
    else:
        lines = [line for line in source.read_text().splitlines() if line.strip()]
        tmp = target.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n")
    if len(lines) != genes:
        raise ValueError(f"{model}/{rep}: {len(lines)} gene trees, expected {genes}")
    os.replace(tmp, target)
    return run_dir, target


def run_one(job):
    taxa, model, rep, genes, method = job
    run_dir, gene_trees = prepare(taxa, model, rep, genes)
    runner = compare.run_quanta if method == "quanta" else compare.run_wqfm_tree
    rows = runner(taxa, run_dir, gene_trees, species_tree(model, rep))
    for row in rows:
        row.update({"model": model, "rep": rep, "genes": genes})
    return rows


def run(methods, reps, taxa_list, genes_list, jobs):
    out = HERE / "results" / ("astral2_resolved_runs.csv" if RESOLVED else "astral2_runs.csv")
    existing = {}
    if out.exists():
        with out.open() as handle:
            existing = {(r["model"], r["rep"], r["genes"], r["method"]): r for r in csv.DictReader(handle)}
    work = []
    for genes in genes_list:  # in the order given, so the main 1000-gene runs can go first
        for taxa in taxa_list:
            model = MODELS[taxa]
            for rep in replicates(model):
                if reps and rep not in reps:
                    continue
                for method in methods:
                    work.append((taxa, model, rep, genes, method))
    fields = ["taxa", "model", "rep", "genes", "method", "rf", "wall_s", "core_s", "peak_mem_mb", "subproblems",
              "qubo_build_s", "sa_s", "exhaustive_s", "sa_calls", "fallbacks"]
    print(f"{len(work)} runs, {jobs} at a time", flush=True)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_one, job): job for job in work}
        for done, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                rows = future.result()
            except Exception as error:  # keep going; the run is retried on the next invocation
                print(f"[{done}/{len(work)}] FAILED {job}: {error}", flush=True)
                continue
            for row in rows:
                row = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()}
                existing[(row["model"], row["rep"], str(row["genes"]), row["method"])] = row
                print(f"[{done}/{len(work)}] {row['taxa']} taxa rep {row['rep']} {row['genes']} genes "
                      f"{row['method']}: RF {row['rf']}, {row['wall_s']} s", flush=True)
            rows_sorted = sorted(existing.values(), key=lambda r: (int(r["taxa"]), r["rep"], int(r["genes"]),
                                                                   r["method"]))
            write_csv(out, rows_sorted, fields)
    print(f"Saved {out}")


def summary():
    """Mean over the replicates QUANTA ran: its RF and time, and the published
    wQFM-TREE / TREE-QMC / ASTRAL-II RF on the same replicates."""
    prefix = "astral2_resolved" if RESOLVED else "astral2"
    with (HERE / "results" / f"{prefix}_runs.csv").open() as handle:
        runs = [r for r in csv.DictReader(handle) if r["method"].startswith("QUANTA")]
    with (HERE / "results" / "astral2_published.csv").open() as handle:
        pub = {(r["model"], r["rep"], r["genes"], r["method"]): float(r["rf"]) for r in csv.DictReader(handle)}
    groups = {}
    for r in runs:
        groups.setdefault((int(r["taxa"]), int(r["genes"])), []).append(r)
    rows = []
    for (taxa, genes), rs in sorted(groups.items()):
        mean = lambda xs: sum(xs) / len(xs)
        row = {"taxa": taxa, "genes": genes, "replicates": len(rs),
               "quanta_rf": f"{mean([float(r['rf']) for r in rs]):.4f}",
               "quanta_wall_min": f"{mean([float(r['wall_s']) for r in rs]) / 60:.2f}",
               "quanta_wall_max_min": f"{max(float(r['wall_s']) for r in rs) / 60:.2f}",
               "quanta_peak_mem_mb": f"{max(float(r['peak_mem_mb']) for r in rs):.0f}"}
        for method, key in (("wQFM-TREE", "wqfm_tree_rf"), ("wQFM-TREE resolved", "wqfm_tree_resolved_rf"),
                            ("TREE-QMC", "tree_qmc_rf"), ("ASTRAL-II", "astral2_rf")):
            vals = [pub[(r["model"], r["rep"], str(genes), method)] for r in rs
                    if (r["model"], r["rep"], str(genes), method) in pub]
            row[key] = f"{mean(vals):.4f}" if len(vals) == len(rs) else ""
        rows.append(row)
        print(row)
    write_csv(HERE / "results" / f"{prefix}_summary.csv", rows, list(rows[0]))
    print(f"Saved results/{prefix}_summary.csv")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("published")
    sum_parser = sub.add_parser("summary")
    sum_parser.add_argument("--resolved", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("--methods", nargs="+", choices=["quanta", "wqfm-tree"], default=["quanta"])
    p.add_argument("--taxa", type=int, nargs="+", default=list(MODELS))
    p.add_argument("--genes", type=int, nargs="+", default=GENES)
    p.add_argument("--reps", nargs="*", help="replicates (default: all)")
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--resolved", action="store_true", help="resolve polytomies first with the official script")
    p.add_argument("--java-opt", dest="java_opts", action="append",
                   help="JVM option for both methods, repeatable: --java-opt=-Xmx5g --java-opt=-XX:+UseSerialGC")
    args = parser.parse_args()
    if getattr(args, "resolved", False):
        global RESOLVED, RUNS
        RESOLVED, RUNS = True, HERE / "runs" / "a2r"
    if args.command == "published":
        published()
    elif args.command == "summary":
        summary()
    else:
        compare.JAVA_OPTS = args.java_opts  # inherited by the worker processes
        run(args.methods, args.reps, args.taxa, args.genes, args.jobs)


if __name__ == "__main__":
    sys.exit(main())
