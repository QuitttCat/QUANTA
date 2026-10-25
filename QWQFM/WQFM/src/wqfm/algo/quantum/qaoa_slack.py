import numpy as np
import re
import math
import neal

def _parse_quartet_lines(lines):
    """
    Parse quartet lines in format: ((a,b),(c,d)); weight
    Supports both numeric and named taxa.
    Returns list of tuples: ((a, b), (c, d), weight)
    """
    quartets = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*([\d.]+)', line)
        if match:
            a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
            w = float(match.group(5))
            quartets.append(((a, b), (c, d), w))
    return quartets

def parse_quartet_file(filename):
    with open(filename, 'r') as f:
        return _parse_quartet_lines(f)

def parse_quartet_stdin():
    import sys
    return _parse_quartet_lines(sys.stdin)

def build_qubo_matrix(quartets, A=1.0, B=1.0, gamma=0.0, S0=0, lam=0.0):
    """
    Build QUBO matrix Q from weighted quartets.
    
    Parameters:
    - quartets: list of ((a,b), (c,d), weight) tuples
    - A: penalty for separating intended pairs
    - B: penalty for non-separated cross pairs
    - gamma: strength of balance constraint (optional)
    - S0: target partition size (optional)
    - lam: strength of slack-based extreme partition penalty (optional)
          Enforces 2 <= sum(x) <= n-2 using ancilla/slack bits.
    
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
    
    # Calculate slack bits if needed
    if lam > 0:
        num_slack = math.ceil(math.log2(n - 1))
    else:
        num_slack = 0
    
    total_vars = n + 2 * num_slack
    
    print(f"Number of taxa: {n}")
    print(f"Taxa mapping: {taxa_to_idx}")
    print(f"Number of quartets: {len(quartets)}")
    if lam > 0:
        print(f"Slack bits per constraint: {num_slack}")
        print(f"Total variables: {total_vars} ({n} taxa + {2*num_slack} slack)")
    
    # Initialize QUBO matrix
    Q = np.zeros((total_vars, total_vars))
    
    # Process each quartet
    for (a, b), (c, d), wq in quartets:
        a_idx, b_idx, c_idx, d_idx = taxa_to_idx[a], taxa_to_idx[b], taxa_to_idx[c], taxa_to_idx[d]
        
        # Within-pair cohesion: A * [(xa - xb)^2 + (xc - xd)^2]
        Q[a_idx, a_idx] += wq * A
        Q[b_idx, b_idx] += wq * A
        if a_idx < b_idx:
            Q[a_idx, b_idx] += wq * A * (-2)
        else:
            Q[b_idx, a_idx] += wq * A * (-2)
        
        Q[c_idx, c_idx] += wq * A
        Q[d_idx, d_idx] += wq * A
        if c_idx < d_idx:
            Q[c_idx, d_idx] += wq * A * (-2)
        else:
            Q[d_idx, c_idx] += wq * A * (-2)
        
        # Cross-pair separation: B * sum (xu + xv - 1)^2
        cross_pairs = [(a_idx, c_idx), (a_idx, d_idx), (b_idx, c_idx), (b_idx, d_idx)]
        
        for u_idx, v_idx in cross_pairs:
            Q[u_idx, u_idx] += wq * B * (-1)
            Q[v_idx, v_idx] += wq * B * (-1)
            
            if u_idx < v_idx:
                Q[u_idx, v_idx] += wq * B * 2
            else:
                Q[v_idx, u_idx] += wq * B * 2
    
    # Optional balance constraint: gamma * (sum(xi) - S0)^2
    if gamma > 0:
        for i in range(n):
            Q[i, i] += gamma * (1 - 2*S0)
            for j in range(i+1, n):
                Q[i, j] += gamma * 2
    
    # Slack-based penalty: enforce 2 <= sum(x) <= n-2
    # Constraint 1: (sum(x_i) - 2 - sum_k 2^k y_k)^2 = 0
    # Constraint 2: (n - 2 - sum(x_i) - sum_k 2^k z_k)^2 = 0
    if lam > 0:
        y_start = n
        z_start = n + num_slack
        
        # --- Constraint 1: (sum(x_i) - 2 - sum(2^k * y_k))^2 ---
        
        # [sum x_i]^2 = sum x_i + 2*sum_{i<j} x_i*x_j
        for i in range(n):
            Q[i, i] += lam * 1
            for j in range(i+1, n):
                Q[i, j] += lam * 2
        
        # -4*sum(x_i)
        for i in range(n):
            Q[i, i] += lam * (-4)
        
        # [sum 2^k y_k]^2
        for k in range(num_slack):
            yk = y_start + k
            Q[yk, yk] += lam * (2**k)**2
            for l in range(k+1, num_slack):
                yl = y_start + l
                Q[yk, yl] += lam * 2 * (2**k) * (2**l)
        
        # +4*sum(2^k y_k)
        for k in range(num_slack):
            yk = y_start + k
            Q[yk, yk] += lam * 4 * (2**k)
        
        # -2*sum(x_i)*sum(2^k y_k)
        for i in range(n):
            for k in range(num_slack):
                yk = y_start + k
                if i < yk:
                    Q[i, yk] += lam * (-2) * (2**k)
                else:
                    Q[yk, i] += lam * (-2) * (2**k)
        
        # --- Constraint 2: (n - 2 - sum(x_i) - sum(2^k * z_k))^2 ---
        
        c = n - 2
        
        # [sum x_i]^2
        for i in range(n):
            Q[i, i] += lam * 1
            for j in range(i+1, n):
                Q[i, j] += lam * 2
        
        # -2c * sum(x_i)
        for i in range(n):
            Q[i, i] += lam * (-2) * c
        
        # [sum 2^k z_k]^2
        for k in range(num_slack):
            zk = z_start + k
            Q[zk, zk] += lam * (2**k)**2
            for l in range(k+1, num_slack):
                zl = z_start + l
                Q[zk, zl] += lam * 2 * (2**k) * (2**l)
        
        # -2c * sum(2^k z_k)
        for k in range(num_slack):
            zk = z_start + k
            Q[zk, zk] += lam * (-2) * c * (2**k)
        
        # +2*sum(x_i)*sum(2^k z_k)
        for i in range(n):
            for k in range(num_slack):
                zk = z_start + k
                if i < zk:
                    Q[i, zk] += lam * 2 * (2**k)
                else:
                    Q[zk, i] += lam * 2 * (2**k)
    
    return Q, n, taxa_to_idx

def simulated_annealing(Q, n, num_reads=100, num_sweeps=1000):
    """
    Use simulated annealing to find low-energy bitstring for QUBO matrix Q.
    Returns the best bitstring that satisfies the non-trivial partition
    constraint (2 <= sum(x) <= n-2). Falls back to the overall best if no
    valid sample exists.
    """
    sampler = neal.SimulatedAnnealingSampler()

    total_vars = Q.shape[0]
    Q_dict = {}
    for i in range(total_vars):
        for j in range(i, total_vars):
            if Q[i, j] != 0:
                Q_dict[(i, j)] = Q[i, j]

    sampleset = sampler.sample_qubo(Q_dict, num_reads=num_reads, num_sweeps=num_sweeps)

    for sample, energy in sampleset.data(['sample', 'energy']):
        x_full = np.array([sample.get(i, 0) for i in range(total_vars)])
        x_taxa = x_full[:n]
        s = np.sum(x_taxa)
        if 2 <= s <= n - 2:
            return x_taxa, energy

    print("Warning: all SA samples violate partition constraint; using best available.")
    best_sample = sampleset.first.sample
    x_full = np.array([best_sample.get(i, 0) for i in range(total_vars)])
    return x_full[:n], sampleset.first.energy

def find_min_energy(Q, n, taxa_to_idx):
    """
    Find minimum energy bitstring by brute force enumeration.
    Returns min energy, best bitstring, and partition assignments.
    """
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    total_vars = Q.shape[0]
    
    if n > 20:
        print("Warning: n > 20 may be computationally expensive for brute force enumeration.")
        best_x, best_energy = simulated_annealing(Q, n)
        left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
        right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
        return best_energy, best_x, left_partition, right_partition

    min_energy = float('inf')
    best_x = None
    
    for idx in range(2**total_vars):
        x = np.array([(idx >> j) & 1 for j in range(total_vars)])
        
        taxa_sum = np.sum(x[:n])
        if taxa_sum < 2 or taxa_sum > n - 2:
            continue
            
        e = x @ Q @ x
        if e < min_energy:
            min_energy = e
            best_x = x
    
    if best_x is None:
        best_x = np.zeros(total_vars, dtype=int)
        best_x[n//2:n] = 1
        min_energy = best_x @ Q @ best_x
    
    left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    
    return min_energy, best_x[:n], left_partition, right_partition

if __name__ == "__main__":
    import os, sys

    if not sys.stdin.isatty():
        quartets = parse_quartet_stdin()
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(script_dir, 'quartet.txt')
        quartets = parse_quartet_file(filename)
    print(f"Parsed {len(quartets)} quartets:")
    for q in quartets:
        print(f"  {q}")
    
    # Build QUBO matrix
    print("\nBuilding QUBO matrix...")
    Q, n, taxa_to_idx = build_qubo_matrix(quartets, A=1.0, B=0.4, gamma=0.0, S0=0, lam=10.0)
    
    print(f"\nQUBO matrix shape: {Q.shape}")
    print("QUBO matrix Q:")
    print(Q)
    
    # Find minimum energy partition
    print("\nFinding minimum energy partition...")
    min_energy, best_x, left_partition, right_partition = find_min_energy(Q, n, taxa_to_idx)
    
    print(f"\nMinimum energy: {min_energy}")
    print(f"Best bitstring: {best_x}")
    print(f"Left partition (0):  {left_partition}")
    print(f"Right partition (1): {right_partition}")

    --------------------------------------------------


    import numpy as np
import re
import matplotlib.pyplot as plt
import neal

def _parse_quartet_lines(lines):
    """
    Parse quartet lines in format: ((a,b),(c,d)); weight
    Supports both numeric and named taxa.
    Returns list of tuples: ((a, b), (c, d), weight)
    """
    quartets = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'\(\(([^,]+),([^)]+)\),\(([^,]+),([^)]+)\)\);\s*([\d.]+)', line)
        if match:
            a, b, c, d = match.group(1), match.group(2), match.group(3), match.group(4)
            w = float(match.group(5))
            quartets.append(((a, b), (c, d), w))
    return quartets

def parse_quartet_file(filename):
    with open(filename, 'r') as f:
        return _parse_quartet_lines(f)

def parse_quartet_stdin():
    import sys
    return _parse_quartet_lines(sys.stdin)

def build_qubo_matrix(quartets, A=1.0, B=1.0, gamma=0.0, S0=0):
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

def simulated_annealing(Q, num_reads=100, num_sweeps=1000):
    """
    Use simulated annealing to find low-energy bitstring for QUBO matrix Q.
    Returns the best bitstring that satisfies the non-trivial partition
    constraint (1 < sum(x) < n-1). Falls back to the overall best if no
    valid sample exists.
    """
    sampler = neal.SimulatedAnnealingSampler()

    # Convert QUBO matrix to dictionary format required by neal
    Q_dict = {}
    n = Q.shape[0]
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0:
                Q_dict[(i, j)] = Q[i, j]

    # Sample from the QUBO
    sampleset = sampler.sample_qubo(Q_dict, num_reads=num_reads, num_sweeps=num_sweeps)

    # Iterate samples in ascending energy order; pick first valid one
    for sample, energy in sampleset.data(['sample', 'energy']):
        x = np.array([sample.get(i, 0) for i in range(n)])
        if not (np.sum(x) <= 1 or np.sum(x) >= n - 1):
            return x, energy

    # Fallback: no valid sample found, return overall best
    print("Warning: all SA samples violate partition constraint; using best available.")
    best_sample = sampleset.first.sample
    best_x = np.array([best_sample.get(i, 0) for i in range(n)])
    return best_x, sampleset.first.energy

def find_min_energy(Q, n, taxa_to_idx):
    """
    Find minimum energy bitstring by brute force enumeration.
    Returns min energy, best bitstring, and partition assignments.
    """
    # Create reverse mapping: idx -> taxon name
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    
    if n > 20:
        print("Warning: n > 20 may be computationally expensive for brute force enumeration.")
        best_x, best_energy = simulated_annealing(Q)
            # Build partition result
        left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
        right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
        return best_energy, best_x, left_partition, right_partition

        

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
    
    # Build partition result
    left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    
    return min_energy, best_x, left_partition, right_partition

if __name__ == "__main__":
    import os, sys

    # Read from stdin if data is piped in, otherwise fall back to quartet.txt
    if not sys.stdin.isatty():
        quartets = parse_quartet_stdin()
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(script_dir, 'quartet.txt')
        quartets = parse_quartet_file(filename)
    print(f"Parsed {len(quartets)} quartets:")
    for q in quartets:
        print(f"  {q}")
    
    # Build QUBO matrix
    print("\nBuilding QUBO matrix...")
    Q, n, taxa_to_idx = build_qubo_matrix(quartets, A=1.0, B=0.4, gamma=0.0, S0=0)
    
    print(f"\nQUBO matrix shape: {Q.shape}")
    print("QUBO matrix Q:")
    print(Q)
    
    # Find minimum energy partition
    print("\nFinding minimum energy partition...")
    min_energy, best_x, left_partition, right_partition = find_min_energy(Q, n, taxa_to_idx)
    
    print(f"\nMinimum energy: {min_energy}")
    print(f"Best bitstring: {best_x}")
    print(f"Left partition (0):  {left_partition}")
    print(f"Right partition (1): {right_partition}")

    -----------------------------------------------------------

    import numpy as np
import re
import matplotlib.pyplot as plt
import neal

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

def build_qubo_matrix(quartets, A=1.0, B=1.0, gamma=0.0, S0=0):
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

def simulated_annealing(Q, num_reads=100, num_sweeps=1000):
    """
    Use simulated annealing to find low-energy bitstring for QUBO matrix Q.
    Returns best bitstring and its energy.
    """
    sampler = neal.SimulatedAnnealingSampler()
    
    # Convert QUBO matrix to dictionary format required by neal
    Q_dict = {}
    n = Q.shape[0]
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0:
                Q_dict[(i, j)] = Q[i, j]
    
    # Sample from the QUBO
    sampleset = sampler.sample_qubo(Q_dict, num_reads=num_reads, num_sweeps=num_sweeps)
    
    # Get best sample
    best_sample = sampleset.first.sample
    best_energy = sampleset.first.energy
    
    # Convert sample dict to bitstring array
    best_x = np.array([best_sample.get(i, 0) for i in range(n)])
    
    return best_x, best_energy

def find_min_energy(Q, n, taxa_to_idx):
    """
    Find minimum energy bitstring by brute force enumeration.
    Returns min energy, best bitstring, and partition assignments.
    """
    # Create reverse mapping: idx -> taxon name
    idx_to_taxa = {idx: taxon for taxon, idx in taxa_to_idx.items()}
    
    if n > 20:
        print("Warning: n > 20 may be computationally expensive for brute force enumeration.")
        best_x, best_energy = simulated_annealing(Q)
            # Build partition result
        left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
        right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
        return best_energy, best_x, left_partition, right_partition

        

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
    
    # Build partition result
    left_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 0]
    right_partition = [idx_to_taxa[i] for i in range(n) if best_x[i] == 1]
    
    return min_energy, best_x, left_partition, right_partition

if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, 'quartet.txt')
    
    # Parse quartets
    quartets = parse_quartet_file(filename)
    print(f"Parsed {len(quartets)} quartets:")
    for q in quartets:
        print(f"  {q}")
    
    # Build QUBO matrix
    print("\nBuilding QUBO matrix...")
    Q, n, taxa_to_idx = build_qubo_matrix(quartets, A=1.0, B=0.4, gamma=0.0, S0=0)
    
    print(f"\nQUBO matrix shape: {Q.shape}")
    print("QUBO matrix Q:")
    print(Q)
    
    # Find minimum energy partition
    print("\nFinding minimum energy partition...")
    min_energy, best_x, left_partition, right_partition = find_min_energy(Q, n, taxa_to_idx)
    
    print(f"\nMinimum energy: {min_energy}")
    print(f"Best bitstring: {best_x}")
    print(f"Left partition (0):  {left_partition}")
    print(f"Right partition (1): {right_partition}")