"""Bipartition solver for Algorithm 2 that uses a classical QUBO sampler
(simulated annealing or tabu search, from dwave-samplers) in place of the
D-Wave QPU. Selected by pointing WQFM_QUBO_SCRIPT at this file.

Same QUBO, stdin/stdout protocol and routing as qaoa.py; only the solver for
large partitions differs:
  n > 20   -> classical sampler with the QPU settings of qaoa.py: 1000 reads,
              lowest-energy sample with at least two taxa per side, and the
              same deterministic balanced fallback
  n <= 20  -> exact brute force (qaoa.find_min_energy, unchanged)

Environment: WQ2A_CLASSICAL_SOLVER (required: sa or tabu),
WQ2A_CLASSICAL_READS (1000).
"""

import os
import sys
import time

import numpy as np
from dwave.samplers import SimulatedAnnealingSampler, TabuSampler

import qaoa

THRESHOLD = 20  # partitions above this size go to the QPU in qaoa.py
SOLVERS = {
    "sa": ("SIMULATED_ANNEALING", SimulatedAnnealingSampler),
    "tabu": ("TABU_SEARCH", TabuSampler),
}
SOLVER = os.environ.get("WQ2A_CLASSICAL_SOLVER", "")
if SOLVER not in SOLVERS:
    sys.exit("Set WQ2A_CLASSICAL_SOLVER to 'sa' or 'tabu'")
LABEL, SAMPLER = SOLVERS[SOLVER]
READS = int(os.environ.get("WQ2A_CLASSICAL_READS", "1000"))


def classical_annealing(Q, n):
    start_ns = time.perf_counter_ns()
    sampleset = SAMPLER().sample_qubo(qaoa.qubo_matrix_to_dict(Q), num_reads=READS)
    print(f"{LABEL}_TIME_NS n={n} duration_ns={time.perf_counter_ns() - start_ns}", flush=True)
    try:
        return qaoa._best_nontrivial_sample(sampleset, n, min_partition_size=2,
                                            selection_label=LABEL)
    except RuntimeError:
        # Same deterministic balanced fallback as the QPU path in qaoa.py.
        fallback = np.zeros(n, dtype=np.int8)
        fallback[n // 2:] = 1
        print(f"{LABEL} returned no valid sampled partition; using deterministic "
              f"balanced fallback: {n // 2} & {n - n // 2}", flush=True)
        return fallback, float(fallback @ Q @ fallback)


def solve(Q, n, taxa_to_idx):
    if n <= THRESHOLD:
        _, _, left, right = qaoa.find_min_energy(Q, n, taxa_to_idx)
        return left, right
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    print(f"Using {LABEL} for n > {THRESHOLD} (reads={READS}).", flush=True)
    best_x, _ = classical_annealing(Q, n)
    left = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    return left, right


if __name__ == "__main__":
    print(f"Solver: {LABEL} (n > {THRESHOLD}, reads={READS}), brute force otherwise; "
          f"QUBO A=1.0, B=0.4", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        accumulator = qaoa.StreamingQuboAccumulator(A=1.0, B=0.4)
        while line != "END":
            match = qaoa.QUARTET_PATTERN.match(line)
            if match:
                a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
                accumulator.add(a, b, c, d, float(match.group(5)))
            next_line = sys.stdin.readline()
            if not next_line:
                raise EOFError("Quartet stream ended before END sentinel")
            line = next_line.strip()

        Q, n, taxa_to_idx = accumulator.finish()
        left_partition, right_partition = solve(Q, n, taxa_to_idx)
        print(f"Left partition (0):  {left_partition}", flush=True)
        print(f"Right partition (1): {right_partition}", flush=True)
        print("DONE", flush=True)
