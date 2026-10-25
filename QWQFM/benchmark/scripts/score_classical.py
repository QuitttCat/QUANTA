#!/usr/bin/env python3
"""Score classical-solver runs (run_classical_benchmark.sh) on datasets that
have no single shared model tree (biological, 101, 144 and 200 taxa).

Each tree gets its weighted quartet score against its own input quartets (the
four-point test used for all methods, baselines/scripts/score_tree.py) and,
when a reference tree is given, its normalized RF distance: one reference per
input from --reference-dir (101 taxa: <prefix><suffix>, prefix = file name up
to the first dot), or one --reference-file for all (144 and 200 taxa: the
input gene tree). Scores are cached in each run folder as score.json.
"""

import argparse
import csv
import json
import os
import re
import subprocess
from pathlib import Path

from summarize_classical import LABELS, load_scorer

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parents[2]
PYTHON = REPO / "QWQFM" / ".venv" / "bin" / "python"
SCORE = REPO / "baselines" / "scripts" / "score_tree.py"


def reference_for(name, args):
    if args.reference_file:
        return Path(args.reference_file)
    if args.reference_dir:
        return Path(args.reference_dir) / (name.split(".")[0] + args.reference_suffix)
    return None


def score(result_dir, quartets, reference):
    cached = result_dir / "score.json"
    try:
        return json.loads(cached.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    cmd = [str(PYTHON), str(SCORE), "--tree", str(result_dir / "quantum.tre"), "--quartets", str(quartets)]
    if reference:
        cmd += ["--reference", str(reference)]
    output = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    with open(cached, "w") as handle:
        handle.write(output)
        handle.flush()
        os.fsync(handle.fileno())
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True, choices=sorted(LABELS))
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--input-dir", required=True, help="the weighted-quartet inputs of the runs")
    parser.add_argument("--reference-dir", help="one reference tree per input")
    parser.add_argument("--reference-suffix", default="", help="file suffix of the trees in --reference-dir")
    parser.add_argument("--reference-file", help="one reference tree for all inputs")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    name, marker = LABELS[args.solver]
    scorer = load_scorer()
    rows = []
    for result_dir in sorted(Path(args.work_dir).iterdir()):
        if not (result_dir / "quantum.done").exists():
            continue
        reference = reference_for(result_dir.name, args)
        result = score(result_dir, Path(args.input_dir) / result_dir.name, reference)
        log = (result_dir / "quantum.log").read_text(errors="replace")
        sampler_ns = [int(v) for v in re.findall(rf"{marker}_TIME_NS n=\d+ duration_ns=(\d+)", log)]
        sampler_seconds = sum(sampler_ns) / 1e9
        bruteforce_seconds = scorer.sum_quantum_bruteforce_seconds(result_dir / "quantum.log")
        rows.append({
            "quartet_file_name": result_dir.name,
            f"{name}_tree": result["tree"],
            f"rf_{name}_wrt_reference": f"{result['rf']:.12f}" if "rf" in result else "",
            "reference": reference.name if reference else "",
            f"{name}_weighted_quartet_score": f"{result['weighted_quartet_score']:.0f}",
            "total_quartet_weight": f"{result['total_quartet_weight']:.0f}",
            f"{name}_quartet_score_fraction": f"{result['quartet_score_fraction']:.6f}",
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
