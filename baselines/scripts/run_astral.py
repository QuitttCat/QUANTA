#!/usr/bin/env python3
"""Run ASTRAL (ASTER v1.25.4.8) on the inputs used for wQFM and wQ2A.

Weighted-quartet inputs (101-taxon replicates, biological datasets) are run
with `wastral --mode 4 --treeweights`: every quartet becomes a four-taxon
tree weighted by its quartet weight, so ASTRAL maximizes exactly the same
weighted quartet score as wQFM and wQ2A. Single-gene-tree inputs (144 and
200 taxa) are run with `astral4` on the gene tree itself, which carries the
same quartet information as their weighted-quartet files.

Each run is timed end to end (wall clock of the ASTRAL process, which
includes reading the input), single-threaded (-t 1) like wQFM. The format
conversion is timed separately. Finished runs are skipped on rerun.

Run from the repository root:
    QWQFM/.venv/bin/python baselines/scripts/run_astral.py [--only GROUP ...]
"""

import argparse
import csv
import fcntl
import json
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "QWQFM" / "WQFM" / "input_files"
ASTER = REPO / "baselines" / "tools" / "ASTER" / "bin"
OUT_DIR = REPO / "baselines" / "results" / "astral"
CSV_PATH = REPO / "baselines" / "results" / "astral_results.csv"
PYTHON = REPO / "QWQFM" / ".venv" / "bin" / "python"
SCORE = REPO / "baselines" / "scripts" / "score_tree.py"
CONVERT = REPO / "baselines" / "scripts" / "quartets_to_aster.py"
ASTER_VERSION = "ASTER v1.25.4.8 (commit ddc3dc6)"

FIELDS = ["group", "input_file", "taxa", "method", "astral_tree", "rf", "rf_reference",
          "weighted_quartet_score", "total_quartet_weight", "quartet_score_fraction",
          "end_to_end_seconds", "conversion_seconds", "max_rss_mb", "threads", "aster_version"]


REFERENCES = REPO / "baselines" / "references"  # written by recover_references.py


def runs():
    simulated = [("11", "11-taxa-weighted-quartets"), ("15", "15-taxa-weighted-quartets"),
                 ("37", "37-taxa-weighted-quartets"), ("48", "48-taxa-weighted-quartets")]
    for group, folder in simulated:
        if not (INPUT / folder).is_dir():  # dataset not extracted on this machine
            continue
        for path in sorted((INPUT / folder).iterdir()):
            if group == "11":
                reference = REFERENCES / ("11_estimated.tre" if path.name.startswith("estimated_") else "11_simulated.tre")
            else:
                reference = REFERENCES / f"{group}.tre"
            yield dict(group=group, name=path.name, kind="quartets", input=path, quartets=path, reference=reference)
    bio = INPUT / "biological_dataset_weigted_quartets"
    for path in sorted(bio.glob("*.weighted_quartets")):
        yield dict(group="biological", name=path.name, kind="quartets", input=path, quartets=path, reference=None)
    for path in sorted((INPUT / "101-taxa-weighted-quartets").glob("*.true.wqrts")):
        replicate = path.name.split(".")[0]
        yield dict(group="101", name=path.name, kind="quartets", input=path, quartets=path,
                   reference=INPUT / "101-taxa-true-species-tree" / f"{replicate}.SPECIES_TREE")
    yield dict(group="144", name="insect_gene_tree_0713", kind="genetree",
               input=INPUT / "144-taxa-insect-single-gene" / "insect_gene_tree_0713.tre",
               quartets=INPUT / "144-taxa-insect-single-gene-weighted-quartets" / "insect_gene_tree_0713.weighted_quartets",
               reference=INPUT / "144-taxa-insect-single-gene" / "insect_gene_tree_0713.tre")
    yield dict(group="200", name="s200_rep01_true_gene_tree_001", kind="genetree",
               input=INPUT / "200-taxa-s200-rep01-true-gene-tree" / "s200_rep01_true_gene_tree_001_200_taxa.tre",
               quartets=INPUT / "200-taxa-s200-rep01-true-gene-tree-weighted-quartets" / "s200_rep01_true_gene_tree_001_200_taxa.weighted_quartets",
               reference=INPUT / "200-taxa-s200-rep01-true-gene-tree" / "s200_rep01_true_gene_tree_001_200_taxa.tre")


