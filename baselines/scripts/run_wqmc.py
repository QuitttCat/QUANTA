#!/usr/bin/env python3
"""Run wQMC (weighted Quartet MaxCut, Avni et al. 2015) on the same
weighted-quartet inputs used for wQFM and wQ2A.

wQMC requires integer taxon names, so each input is first converted to its
format (one line of `a,b|c,d:weight` entries, as in the wQFM benchmark
scripts); the output tree is then mapped back to the original names. The
max-cut-tree run is timed end to end (wall clock, includes reading the
input); the conversion is timed separately. Finished runs are skipped.

Requires the max-cut-tree binary at baselines/tools/wQMC/max-cut-tree.

Run from the repository root:
    QWQFM/.venv/bin/python baselines/scripts/run_wqmc.py [--only GROUP ...]
"""

import argparse
import csv
import json
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "QWQFM" / "WQFM" / "input_files"
WQMC = REPO / "baselines" / "tools" / "wQMC" / "max-cut-tree"
OUT_DIR = REPO / "baselines" / "results" / "wqmc"
CSV_PATH = REPO / "baselines" / "results" / "wqmc_results.csv"
PYTHON = REPO / "QWQFM" / ".venv" / "bin" / "python"
SCORE = REPO / "baselines" / "scripts" / "score_tree.py"

FIELDS = ["group", "input_file", "taxa", "wqmc_tree", "rf", "rf_reference",
          "weighted_quartet_score", "total_quartet_weight", "quartet_score_fraction",
          "end_to_end_seconds", "conversion_seconds", "max_rss_mb"]
QUARTET = re.compile(r"^\(\(([^,()]+),([^,()]+)\),\(([^,()]+),([^,()]+)\)\);\s*(\S+)\s*$")


REFERENCES = REPO / "baselines" / "references"  # written by recover_references.py


def runs():
    simulated = [("11", "11-taxa-weighted-quartets"), ("15", "15-taxa-weighted-quartets"),
                 ("37", "37-taxa-weighted-quartets"), ("48", "48-taxa-weighted-quartets")]
    for group, folder in simulated:
        for path in sorted((INPUT / folder).iterdir()):
            if group == "11":
                reference = REFERENCES / ("11_estimated.tre" if path.name.startswith("estimated_") else "11_simulated.tre")
            else:
                reference = REFERENCES / f"{group}.tre"
            yield dict(group=group, name=path.name, quartets=path, reference=reference)
    bio = INPUT / "biological_dataset_weigted_quartets"
    for path in sorted(bio.glob("*.weighted_quartets")):
        yield dict(group="biological", name=path.name, quartets=path, reference=None)
    for path in sorted((INPUT / "101-taxa-weighted-quartets").glob("*.true.wqrts")):
        replicate = path.name.split(".")[0]
        yield dict(group="101", name=path.name, quartets=path,
                   reference=INPUT / "101-taxa-true-species-tree" / f"{replicate}.SPECIES_TREE")
    yield dict(group="144", name="insect_gene_tree_0713",
               quartets=INPUT / "144-taxa-insect-single-gene-weighted-quartets" / "insect_gene_tree_0713.weighted_quartets",
               reference=INPUT / "144-taxa-insect-single-gene" / "insect_gene_tree_0713.tre")
    yield dict(group="200", name="s200_rep01_true_gene_tree_001",
               quartets=INPUT / "200-taxa-s200-rep01-true-gene-tree-weighted-quartets" / "s200_rep01_true_gene_tree_001_200_taxa.weighted_quartets",
               reference=INPUT / "200-taxa-s200-rep01-true-gene-tree" / "s200_rep01_true_gene_tree_001_200_taxa.tre")


def convert(source, target):
    """Write wQMC input with integer taxon IDs; return the ID -> name map."""
    ids = {}
    with open(source) as quartets, open(target, "w") as out:
        first = True
        for line_number, line in enumerate(quartets, start=1):
            if not line.strip():
                continue
            match = QUARTET.match(line)
            if not match:
                raise ValueError(f"invalid quartet on line {line_number}: {line!r}")
            a, b, c, d, weight = match.groups()
            a, b, c, d = (ids.setdefault(t, len(ids) + 1) for t in (a, b, c, d))
            out.write(("" if first else " ") + f"{a},{b}|{c},{d}:{float(weight)}")
            first = False
        out.write("\n")
    return {i: name for name, i in ids.items()}


