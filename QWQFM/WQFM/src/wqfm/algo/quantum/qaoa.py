import numpy as np
import os
import re
import time
import matplotlib.pyplot as plt
import neal

QUARTET_PATTERN = re.compile(
    r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*'
    r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
)


def parse_quartet_file(filename):
    """
    Parse quartet file in format: ((a,b),(c,d)); weight
    Supports both numeric and named taxa.
    Returns list of tuples: ((a, b), (c, d), weight)
    """
    quartets = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Parse format: ((a,b),(c,d)); weight (supports named or numeric taxa)
            match = QUARTET_PATTERN.match(line)
            if match:
                a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
                w = float(match.group(5))
                quartets.append(((a, b), (c, d), w))

    return quartets

def parse_quartet_stdin():
    """
    Parse quartets streamed from stdin in format: ((a,b),(c,d)); weight
    Returns list of tuples: ((a, b), (c, d), weight)
    """
    import sys
    quartets = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        match = QUARTET_PATTERN.match(line)
        if match:
            a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
            w = float(match.group(5))
            quartets.append(((a, b), (c, d), w))
    return quartets

def build_qubo_matrix(quartets, A=1.0, B=0.4, gamma=0.0, S0=0):
    """
    Build QUBO matrix Q from weighted quartets.
    
    Parameters:
    - quartets: list of ((a,b), (c,d), weight) tuples
    - A: penalty for separating intended pairs
    - B: penalty for non-separated cross pairs
    - gamma: strength of balance constraint (optional)
    - S0: target partition size (optional)
    
    Returns:
    - Q: QUBO matrix (numpy array)
    - n: number of taxa
    - taxa_to_idx: mapping from taxon name to index
    """
    # Collect all unique taxa and create index mapping
    all_taxa = set()
    for (a, b), (c, d), _ in quartets:
        all_taxa.update([a, b, c, d])
    
    taxa_list = sorted(all_taxa)
    taxa_to_idx = {taxon: idx for idx, taxon in enumerate(taxa_list)}
    n = len(taxa_list)
    
    print(f"Number of taxa: {n}")
    print(f"Taxa mapping: {taxa_to_idx}")
    print(f"Number of quartets: {len(quartets)}")
    
    # Initialize QUBO matrix
    Q = np.zeros((n, n))
    
    # Process each quartet
    for (a, b), (c, d), wq in quartets:
        # Map taxa names to indices
        a_idx, b_idx, c_idx, d_idx = taxa_to_idx[a], taxa_to_idx[b], taxa_to_idx[c], taxa_to_idx[d]
        
        # Within-pair cohesion terms: A * [(xa - xb)^2 + (xc - xd)^2]
        # (xa - xb)^2 = xa^2 - 2*xa*xb + xb^2 = xa - 2*xa*xb + xb (since xi^2 = xi)
        Q[a_idx, a_idx] += wq * A
        Q[b_idx, b_idx] += wq * A
        if a_idx < b_idx:
            Q[a_idx, b_idx] += wq * A * (-2)
        else:
            Q[b_idx, a_idx] += wq * A * (-2)
        
        # (xc - xd)^2
        Q[c_idx, c_idx] += wq * A
        Q[d_idx, d_idx] += wq * A
        if c_idx < d_idx:
            Q[c_idx, d_idx] += wq * A * (-2)
        else:
            Q[d_idx, c_idx] += wq * A * (-2)
        
        # Cross-pair separation terms: B * sum_{u in {a,b}, v in {c,d}} (xu + xv - 1)^2
        # (xu + xv - 1)^2 = xu^2 + xv^2 + 1 + 2*xu*xv - 2*xu - 2*xv
        #                 = xu + xv + 1 + 2*xu*xv - 2*xu - 2*xv
        #                 = 2*xu*xv - xu - xv + 1
        cross_pairs = [(a_idx, c_idx), (a_idx, d_idx), (b_idx, c_idx), (b_idx, d_idx)]
        
        for u_idx, v_idx in cross_pairs:
            Q[u_idx, u_idx] += wq * B * (-1)
            Q[v_idx, v_idx] += wq * B * (-1)
            
            if u_idx < v_idx:
                Q[u_idx, v_idx] += wq * B * 2
            else:
                Q[v_idx, u_idx] += wq * B * 2
            
            # Constant term (1) is not included in Q matrix
    
    # Optional: Add balance constraint gamma * (sum(xi) - S0)^2
    if gamma > 0:
        # (sum xi - S0)^2 = sum xi^2 + 2*sum_{i<j} xi*xj - 2*S0*sum xi + S0^2
        for i in range(n):
            Q[i, i] += gamma * (1 - 2*S0)
            for j in range(i+1, n):
                Q[i, j] += gamma * 2
    
    return Q, n, taxa_to_idx


