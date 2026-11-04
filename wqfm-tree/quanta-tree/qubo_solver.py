#!/usr/bin/env python3
"""QUANTA's bipartition solvers behind QFMQubo (Java), as a persistent process.

Reads "QUBO M" and M rows of the upper-triangular Q (row i holds
Q[i][i..M-1]); replies "SOLUTION <bits> <solver seconds>" on stdout. Solvers
are QUANTA's own, unchanged:
  M <= 20  qaoa.find_min_energy (exhaustive, at least two units per side)
  M > 20   qaoa_classical.classical_annealing (simulated annealing,
           dwave-samplers, 1000 reads, lowest-energy sample with at least two
           units per side, balanced fallback)
Their logs go to stderr (the Java side writes it to QUBO_SOLVER_LOG).
"""

import contextlib
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "QWQFM" / "WQFM" / "src" / "wqfm" / "algo" / "quantum"))
os.environ.setdefault("WQ2A_CLASSICAL_SOLVER", "sa")
import qaoa  # noqa: E402
import qaoa_classical  # noqa: E402

THRESHOLD = 20


def main():
    for line in sys.stdin:
        if not line.startswith("QUBO "):
            continue
        m = int(line.split()[1])
        Q = np.zeros((m, m))
        for i in range(m):
            Q[i, i:] = np.array(sys.stdin.readline().split(), dtype=float)
        start = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            if m <= THRESHOLD:
                _, x, _, _ = qaoa.find_min_energy(Q, m, {str(i): i for i in range(m)})
            else:
                x, _ = qaoa_classical.classical_annealing(Q, m)
        seconds = time.perf_counter() - start
        bits = "".join(str(int(v)) for v in x)
        print(f"SOLUTION {bits} {seconds:.6f}", flush=True)


if __name__ == "__main__":
    main()