def timed(cmd, time_file, log_file):
    with open(log_file, "w") as log:
        subprocess.run(["/usr/bin/time", "-f", "%e %M", "-o", str(time_file), *cmd],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    wall, rss_kb = Path(time_file).read_text().split()[-2:]
    return float(wall), int(rss_kb) / 1024


def read_json(path):
    """Parsed JSON, or None if the file is missing or was cut short by a crash."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fsync_file(path):
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())


def write_synced(path, text):
    """Write and flush to disk: a WSL crash once left just-written results empty."""
    with open(path, "w") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def run_one(spec):
    out = OUT_DIR / spec["group"] / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    tree_file = out / "astral.tre"
    meta_file = out / "run.json"
    score_file = out / "score.json"
    meta = read_json(meta_file)
    if meta is None or not tree_file.exists() or tree_file.stat().st_size == 0:
        score_file.unlink(missing_ok=True)
        for stale in out.glob("tmp*"):  # left by an interrupted run
            shutil.rmtree(stale)
        conversion = 0.0
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            if spec["kind"] == "quartets":
                trees, weights = Path(tmp) / "trees", Path(tmp) / "weights"
                start = time.perf_counter()
                subprocess.run([str(PYTHON), str(CONVERT), str(spec["input"]), str(trees), str(weights)], check=True)
                conversion = time.perf_counter() - start
                cmd = [str(ASTER / "wastral"), "--mode", "4", "--treeweights", str(weights),
                       "-t", "1", "-u", "0", "-o", str(tree_file), str(trees)]
                method = "wastral --mode 4 --treeweights"
            else:
                cmd = [str(ASTER / "astral4"), "-t", "1", "-u", "0", "-o", str(tree_file), str(spec["input"])]
                method = "astral4"
            wall, rss = timed(cmd, out / "time.txt", out / "astral.log")
        fsync_file(tree_file)
        meta = dict(method=method, end_to_end_seconds=wall, conversion_seconds=conversion, max_rss_mb=rss)
        write_synced(meta_file, json.dumps(meta))

    score = read_json(score_file)
    if score is None:
        cmd = [str(PYTHON), str(SCORE), "--tree", str(tree_file), "--quartets", str(spec["quartets"])]
        if spec["reference"]:
            cmd += ["--reference", str(spec["reference"])]
        output = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        write_synced(score_file, output)
        score = json.loads(output)

    taxa = score["tree"].count(",") + 1
    return {
        "group": spec["group"], "input_file": spec["name"], "taxa": taxa, "method": meta["method"],
        "astral_tree": score["tree"], "rf": f"{score['rf']:.12f}" if "rf" in score else "",
        "rf_reference": ("true species tree" if spec["group"] in ("11", "15", "37", "48", "101") else
                         "input gene tree" if spec["kind"] == "genetree" else ""),
        "weighted_quartet_score": f"{score['weighted_quartet_score']:.0f}",
        "total_quartet_weight": f"{score['total_quartet_weight']:.0f}",
        "quartet_score_fraction": f"{score['quartet_score_fraction']:.6f}",
        "end_to_end_seconds": f"{meta['end_to_end_seconds']:.3f}",
        "conversion_seconds": f"{meta['conversion_seconds']:.3f}",
        "max_rss_mb": f"{meta['max_rss_mb']:.1f}",
        "threads": 1, "aster_version": ASTER_VERSION,
    }


def write_csv(new_rows):
    """Merge this run's rows into the CSV under a lock, so several
    run_astral.py processes (e.g. different --only groups) can share it."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = {}
        if CSV_PATH.exists():
            with CSV_PATH.open() as handle:
                rows = {(r["group"], r["input_file"]): r for r in csv.DictReader(handle)}
        rows.update(new_rows)
        tmp = CSV_PATH.with_suffix(".tmp")
        with tmp.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(sorted(rows.values(), key=lambda r: (r["group"], r["input_file"])))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, CSV_PATH)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="groups to run: 11 15 37 48 biological 101 144 200")
    parser.add_argument("--jobs", type=int, default=1,
                        help="inputs run in parallel, each single-threaded (default 1)")
    args = parser.parse_args()

    new_rows = {}
    specs = [s for s in runs() if not args.only or s["group"] in args.only]
    print(f"{len(specs)} inputs, {args.jobs} in parallel", flush=True)
    # Workers only run ASTRAL and score; this process alone writes the CSV.
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_one, spec): spec for spec in specs}
        for done, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            new_rows[(row["group"], row["input_file"])] = row
            write_csv(new_rows)
            print(f"[{done}/{len(specs)}] {row['group']} {row['input_file']}: time {row['end_to_end_seconds']} s, "
                  f"RSS {row['max_rss_mb']} MB, quartet score {row['quartet_score_fraction']}, RF {row['rf'] or '-'}",
                  flush=True)
    print(f"Saved {CSV_PATH}")


if __name__ == "__main__":
    main()