class StreamingQuboAccumulator:
    """Accumulate QUBO coefficients without retaining every quartet.

    The Java engine streams every relevant quartet to this process. Keeping
    tens of millions of parsed Python tuples is unnecessary because each
    quartet contributes additively to a small ``n x n`` QUBO.
    """

    def __init__(
        self,
        A=1.0,
        B=0.4,
        initial_capacity=256,
        batch_size=262144,
    ):
        if initial_capacity < 1:
            raise ValueError("initial_capacity must be positive")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.A = A
        self.B = B
        self.Q = np.zeros((initial_capacity, initial_capacity))
        self.taxa_to_idx = {}
        self.quartet_count = 0
        self.batch_size = batch_size
        self._a_indices = []
        self._b_indices = []
        self._c_indices = []
        self._d_indices = []
        self._weights = []

    def _ensure_capacity(self, required):
        if required <= self.Q.shape[0]:
            return
        new_capacity = self.Q.shape[0]
        while new_capacity < required:
            new_capacity *= 2
        expanded = np.zeros((new_capacity, new_capacity))
        old_capacity = self.Q.shape[0]
        expanded[:old_capacity, :old_capacity] = self.Q
        self.Q = expanded

    def _taxon_index(self, taxon):
        index = self.taxa_to_idx.get(taxon)
        if index is not None:
            return index
        index = len(self.taxa_to_idx)
        self._ensure_capacity(index + 1)
        self.taxa_to_idx[taxon] = index
        return index

    def add(self, a, b, c, d, weight):
        a_idx = self._taxon_index(a)
        b_idx = self._taxon_index(b)
        c_idx = self._taxon_index(c)
        d_idx = self._taxon_index(d)

        self._a_indices.append(a_idx)
        self._b_indices.append(b_idx)
        self._c_indices.append(c_idx)
        self._d_indices.append(d_idx)
        self._weights.append(weight)
        self.quartet_count += 1
        if len(self._weights) >= self.batch_size:
            self._flush()

    def _flush(self):
        """Apply one buffered batch with vectorized indexed accumulation."""
        if not self._weights:
            return

        a = np.asarray(self._a_indices, dtype=np.intp)
        b = np.asarray(self._b_indices, dtype=np.intp)
        c = np.asarray(self._c_indices, dtype=np.intp)
        d = np.asarray(self._d_indices, dtype=np.intp)
        weights = np.asarray(self._weights, dtype=np.float64)

        # Each taxon receives +A once from its within-pair term and -B
        # twice from its two cross-pair terms.
        diagonal_indices = np.concatenate((a, b, c, d))
        diagonal_values = np.tile(weights * (self.A - 2 * self.B), 4)
        np.add.at(
            self.Q,
            (diagonal_indices, diagonal_indices),
            diagonal_values,
        )

        pair_u = (a, c, a, a, b, b)
        pair_v = (b, d, c, d, c, d)
        pair_scales = (
            -2 * self.A,
            -2 * self.A,
            2 * self.B,
            2 * self.B,
            2 * self.B,
            2 * self.B,
        )
        rows = np.concatenate(
            tuple(np.minimum(u, v) for u, v in zip(pair_u, pair_v))
        )
        columns = np.concatenate(
            tuple(np.maximum(u, v) for u, v in zip(pair_u, pair_v))
        )
        values = np.concatenate(
            tuple(weights * scale for scale in pair_scales)
        )
        np.add.at(self.Q, (rows, columns), values)

        self._a_indices.clear()
        self._b_indices.clear()
        self._c_indices.clear()
        self._d_indices.clear()
        self._weights.clear()

    def finish(self):
        self._flush()
        n = len(self.taxa_to_idx)
        Q = self.Q[:n, :n].copy()
        print(f"Number of taxa: {n}")
        print(f"Taxa mapping: {self.taxa_to_idx}")
        print(f"Number of quartets: {self.quartet_count}")
        return Q, n, self.taxa_to_idx.copy()


