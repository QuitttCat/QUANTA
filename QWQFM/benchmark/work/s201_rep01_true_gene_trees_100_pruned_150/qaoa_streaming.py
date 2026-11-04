import numpy as np
import os
import re
import time
import matplotlib.pyplot as plt
import neal
from collections import defaultdict

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
            match = re.match(r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*([\d.]+)', line)
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
        match = re.match(r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*([\d.]+)', line)
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


def accumulate_quartet_terms(
    diagonal,
    interactions,
    all_taxa,
    a,
    b,
    c,
    d,
    weight,
    A=1.0,
    B=0.4,
):
    """Accumulate one quartet directly into compact label-keyed QUBO terms."""
    all_taxa.update((a, b, c, d))

    def add_interaction(first, second, value):
        key = (first, second) if first < second else (second, first)
        interactions[key] += value

    for first, second in ((a, b), (c, d)):
        diagonal[first] += weight * A
        diagonal[second] += weight * A
        add_interaction(first, second, weight * A * -2)

    for first, second in ((a, c), (a, d), (b, c), (b, d)):
        diagonal[first] += weight * B * -1
        diagonal[second] += weight * B * -1
        add_interaction(first, second, weight * B * 2)


def materialize_streamed_qubo(
    diagonal,
    interactions,
    all_taxa,
    quartet_count,
    gamma=0.0,
    S0=0,
):
    """Create the same sorted-label QUBO as ``build_qubo_matrix``."""
    taxa_list = sorted(all_taxa)
    taxa_to_idx = {taxon: idx for idx, taxon in enumerate(taxa_list)}
    n = len(taxa_list)
    Q = np.zeros((n, n))

    for taxon, value in diagonal.items():
        idx = taxa_to_idx[taxon]
        Q[idx, idx] += value
    for (first, second), value in interactions.items():
        first_idx = taxa_to_idx[first]
        second_idx = taxa_to_idx[second]
        if first_idx < second_idx:
            Q[first_idx, second_idx] += value
        else:
            Q[second_idx, first_idx] += value

    if gamma > 0:
        for i in range(n):
            Q[i, i] += gamma * (1 - 2 * S0)
            for j in range(i + 1, n):
                Q[i, j] += gamma * 2

    print(f"Number of taxa: {n}")
    print(f"Taxa mapping: {taxa_to_idx}")
    print(f"Number of quartets: {quartet_count}")
    return Q, n, taxa_to_idx

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
        f"size of {min_partition_size}; increase num_reads or add a "
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

    if n > 20:
        print("Using the D-Wave QPU for n > 20.")
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

        # Accumulate the QUBO while reading. The original implementation kept
        # every parsed quartet as nested Python tuples and then traversed the
        # list a second time. Streaming is mathematically identical and keeps
        # memory bounded for tens of millions of weighted-quartet records.
        diagonal = defaultdict(float)
        interactions = defaultdict(float)
        all_taxa = set()
        quartet_count = 0
        while line != "END":
            match = re.match(r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*([\d.]+)', line)
            if match:
                a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
                w = float(match.group(5))
                accumulate_quartet_terms(
                    diagonal,
                    interactions,
                    all_taxa,
                    a,
                    b,
                    c,
                    d,
                    w,
                    A=1.0,
                    B=0.4,
                )
                quartet_count += 1
            line = sys.stdin.readline().strip()

        Q, n, taxa_to_idx = materialize_streamed_qubo(
            diagonal,
            interactions,
            all_taxa,
            quartet_count,
            gamma=0.0,
            S0=0,
        )
        _, _, left_partition, right_partition = find_min_energy(Q, n, taxa_to_idx)

        print(f"Left partition (0):  {left_partition}", flush=True)
        print(f"Right partition (1): {right_partition}", flush=True)
        print("DONE", flush=True)