def map_back(tree, names):
    return re.sub(r"(?<=[(,])(\d+)(?=[,):;])", lambda m: names[int(m.group(1))], tree.strip())


def run_one(spec):
    out = OUT_DIR / spec["group"] / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    tree_file, meta_file = out / "wqmc.tre", out / "run.json"
    if not meta_file.exists():
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            qmc_in, qmc_out = Path(tmp) / "input", Path(tmp) / "output"
            start = time.perf_counter()
            names = convert(spec["quartets"], qmc_in)
            conversion = time.perf_counter() - start
            with open(out / "wqmc.log", "w") as log:
                subprocess.run(["/usr/bin/time", "-f", "%e %M", "-o", str(out / "time.txt"), str(WQMC),
                                f"qrtt={qmc_in}", "weights=on", f"otre={qmc_out}"],
                               stdout=log, stderr=subprocess.STDOUT, check=True, cwd=tmp)
            tree_file.write_text(map_back(qmc_out.read_text().strip().splitlines()[-1], names) + "\n")
        wall, rss_kb = (out / "time.txt").read_text().split()[-2:]
        meta_file.write_text(json.dumps(dict(end_to_end_seconds=float(wall), conversion_seconds=conversion,
                                             max_rss_mb=int(rss_kb) / 1024)))
    meta = json.loads(meta_file.read_text())

    score_file = out / "score.json"
    if not score_file.exists():
        cmd = [str(PYTHON), str(SCORE), "--tree", str(tree_file), "--quartets", str(spec["quartets"])]
        if spec["reference"]:
            cmd += ["--reference", str(spec["reference"])]
        score_file.write_text(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)
    score = json.loads(score_file.read_text())
    return {
        "group": spec["group"], "input_file": spec["name"], "taxa": score["tree"].count(",") + 1,
        "wqmc_tree": score["tree"], "rf": f"{score['rf']:.12f}" if "rf" in score else "",
        "rf_reference": ("true species tree" if spec["group"] in ("11", "15", "37", "48", "101") else
                         "input gene tree" if spec["group"] in ("144", "200") else ""),
        "weighted_quartet_score": f"{score['weighted_quartet_score']:.0f}",
        "total_quartet_weight": f"{score['total_quartet_weight']:.0f}",
        "quartet_score_fraction": f"{score['quartet_score_fraction']:.6f}",
        "end_to_end_seconds": f"{meta['end_to_end_seconds']:.3f}",
        "conversion_seconds": f"{meta['conversion_seconds']:.3f}",
        "max_rss_mb": f"{meta['max_rss_mb']:.1f}",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="groups to run: 11 15 37 48 biological 101 144 200")
    parser.add_argument("--jobs", type=int, default=1, help="inputs run in parallel (default 1)")
    args = parser.parse_args()
    if not WQMC.exists():
        raise SystemExit(f"wQMC binary not found: {WQMC} (see baselines/commands.md)")

    rows = {}
    if CSV_PATH.exists():
        with CSV_PATH.open() as handle:
            rows = {(r["group"], r["input_file"]): r for r in csv.DictReader(handle)}
    specs = [s for s in runs() if not args.only or s["group"] in args.only]
    print(f"{len(specs)} inputs, {args.jobs} in parallel", flush=True)
    # Workers only run wQMC and score; this process alone writes the CSV.
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, spec) for spec in specs]
        for done, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            rows[(row["group"], row["input_file"])] = row
            tmp = CSV_PATH.with_suffix(".tmp")
            with tmp.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(sorted(rows.values(), key=lambda r: (r["group"], r["input_file"])))
            os.replace(tmp, CSV_PATH)
            print(f"[{done}/{len(specs)}] {row['group']} {row['input_file']}: time {row['end_to_end_seconds']} s, "
                  f"quartet score {row['quartet_score_fraction']}, RF {row['rf'] or '-'}", flush=True)
    print(f"Saved {CSV_PATH}")


if __name__ == "__main__":
    main()
