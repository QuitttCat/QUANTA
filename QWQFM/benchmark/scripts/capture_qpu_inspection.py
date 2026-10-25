#!/usr/bin/env python3
"""Capture one reproducible D-Wave Problem Inspector experiment.

The script builds the same top-level QUBO used by QWQFM Algorithm 2, submits
it through EmbeddingComposite, saves the returned samples and Inspector API
payloads, and optionally keeps the Inspector web server alive.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import requests


REPO_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = REPO_DIR.parent
APP_DIR = REPO_DIR / "WQFM"
DEFAULT_INPUT = (
    APP_DIR
    / "input_files"
    / "48-taxa-weighted-quartets"
    / "1X-50-500_R9_weighted_quartets"
)
DEFAULT_SOURCE_CSV = (
    REPO_DIR
    / "benchmark"
    / "output_csv"
    / "results_48_taxa_qpu_plus_bruteforce_n>20.csv"
)
DEFAULT_OUTPUT_ROOT = REPO_DIR / "benchmark" / "QPU_inspection"
QAOA_PATH = APP_DIR / "src" / "wqfm" / "algo" / "quantum" / "qaoa.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit and save one QWQFM D-Wave Problem Inspector capture."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=WORKSPACE_DIR / ".env")
    parser.add_argument("--a", type=float, default=1.0)
    parser.add_argument("--b", type=float, default=0.4)
    parser.add_argument("--num-reads", type=int, default=1000)
    parser.add_argument("--min-partition-size", type=int, default=2)
    parser.add_argument("--solver", default=None)
    parser.add_argument("--chain-strength", type=float, default=None)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Keep the local Problem Inspector web server alive.",
    )
    return parser.parse_args()


def load_qaoa_module():
    spec = importlib.util.spec_from_file_location("qwqfm_qaoa", QAOA_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load QUBO module: {QAOA_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_token(env_file: Path) -> tuple[str, str]:
    token = os.environ.get("DWAVE_API_TOKEN", "").strip()
    if token:
        return token, "environment"

    if env_file.is_file():
        pattern = re.compile(
            r"^\s*(?:export\s+)?DWAVE_API_TOKEN\s*=\s*(.*?)\s*$"
        )
        for line in env_file.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if not match:
                continue
            token = match.group(1).strip()
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
                token = token[1:-1]
            if token:
                return token, str(env_file)

    raise RuntimeError(
        "DWAVE_API_TOKEN is missing from the environment and env file"
    )


def source_csv_row(csv_path: Path, input_name: str) -> dict[str, str]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("quartet_file_name") == input_name:
                return row
    raise RuntimeError(f"No CSV row for {input_name!r} in {csv_path}")


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(json_safe(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def best_valid_sample(sampleset, n: int, min_partition_size: int):
    for rank, record in enumerate(
        sampleset.data(
            fields=["sample", "energy", "num_occurrences", "chain_break_fraction"],
            sorted_by="energy",
        ),
        start=1,
    ):
        bits = np.array([record.sample.get(i, 0) for i in range(n)], dtype=np.int8)
        ones = int(bits.sum())
        if min_partition_size <= ones <= n - min_partition_size:
            return rank, record, bits
    raise RuntimeError(
        "No returned sample satisfies the requested minimum partition size"
    )


def write_samples_csv(path: Path, sampleset) -> None:
    variables = list(sampleset.variables)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "energy",
                "num_occurrences",
                "chain_break_fraction",
                *[f"x_{variable}" for variable in variables],
            ]
        )
        for rank, record in enumerate(
            sampleset.data(
                fields=[
                    "sample",
                    "energy",
                    "num_occurrences",
                    "chain_break_fraction",
                ],
                sorted_by="energy",
            ),
            start=1,
        ):
            writer.writerow(
                [
                    rank,
                    record.energy,
                    record.num_occurrences,
                    record.chain_break_fraction,
                    *[record.sample[variable] for variable in variables],
                ]
            )


def main() -> int:
    args = parse_args()
    if args.num_reads < 1:
        raise ValueError("--num-reads must be positive")
    if args.min_partition_size < 2:
        raise ValueError("--min-partition-size must be at least 2")
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    if not args.source_csv.is_file():
        raise FileNotFoundError(args.source_csv)

    token, token_source = load_token(args.env_file)
    csv_row = source_csv_row(args.source_csv, args.input.name)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_root / (
        f"{args.input.name}_A{args.a:g}_B{args.b:g}_{timestamp}"
    )
    run_dir.mkdir(parents=True, exist_ok=False)

    qaoa = load_qaoa_module()
    print(f"Reading quartets: {args.input}", flush=True)
    quartets = qaoa.parse_quartet_file(args.input)
    print(f"Building QUBO from {len(quartets)} weighted quartets", flush=True)
    build_start = time.perf_counter_ns()
    Q, n, taxa_to_idx = qaoa.build_qubo_matrix(
        quartets,
        A=args.a,
        B=args.b,
        gamma=0.0,
        S0=0,
    )
    build_ns = time.perf_counter_ns() - build_start
    if 2 * args.min_partition_size > n:
        raise ValueError("--min-partition-size is too large for this QUBO")

    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    Q_dict = qaoa.qubo_matrix_to_dict(Q)
    np.save(run_dir / "qubo_matrix.npy", Q)
    np.savetxt(run_dir / "qubo_matrix.csv", Q, delimiter=",")
    write_json(run_dir / "taxa_to_index.json", taxa_to_idx)
    write_json(run_dir / "source_csv_row.json", csv_row)

    # Import before sampling: the import activates Inspector data capture.
    import dwave.inspector
    from dwave.inspector.server import app_server
    from dwave.system import DWaveSampler, EmbeddingComposite
    from dwave.system.warnings import WarningAction

    sampler_options = {"token": token}
    if args.solver:
        sampler_options["solver"] = args.solver

    sample_options = {
        "num_reads": args.num_reads,
        "label": f"QWQFM Inspector: {args.input.name}",
        "return_embedding": True,
        "warnings": WarningAction.SAVE,
    }
    if args.chain_strength is not None:
        sample_options["chain_strength"] = args.chain_strength

    qpu_sampler = DWaveSampler(**sampler_options)
    try:
        solver_name = getattr(qpu_sampler.solver, "name", "unknown")
        embedded_sampler = EmbeddingComposite(qpu_sampler)
        print(f"Submitting to QPU solver: {solver_name}", flush=True)
        sample_start = time.perf_counter_ns()
        sampleset = embedded_sampler.sample_qubo(Q_dict, **sample_options)
        sample_ns = time.perf_counter_ns() - sample_start

        problem_id = sampleset.info.get("problem_id", "unknown")
        rank, record, bits = best_valid_sample(
            sampleset,
            n=n,
            min_partition_size=args.min_partition_size,
        )
        left_partition = [
            idx_to_taxa[index] for index in range(n) if bits[index] == 0
        ]
        right_partition = [
            idx_to_taxa[index] for index in range(n) if bits[index] == 1
        ]

        embedding_context = sampleset.info.get("embedding_context", {})
        embedding = embedding_context.get("embedding", {})
        chain_lengths = [len(chain) for chain in embedding.values()]
        physical_qubits = sorted(
            {qubit for chain in embedding.values() for qubit in chain}
        )
        chain_breaks = np.asarray(sampleset.record.chain_break_fraction)
        occurrences = np.asarray(sampleset.record.num_occurrences)
        total_reads = int(np.sum(occurrences))
        broken_sample_mask = chain_breaks > 0
        broken_reads = int(np.sum(occurrences[broken_sample_mask]))

        write_json(
            run_dir / "sampleset.json",
            sampleset.to_serializable(use_bytes=False),
        )
        write_samples_csv(run_dir / "samples.csv", sampleset)
        write_json(run_dir / "embedding_context.json", embedding_context)
        write_json(run_dir / "warnings.json", sampleset.info.get("warnings", []))

        # Start the official Inspector server and then archive exactly what its
        # problem and solver API endpoints provide to the web application.
        inspector_url = dwave.inspector.show(sampleset, block="never")
        internal_problem_url = app_server.get_problem_url(problem_id)
        internal_solver_url = app_server.get_solver_url(problem_id)
        problem_response = requests.get(internal_problem_url, timeout=30)
        problem_response.raise_for_status()
        solver_response = requests.get(internal_solver_url, timeout=30)
        solver_response.raise_for_status()
        (run_dir / "inspector_problem.json").write_bytes(problem_response.content)
        (run_dir / "inspector_solver.json").write_bytes(solver_response.content)
        (run_dir / "inspector_url.txt").write_text(
            f"{inspector_url}\n", encoding="utf-8"
        )

        rf_wqfm = float(csv_row["rf_wqfm_wrt_base"])
        rf_quantum = float(csv_row["rf_quantum_wrt_base"])
        summary = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_file": str(args.input),
            "source_csv": str(args.source_csv),
            "source_csv_row": csv_row,
            "selection_reason": "largest positive RF_WQFM - RF_quantum across RF benchmark CSVs",
            "rf_wqfm": rf_wqfm,
            "rf_quantum": rf_quantum,
            "rf_quantum_advantage": rf_wqfm - rf_quantum,
            "match_wqfm_percent": 100.0 * (1.0 - rf_wqfm),
            "match_quantum_percent": 100.0 * (1.0 - rf_quantum),
            "match_quantum_advantage_percentage_points": 100.0
            * (rf_wqfm - rf_quantum),
            "qubo": {
                "A": args.a,
                "B": args.b,
                "gamma": 0.0,
                "S0": 0,
                "variables": n,
                "quartets": len(quartets),
                "stored_upper_triangular_biases": len(Q_dict),
                "nonzero_matrix_entries": int(np.count_nonzero(Q)),
                "build_time_seconds": build_ns / 1e9,
            },
            "submission": {
                "solver": solver_name,
                "problem_id": problem_id,
                "num_reads": args.num_reads,
                "sample_call_wall_seconds": sample_ns / 1e9,
                "timing": sampleset.info.get("timing", {}),
                "token_source": token_source,
            },
            "embedding": {
                "logical_variables": len(embedding),
                "physical_qubits": len(physical_qubits),
                "chain_strength": embedding_context.get("chain_strength"),
                "min_chain_length": min(chain_lengths) if chain_lengths else None,
                "max_chain_length": max(chain_lengths) if chain_lengths else None,
                "mean_chain_length": (
                    float(np.mean(chain_lengths)) if chain_lengths else None
                ),
                "unique_samples": len(chain_breaks),
                "unique_samples_with_any_chain_break": int(
                    np.count_nonzero(broken_sample_mask)
                ),
                "reads": total_reads,
                "reads_with_any_chain_break": broken_reads,
                "reads_with_any_chain_break_percent": (
                    100.0 * broken_reads / total_reads
                ),
                "read_weighted_mean_chain_break_fraction": float(
                    np.average(chain_breaks, weights=occurrences)
                ),
                "max_chain_break_fraction": float(np.max(chain_breaks)),
            },
            "selected_sample": {
                "valid_energy_rank": rank,
                "energy": float(record.energy),
                "num_occurrences": int(record.num_occurrences),
                "chain_break_fraction": float(record.chain_break_fraction),
                "minimum_partition_size": args.min_partition_size,
                "left_partition": left_partition,
                "right_partition": right_partition,
                "partition_sizes": [len(left_partition), len(right_partition)],
            },
            "inspector": {
                "url": inspector_url,
                "url_port": urlparse(inspector_url).port,
                "serve_requested": args.serve,
            },
        }
        write_json(run_dir / "summary.json", summary)

        report = f"""# QWQFM D-Wave QPU inspection

