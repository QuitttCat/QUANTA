#!/usr/bin/env python3
"""Build weighted-quartet-score CSVs from saved benchmark trees.

For each input quartet ``((a,b),(c,d)); weight``, the weight contributes to a
tree's score when the tree displays the split ``ab|cd``. Both candidate trees
are scored in the same streaming pass over the quartet file.
"""

from __future__ import annotations

import argparse
import csv
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import io
import os
from pathlib import Path
import tempfile
from typing import Iterable

import dendropy


FIELDNAMES = [
    "quartet_file_name",
    "wqfm_tree",
    "quantum_annealing_tree",
    "wqfm_weighted_quartet_score",
    "quantum_weighted_quartet_score",
    "better_by_weighted_quartet_score",
]


@dataclass(frozen=True)
class Dataset:
    name: str
    input_dir: Path
    source_csv: Path
    output_csv: Path


@dataclass(frozen=True)
class ScoreTask:
    quartet_file_name: str
    quartet_file: Path
    wqfm_tree: str
    quantum_tree: str
    progress_every: int


@dataclass(frozen=True)
class ScoreResult:
    quartet_file_name: str
    quartet_count: int
    total_quartet_weight: float
    wqfm_score: float
    quantum_score: float


def repository_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def datasets() -> dict[str, Dataset]:
    repo = repository_dir()
    input_root = repo / "WQFM" / "input_files"
    output_root = repo / "benchmark" / "output_csv"
    quartet_score_output_root = output_root / "quartet_score"
    return {
        "37": Dataset(
            name="37",
            input_dir=input_root / "37-taxa-weighted-quartets",
            source_csv=output_root
            / "results_37_taxa_qpu_plus_bruteforce_n>12.csv",
            output_csv=quartet_score_output_root
            / "results_37_taxa_weighted_quartet_scores.csv",
        ),
        "48": Dataset(
            name="48",
            input_dir=input_root / "48-taxa-weighted-quartets",
            source_csv=output_root
            / "results_48_taxa_qpu_plus_bruteforce_n>18.csv",
            output_csv=quartet_score_output_root
            / "results_48_taxa_weighted_quartet_scores.csv",
        ),
        "101": Dataset(
            name="101",
            input_dir=input_root / "101-taxa-weighted-quartets",
            source_csv=output_root
            / "results_101_taxa_qpu_plus_bruteforce.csv",
            output_csv=quartet_score_output_root
            / "results_101_taxa_weighted_quartet_scores.csv",
        ),
    }