def qubo_matrix_to_dict(Q):
    """Convert an upper-triangular QUBO matrix to Ocean's dictionary format.

    Every diagonal is retained, including zero-valued diagonals, so Ocean
    knows about isolated variables and a completely flat QUBO is not submitted
    as an empty problem.
    """
    if Q.ndim != 2 or Q.shape[0] != Q.shape[1]:
        raise ValueError("Q must be a square matrix")

    n = Q.shape[0]
    return {
        (i, j): float(Q[i, j])
        for i in range(n)
        for j in range(i, n)
        if i == j or Q[i, j] != 0
    }


def _best_nontrivial_sample(
    sampleset,
    n,
    min_partition_size=1,
    selection_label=None,
):
    """Return the first valid sample after sorting from lowest energy upward.

    A sample is valid only when both its zero and one partitions contain at
    least ``min_partition_size`` variables. Invalid low-energy samples are
    skipped, so the next-best sample is considered automatically.
    """
    if min_partition_size < 1:
        raise ValueError("min_partition_size must be at least 1")
    if 2 * min_partition_size > n:
        raise ValueError("min_partition_size is too large for this QUBO")

    for rank, record in enumerate(
        sampleset.data(fields=["sample", "energy"], sorted_by="energy"),
        start=1,
    ):
        candidate = np.array(
            [record.sample.get(i, 0) for i in range(n)],
            dtype=np.int8,
        )
        partition_size = int(np.sum(candidate))
        if min_partition_size <= partition_size <= n - min_partition_size:
            if selection_label is not None:
                print(
                    f"{selection_label} selected sample rank: {rank}; "
                    f"skipped invalid samples: {rank - 1}; partition sizes: "
                    f"{n - partition_size} & {partition_size}",
                    flush=True,
                )
            return candidate, record.energy

    raise RuntimeError(
        "The sampler returned no solution meeting the minimum partition "
        f"size of {min_partition_size}; increase sampler effort or add a "
        "partition constraint."
    )


def simulated_annealing(Q, num_reads=100, num_sweeps=1000):
    """
    Use simulated annealing to find low-energy bitstring for QUBO matrix Q.
    Returns best bitstring and its energy.
    """
    sampler = neal.SimulatedAnnealingSampler()
    
    n = Q.shape[0]
    Q_dict = qubo_matrix_to_dict(Q)
    
    # Sample from the QUBO
    sampleset = sampler.sample_qubo(Q_dict, num_reads=num_reads, num_sweeps=num_sweeps)
    
    return _best_nontrivial_sample(sampleset, n)