- Input: `{args.input.name}`
- Selection: largest quantum RF advantage found across RF benchmark CSVs
- WQFM normalized RF: `{rf_wqfm:.12f}`
- Quantum normalized RF: `{rf_quantum:.12f}`
- Quantum match advantage: `{100 * (rf_wqfm - rf_quantum):.6f}` percentage points
- QUBO: `A={args.a:g}`, `B={args.b:g}`, `{n}` variables
- QPU solver: `{solver_name}`
- Problem ID: `{problem_id}`
- Reads: `{args.num_reads}`
- Selected valid sample energy rank: `{rank}`
- Partition sizes: `{len(left_partition)} & {len(right_partition)}`
- Logical variables embedded: `{len(embedding)}`
- Physical qubits used: `{len(physical_qubits)}`
- Chain length range: `{min(chain_lengths) if chain_lengths else "n/a"}–{max(chain_lengths) if chain_lengths else "n/a"}`
- Reads with chain breaks: `{broken_reads}/{total_reads}`
- Unique returned samples: `{len(chain_breaks)}`
- Inspector URL: `{inspector_url}`

The URL is served from the remote host. Forward its port through VS Code or SSH
while the `qwqfm-qpu-inspection.service` service is active.

Saved machine-readable artifacts include the full Inspector problem and solver
payloads, QUBO matrix, embedding context, returned samples, selected partition,
QPU timing, and the benchmark CSV evidence.
"""
        (run_dir / "REPORT.md").write_text(report, encoding="utf-8")
        (args.output_root / "LATEST").write_text(
            f"{run_dir.name}\n", encoding="utf-8"
        )

        print(f"Artifacts: {run_dir}", flush=True)
        print(f"Problem ID: {problem_id}", flush=True)
        print(f"Inspector URL: {inspector_url}", flush=True)
        print(
            f"Selected partition sizes: {len(left_partition)} & "
            f"{len(right_partition)}",
            flush=True,
        )

        if args.serve:
            print("Inspector server will remain active until stopped.", flush=True)
            while True:
                time.sleep(3600)
    finally:
        qpu_sampler.close()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        raise SystemExit(130)