def parse_args() -> argparse.Namespace:
    default_jobs = int(os.environ.get("QUARTET_SCORE_JOBS", "4"))
    parser = argparse.ArgumentParser(
        description=(
            "Compute weighted quartet scores for saved WQFM and quantum trees. "
            "Completed rows are reused unless --force is supplied."
        )
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=("37", "48", "101"),
        default=("37", "48", "101"),
        help="datasets to score (default: 37 48 101)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_jobs,
        help=f"parallel quartet files to score (default: {default_jobs})",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1_000_000,
        help="print progress every N quartets per file; 0 disables it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recompute rows even when their saved trees have not changed",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run a small in-memory correctness test and exit",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.progress_every < 0:
        parser.error("--progress-every must be non-negative")
    return args


def normalize_newick(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("tree is empty")
    return value if value.endswith(";") else value + ";"


def tree_graph(newick: str) -> tuple[dict[str, int], list[list[int]]]:
    tree = dendropy.Tree.get(data=normalize_newick(newick), schema="newick")
    nodes = list(tree.preorder_node_iter())
    node_index = {node: index for index, node in enumerate(nodes)}
    adjacency = [[] for _ in nodes]

    for node in nodes:
        parent = node.parent_node
        if parent is None:
            continue
        node_id = node_index[node]
        parent_id = node_index[parent]
        adjacency[node_id].append(parent_id)
        adjacency[parent_id].append(node_id)

    leaves: dict[str, int] = {}
    for leaf in tree.leaf_node_iter():
        label = leaf.taxon.label
        if label in leaves:
            raise ValueError(f"tree contains duplicate taxon label: {label}")
        leaves[label] = node_index[leaf]
    return leaves, adjacency


def topological_distance_matrix(
    newick: str, expected_labels: tuple[str, ...] | None = None
) -> tuple[tuple[str, ...], list[int]]:
    leaves, adjacency = tree_graph(newick)
    labels = tuple(sorted(leaves)) if expected_labels is None else expected_labels
    if set(leaves) != set(labels):
        missing = sorted(set(labels) - set(leaves))
        extra = sorted(set(leaves) - set(labels))
        raise ValueError(f"tree taxa differ; missing={missing}, extra={extra}")

    taxon_count = len(labels)
    distances = [0] * (taxon_count * taxon_count)
    for source_taxon, source_label in enumerate(labels):
        source_node = leaves[source_label]
        node_distances = [-1] * len(adjacency)
        node_distances[source_node] = 0
        queue = deque([source_node])
        while queue:
            node = queue.popleft()
            next_distance = node_distances[node] + 1
            for neighbour in adjacency[node]:
                if node_distances[neighbour] == -1:
                    node_distances[neighbour] = next_distance
                    queue.append(neighbour)

        row_offset = source_taxon * taxon_count
        for target_taxon, target_label in enumerate(labels):
            distances[row_offset + target_taxon] = node_distances[
                leaves[target_label]
            ]
    return labels, distances


def parse_weighted_quartet(line: str, line_number: int) -> tuple[str, str, str, str, float]:
    """Parse the repository's fixed ``((a,b),(c,d)); weight`` format."""
    first_comma = line.find(",", 2)
    middle = line.find("),(", first_comma + 1)
    second_comma = line.find(",", middle + 3)
    quartet_end = line.find("));", second_comma + 1)
    if (
        not line.startswith("((")
        or first_comma < 0
        or middle < 0
        or second_comma < 0
        or quartet_end < 0
    ):
        raise ValueError(f"invalid quartet syntax on line {line_number}: {line!r}")

    try:
        weight = float(line[quartet_end + 3 :].strip())
    except ValueError as exc:
        raise ValueError(
            f"invalid quartet weight on line {line_number}: {line!r}"
        ) from exc

    return (
        line[2:first_comma],
        line[first_comma + 1 : middle],
        line[middle + 3 : second_comma],
        line[second_comma + 1 : quartet_end],
        weight,
    )


def displays_input_split(
    distances: list[int], taxon_count: int, a: int, b: int, c: int, d: int
) -> bool:
    """Return whether the tree displays ``ab|cd`` using the four-point test."""
    ab_cd = distances[a * taxon_count + b] + distances[c * taxon_count + d]
    ac_bd = distances[a * taxon_count + c] + distances[b * taxon_count + d]
    ad_bc = distances[a * taxon_count + d] + distances[b * taxon_count + c]
    return ab_cd < ac_bd and ab_cd < ad_bc


def score_quartet_lines(
    lines: Iterable[str],
    labels: tuple[str, ...],
    wqfm_distances: list[int],
    quantum_distances: list[int],
    *,
    progress_name: str | None = None,
    progress_every: int = 0,
) -> tuple[int, float, float, float]:
    label_index = {label: index for index, label in enumerate(labels)}
    taxon_count = len(labels)
    quartet_count = 0
    total_weight = 0.0
    wqfm_score = 0.0
    quantum_score = 0.0

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        a_label, b_label, c_label, d_label, weight = parse_weighted_quartet(
            line, line_number
        )
        try:
            a = label_index[a_label]
            b = label_index[b_label]
            c = label_index[c_label]
            d = label_index[d_label]
        except KeyError as exc:
            raise ValueError(
                f"unknown taxon {exc.args[0]!r} on line {line_number}"
            ) from exc

        quartet_count += 1
        total_weight += weight
        if displays_input_split(
            wqfm_distances, taxon_count, a, b, c, d
        ):
            wqfm_score += weight
        if displays_input_split(
            quantum_distances, taxon_count, a, b, c, d
        ):
            quantum_score += weight

        if (
            progress_name
            and progress_every
            and quartet_count % progress_every == 0
        ):
            print(
                f"    {progress_name}: {quartet_count:,} quartets",
                flush=True,
            )

    return quartet_count, total_weight, wqfm_score, quantum_score


def score_task(task: ScoreTask) -> ScoreResult:
    labels, wqfm_distances = topological_distance_matrix(task.wqfm_tree)
    _, quantum_distances = topological_distance_matrix(
        task.quantum_tree, expected_labels=labels
    )
    with task.quartet_file.open(errors="strict") as handle:
        quartet_count, total_weight, wqfm_score, quantum_score = (
            score_quartet_lines(
                handle,
                labels,
                wqfm_distances,
                quantum_distances,
                progress_name=task.quartet_file_name,
                progress_every=task.progress_every,
            )
        )
    return ScoreResult(
        quartet_file_name=task.quartet_file_name,
        quartet_count=quartet_count,
        total_quartet_weight=total_weight,
        wqfm_score=wqfm_score,
        quantum_score=quantum_score,
    )


def read_csv(path: Path, required_fields: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in required_fields if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} is missing columns: {missing}")
        return list(reader)


def existing_output_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    rows = read_csv(path, FIELDNAMES)
    return {row["quartet_file_name"]: row for row in rows}


def write_output_rows(path: Path, rows: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows[name] for name in sorted(rows))
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def format_score(score: float) -> str:
    return str(int(score)) if score.is_integer() else f"{score:.12g}"


def result_row(
    source_row: dict[str, str], result: ScoreResult
) -> dict[str, str]:
    if result.quantum_score > result.wqfm_score:
        better = 1
    elif result.wqfm_score > result.quantum_score:
        better = -1
    else:
        better = 0
    return {
        "quartet_file_name": result.quartet_file_name,
        "wqfm_tree": normalize_newick(source_row["wqfm_tree"]),
        "quantum_annealing_tree": normalize_newick(
            source_row["quantum_annealing_tree"]
        ),
        "wqfm_weighted_quartet_score": format_score(result.wqfm_score),
        "quantum_weighted_quartet_score": format_score(
            result.quantum_score
        ),
        "better_by_weighted_quartet_score": str(better),
    }


def row_is_current(
    existing: dict[str, str] | None, source: dict[str, str]
) -> bool:
    if not existing:
        return False
    return (
        existing["wqfm_tree"] == normalize_newick(source["wqfm_tree"])
        and existing["quantum_annealing_tree"]
        == normalize_newick(source["quantum_annealing_tree"])
        and bool(existing["wqfm_weighted_quartet_score"])
        and bool(existing["quantum_weighted_quartet_score"])
    )


def process_dataset(
    dataset: Dataset, *, jobs: int, progress_every: int, force: bool
) -> None:
    print(f"[{dataset.name} taxa] source: {dataset.source_csv}", flush=True)
    source_rows = read_csv(
        dataset.source_csv,
        [
            "quartet_file_name",
            "wqfm_tree",
            "quantum_annealing_tree",
        ],
    )
    output_rows = existing_output_rows(dataset.output_csv)
    source_by_name = {
        row["quartet_file_name"]: row for row in source_rows
    }
    tasks: list[ScoreTask] = []

    for file_name in sorted(source_by_name):
        source_row = source_by_name[file_name]
        quartet_file = dataset.input_dir / file_name
        if not quartet_file.is_file():
            raise FileNotFoundError(
                f"quartet file listed in {dataset.source_csv} is missing: "
                f"{quartet_file}"
            )
        if not force and row_is_current(output_rows.get(file_name), source_row):
            continue
        tasks.append(
            ScoreTask(
                quartet_file_name=file_name,
                quartet_file=quartet_file,
                wqfm_tree=source_row["wqfm_tree"],
                quantum_tree=source_row["quantum_annealing_tree"],
                progress_every=progress_every,
            )
        )

    print(
        f"[{dataset.name} taxa] {len(tasks)} to score, "
        f"{len(source_rows) - len(tasks)} reused",
        flush=True,
    )
    if not tasks:
        print(f"[{dataset.name} taxa] complete: {dataset.output_csv}", flush=True)
        return

    def save(result: ScoreResult) -> None:
        source_row = source_by_name[result.quartet_file_name]
        output_rows[result.quartet_file_name] = result_row(source_row, result)
        write_output_rows(dataset.output_csv, output_rows)
        print(
            f"[{dataset.name} taxa] completed {result.quartet_file_name}: "
            f"quartets={result.quartet_count:,}, "
            f"total_weight={format_score(result.total_quartet_weight)}, "
            f"WQFM={format_score(result.wqfm_score)}, "
            f"quantum={format_score(result.quantum_score)}",
            flush=True,
        )

    if jobs == 1:
        for task in tasks:
            save(score_task(task))
    else:
        with ProcessPoolExecutor(max_workers=min(jobs, len(tasks))) as executor:
            futures = {executor.submit(score_task, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                try:
                    save(future.result())
                except BaseException as exc:
                    raise RuntimeError(
                        f"failed while scoring {task.quartet_file_name}"
                    ) from exc

    print(f"[{dataset.name} taxa] complete: {dataset.output_csv}", flush=True)


def self_test() -> None:
    labels, first = topological_distance_matrix("((A,B),(C,D));")
    _, second = topological_distance_matrix(
        "((A,C),(B,D));", expected_labels=labels
    )
    lines = io.StringIO(
        "((A,B),(C,D)); 10\n"
        "((A,C),(B,D)); 20\n"
        "((A,D),(B,C)); 30\n"
    )
    count, total, first_score, second_score = score_quartet_lines(
        lines, labels, first, second
    )
    assert (count, total, first_score, second_score) == (3, 60.0, 10.0, 20.0)
    print("Self-test passed.", flush=True)


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    available = datasets()
    for name in args.datasets:
        process_dataset(
            available[name],
            jobs=args.jobs,
            progress_every=args.progress_every,
            force=args.force,
        )


if __name__ == "__main__":
    main()