def dwave_quantum_annealing(
    Q,
    api_key=None,
    num_reads=1000,
    solver=None,
    chain_strength=None,
    min_partition_size=2,
):
    """Solve the QUBO on a D-Wave QPU through automatic minor embedding.

    The API token can be passed as ``api_key`` or provided through the
    ``DWAVE_API_TOKEN`` environment variable. The return value matches
    ``simulated_annealing``: ``(best_x, best_energy)``. Samples are examined
    in ascending energy order until both partitions contain at least
    ``min_partition_size`` taxa (two by default).
    """
    if min_partition_size < 2:
        raise ValueError(
            "D-Wave partitions must contain at least two taxa on each side"
        )

    token = api_key or os.environ.get("DWAVE_API_TOKEN")
    if not token:
        raise ValueError(
            "A D-Wave API token is required. Pass api_key=... or set "
            "DWAVE_API_TOKEN."
        )

    try:
        from dwave.system import DWaveSampler, EmbeddingComposite
    except ImportError as exc:
        raise RuntimeError(
            "D-Wave hardware support requires the 'dwave-system' package."
        ) from exc

    n = Q.shape[0]
    Q_dict = qubo_matrix_to_dict(Q)

    if solver is None:
        solver = os.environ.get("DWAVE_SOLVER") or None

    sampler_options = {"token": token}
    if solver is not None:
        sampler_options["solver"] = solver

    sample_options = {
        "num_reads": num_reads,
        "label": "QWQFM quantum bipartition",
    }
    if chain_strength is not None:
        sample_options["chain_strength"] = chain_strength

    qpu_sampler = DWaveSampler(**sampler_options)
    try:
        embedded_sampler = EmbeddingComposite(qpu_sampler)
        sampleset = embedded_sampler.sample_qubo(Q_dict, **sample_options)
        solver_name = getattr(getattr(qpu_sampler, "solver", None), "name", "unknown")
        print(f"QPU solver: {solver_name}", flush=True)
        print(
            f"QPU problem ID: {sampleset.info.get('problem_id', 'unknown')}",
            flush=True,
        )
        print(f"QPU timing: {sampleset.info.get('timing', {})}", flush=True)
        try:
            return _best_nontrivial_sample(
                sampleset,
                n,
                min_partition_size=min_partition_size,
                selection_label="QPU",
            )
        except RuntimeError:
            # This should be rare after retaining zero-valued diagonals, but do
            # not let an unlucky batch of reads produce an empty partition.
            fallback = np.zeros(n, dtype=np.int8)
            fallback[n // 2:] = 1
            fallback_energy = float(fallback @ Q @ fallback)
            print(
                "QPU returned no valid sampled partition; using deterministic "
                f"balanced fallback: {n // 2} & {n - n // 2}",
                flush=True,
            )
            return fallback, fallback_energy
    finally:
        qpu_sampler.close()


def leap_hybrid_annealing(
    Q,
    api_key=None,
    time_limit=30,
    min_partition_size=2,
):
    """Solve a large QUBO with D-Wave's Leap hybrid BQM solver.

    This has the same ``(best_x, best_energy)`` return contract as
    ``dwave_quantum_annealing``. Leap Hybrid controls its QPU sampling
    internally, so its effort parameter is ``time_limit`` rather than
    ``num_reads``.
    """
    if min_partition_size < 2:
        raise ValueError(
            "Leap Hybrid partitions must contain at least two taxa on each side"
        )
    if time_limit <= 0:
        raise ValueError("time_limit must be positive")

    token = api_key or os.environ.get("DWAVE_API_TOKEN")
    if not token:
        raise ValueError(
            "A D-Wave API token is required. Pass api_key=... or set "
            "DWAVE_API_TOKEN."
        )

    try:
        from dwave.system import LeapHybridSampler
    except ImportError as exc:
        raise RuntimeError(
            "D-Wave Leap Hybrid support requires the 'dwave-system' package."
        ) from exc

    n = Q.shape[0]
    Q_dict = qubo_matrix_to_dict(Q)
    sampler = LeapHybridSampler(token=token)
    try:
        sampleset = sampler.sample_qubo(
            Q_dict,
            time_limit=time_limit,
            label="QWQFM Leap Hybrid bipartition",
        )
        solver_identity = getattr(
            getattr(sampler, "solver", None),
            "identity",
            "unknown",
        )
        print(f"LEAP_HYBRID solver: {solver_identity}", flush=True)
        print(
            "LEAP_HYBRID problem ID: "
            f"{sampleset.info.get('problem_id', 'unknown')}",
            flush=True,
        )
        print(f"LEAP_HYBRID timing: {sampleset.info}", flush=True)
        try:
            return _best_nontrivial_sample(
                sampleset,
                n,
                min_partition_size=min_partition_size,
                selection_label="LEAP_HYBRID",
            )
        except RuntimeError:
            fallback = np.zeros(n, dtype=np.int8)
            fallback[n // 2:] = 1
            fallback_energy = float(fallback @ Q @ fallback)
            print(
                "LEAP_HYBRID returned no valid sampled partition; using "
                f"deterministic balanced fallback: {n // 2} & "
                f"{n - n // 2}",
                flush=True,
            )
            return fallback, fallback_energy
    finally:
        sampler.close()


def num_reads_for_n(n):
    # 200 reads at n=4, increasing to 1000 at n=20
    return min(1000, max(200, 50 * n))

def find_min_energy(Q, n, taxa_to_idx):
    """
    Find minimum energy bitstring by brute force enumeration.
    Returns min energy, best bitstring, and partition assignments.
    """
    # Create reverse mapping: idx -> taxon name
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    
    # if n >= 4 and n<=20:
    #     print("Using the D-Wave QPU for n > 20.")
    #     # best_x, best_energy = simulated_annealing(Q)
    #     best_x, best_energy = dwave_quantum_annealing(Q, num_reads=num_reads_for_n(n))
    #     # Build partition result
    #     left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    #     right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    #     return best_energy, best_x, left_partition, right_partition

    if n > 150:
        print(
            "Using D-Wave Leap Hybrid for n > 150 "
            "(time_limit=30 seconds).",
            flush=True,
        )
        best_x, best_energy = leap_hybrid_annealing(Q, time_limit=30)
        left_partition = [
            idx_to_taxa[i] for i in range(n) if best_x[i] == 0
        ]
        right_partition = [
            idx_to_taxa[i] for i in range(n) if best_x[i] == 1
        ]
        return (
            best_energy,
            best_x,
            left_partition,
            right_partition,
        )

    if n > 20:
        print("Using the D-Wave QPU for n > 20.", flush=True)
        # best_x, best_energy = simulated_annealing(Q)
        best_x, best_energy = dwave_quantum_annealing(Q, num_reads=1000)
        # Build partition result
        left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
        right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
        return best_energy, best_x, left_partition, right_partition

    brute_force_start_ns = time.perf_counter_ns()
    min_energy = float('inf')
    best_x = None
    

    
    for idx in range(2**n):
        x = np.array([(idx >> j) & 1 for j in range(n)])
        
        # Skip trivial solutions (all 0s or all 1s)
        if np.sum(x) <= 1 or np.sum(x) >= n-1:
            continue
            
        e = x @ Q @ x
        if e < min_energy:
            min_energy = e
            best_x = x
    
    # Fallback if no valid partition found
    if best_x is None:
        # Default: first half left, second half right
        best_x = np.array([0 if i < n//2 else 1 for i in range(n)])
        min_energy = best_x @ Q @ best_x

    brute_force_elapsed_ns = time.perf_counter_ns() - brute_force_start_ns
    print(
        f"QUANTUM_BRUTE_FORCE_TIME_NS n={n} "
        f"duration_ns={brute_force_elapsed_ns}",
        flush=True,
    )

    # Build partition result
    left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    
    return min_energy, best_x, left_partition, right_partition

if __name__ == "__main__":
    import sys
    # Persistent loop: handle multiple partition requests without restarting
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        accumulator = StreamingQuboAccumulator(A=1.0, B=0.4)
        while line != "END":
            match = QUARTET_PATTERN.match(line)
            if match:
                a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
                w = float(match.group(5))
                accumulator.add(a, b, c, d, w)
            next_line = sys.stdin.readline()
            if not next_line:
                raise EOFError("Quartet stream ended before END sentinel")
            line = next_line.strip()

        Q, n, taxa_to_idx = accumulator.finish()
        _, _, left_partition, right_partition = find_min_energy(Q, n, taxa_to_idx)

        print(f"Left partition (0):  {left_partition}", flush=True)
        print(f"Right partition (1): {right_partition}", flush=True)
        print("DONE", flush=True)
