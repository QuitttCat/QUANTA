#!/usr/bin/env python3
"""Score and atomically save one biological-dataset benchmark row."""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import re
import tempfile

from build_quartet_score_csvs import (
    format_score,
    normalize_newick,
    score_quartet_lines,
    topological_distance_matrix,
)


FIELDNAMES = [
    "quartet_file_name",
    "taxa_count",
    "wqfm_tree",
    "quantum_annealing_tree",
    "wqfm_weighted_quartet_score",
    "quantum_weighted_quartet_score",
    "better_by_weighted_quartet_score",
    "wqfm_bipartition_time_seconds",
    "quantum_qpu_access_time_seconds",
    "quantum_bruteforce_time_seconds",
    "quantum_time_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate weighted quartet scores and timing for one completed "
            "biological-dataset WQFM/quantum pair."
        )
    )
    parser.add_argument("--quartet-file", required=True)
    parser.add_argument("--wqfm-tree", required=True)
    parser.add_argument("--quantum-tree", required=True)
    parser.add_argument("--wqfm-log", required=True)
    parser.add_argument("--quantum-log", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1_000_000,
        help="print progress every N quartets; 0 disables progress output",
    )
    args = parser.parse_args()
    if args.progress_every < 0:
        parser.error("--progress-every must be non-negative")
    return args


def read_tree(path: str) -> str:
    lines = [
        line.strip()
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]
    if not lines:
        raise ValueError(f"Tree file is empty: {path}")
    return normalize_newick(lines[0])


def marker_seconds(
    log_path: str,
    pattern: str,
    divisor: float,
    *,
    description: str,
    required: bool,
) -> float:
    text = Path(log_path).read_text(errors="replace")
    values = re.findall(pattern, text)
    if not values:
        if required:
            raise ValueError(f"No {description} timing markers in {log_path}")
        return 0.0
    return sum(float(value) for value in values) / divisor


def sum_wqfm_bipartition_seconds(log_path: str) -> float:
    return marker_seconds(
        log_path,
        (
            r"BENCHMARK_BIPARTITION_TIME_NS\s+algorithm=1\b"
            r"[^\r\n]*?duration_ns=(\d+)"
        ),
        1_000_000_000.0,
        description="Algorithm 1 bipartition",
        required=True,
    )


def sum_quantum_qpu_seconds(log_path: str) -> float:
    # D-Wave reports qpu_access_time in microseconds. A run whose every
    # partition is below the QPU threshold legitimately has no QPU marker.
    return marker_seconds(
        log_path,
        r"['\"]qpu_access_time['\"]\s*:\s*(\d+(?:\.\d+)?)",
        1_000_000.0,
        description="D-Wave qpu_access_time",
        required=False,
    )


def sum_quantum_bruteforce_seconds(log_path: str) -> float:
    return marker_seconds(
        log_path,
        r"QUANTUM_BRUTE_FORCE_TIME_NS\s+n=\d+\s+duration_ns=(\d+)",
        1_000_000_000.0,
        description="Algorithm 2 brute-force",
        required=False,
    )


def upsert_csv(output_path: str, row: dict[str, str]) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    if output.exists() and output.stat().st_size:
        with output.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDNAMES:
                raise ValueError(
                    f"Unexpected CSV columns in {output}: {reader.fieldnames}"
                )
            rows = list(reader)

    rows = [
        item
        for item in rows
        if item["quartet_file_name"] != row["quartet_file_name"]
    ]
    rows.append(row)
    rows.sort(key=lambda item: item["quartet_file_name"])

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(descriptor, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    args = parse_args()
    quartet_file = Path(args.quartet_file)
    wqfm_tree = read_tree(args.wqfm_tree)
    quantum_tree = read_tree(args.quantum_tree)

    labels, wqfm_distances = topological_distance_matrix(wqfm_tree)
    _, quantum_distances = topological_distance_matrix(
        quantum_tree, expected_labels=labels
    )
    with quartet_file.open(errors="strict") as handle:
        quartet_count, total_weight, wqfm_score, quantum_score = (
            score_quartet_lines(
                handle,
                labels,
                wqfm_distances,
                quantum_distances,
                progress_name=quartet_file.name,
                progress_every=args.progress_every,
            )
        )

    if math.isclose(wqfm_score, quantum_score, rel_tol=0.0, abs_tol=1e-12):
        better = 0
    elif quantum_score > wqfm_score:
        better = 1
    else:
        better = -1

    quantum_qpu_seconds = sum_quantum_qpu_seconds(args.quantum_log)
    quantum_bruteforce_seconds = sum_quantum_bruteforce_seconds(
        args.quantum_log
    )
    quantum_seconds = quantum_qpu_seconds + quantum_bruteforce_seconds

    row = {
        "quartet_file_name": quartet_file.name,
        "taxa_count": str(len(labels)),
        "wqfm_tree": wqfm_tree,
        "quantum_annealing_tree": quantum_tree,
        "wqfm_weighted_quartet_score": format_score(wqfm_score),
        "quantum_weighted_quartet_score": format_score(quantum_score),
        "better_by_weighted_quartet_score": str(better),
        "wqfm_bipartition_time_seconds": (
            f"{sum_wqfm_bipartition_seconds(args.wqfm_log):.9f}"
        ),
        "quantum_qpu_access_time_seconds": f"{quantum_qpu_seconds:.9f}",
        "quantum_bruteforce_time_seconds": (
            f"{quantum_bruteforce_seconds:.9f}"
        ),
        "quantum_time_seconds": f"{quantum_seconds:.9f}",
    }
    upsert_csv(args.output_csv, row)
    print(
        f"  CSV row: taxa={len(labels)}, quartets={quartet_count:,}, "
        f"total_weight={format_score(total_weight)}, "
        f"WQFM={format_score(wqfm_score)}, "
        f"quantum={format_score(quantum_score)}, better={better}",
        flush=True,
    )


if __name__ == "__main__":
    main()
