"""Bipartition solver for Algorithm 2 that uses classical simulated annealing
instead of the D-Wave QPU. Selected with `run-wqfm.sh ... -algo 2 --simulated_annealing`.

Same QUBO and stdin/stdout protocol as qaoa.py (whose QUBO building and
sample selection it reuses); only the solver choice differs:
  n > WQ2A_SA_THRESHOLD (default 20)  -> simulated annealing (neal)
  otherwise                           -> exact brute force (as in qaoa.py)

Environment overrides: WQ2A_SA_THRESHOLD (20), WQ2A_A (1.0), WQ2A_B (0.4),
WQ2A_SA_READS (100), WQ2A_SA_SWEEPS (1000).
"""

import os
import sys
import time

import numpy as np

import qaoa

THRESHOLD = int(os.environ.get("WQ2A_SA_THRESHOLD", "20"))
A = float(os.environ.get("WQ2A_A", "1.0"))
B = float(os.environ.get("WQ2A_B", "0.4"))
SA_READS = int(os.environ.get("WQ2A_SA_READS", "100"))
SA_SWEEPS = int(os.environ.get("WQ2A_SA_SWEEPS", "1000"))


def brute_force(Q, n):
    """Exact minimum over all bipartitions with at least two taxa per side (as in qaoa.py)."""
    start_ns = time.perf_counter_ns()
    min_energy, best_x = float("inf"), None
    for idx in range(2**n):
        x = np.array([(idx >> j) & 1 for j in range(n)])
        if np.sum(x) <= 1 or np.sum(x) >= n - 1:
            continue
        e = x @ Q @ x
        if e < min_energy:
            min_energy, best_x = e, x
    if best_x is None:
        best_x = np.array([0 if i < n // 2 else 1 for i in range(n)])
        min_energy = best_x @ Q @ best_x
    print(f"QUANTUM_BRUTE_FORCE_TIME_NS n={n} duration_ns={time.perf_counter_ns() - start_ns}", flush=True)
    return best_x, min_energy


def solve(Q, n, taxa_to_idx):
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    if n > THRESHOLD:
        print(f"Using simulated annealing for n > {THRESHOLD} "
              f"(reads={SA_READS}, sweeps={SA_SWEEPS}).", flush=True)
        start_ns = time.perf_counter_ns()
        sampleset = qaoa.neal.SimulatedAnnealingSampler().sample_qubo(
            qaoa.qubo_matrix_to_dict(Q), num_reads=SA_READS, num_sweeps=SA_SWEEPS)
        # Same rule as the QPU path: at least two taxa on each side.
        best_x, _ = qaoa._best_nontrivial_sample(sampleset, n, min_partition_size=2,
                                                 selection_label="SA")
        print(f"SIMULATED_ANNEALING_TIME_NS n={n} duration_ns={time.perf_counter_ns() - start_ns}",
              flush=True)
    else:
        best_x, _ = brute_force(Q, n)
    left = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    return left, right


if __name__ == "__main__":
    print(f"Solver: simulated annealing (n > {THRESHOLD}), brute force otherwise; "
          f"QUBO A={A}, B={B}", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        accumulator = qaoa.StreamingQuboAccumulator(A=A, B=B)
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
