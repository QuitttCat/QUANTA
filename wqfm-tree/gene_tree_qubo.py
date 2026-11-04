#!/usr/bin/env python3
"""QUANTA's QUBO built directly from gene trees, without listing quartets.

QUANTA (qaoa.StreamingQuboAccumulator) adds, for every quartet ab|cd of
weight w: (A - 2B) w to each of Q_aa..Q_dd, -2A w to Q_ab and Q_cd (sibling
pairs) and +2B w to the four cross pairs. With quartet weights equal to the
number of gene trees inducing each topology, Q only needs, per gene tree,

  pair_ij  = number of quartets ij|kl displayed by the tree, and
  cross_ij = number of quartets ik|jl or il|jk = C(n-2, 2) - pair_ij

(binary gene trees on all n taxa). In an unrooted binary tree ij|kl holds
iff k and l hang off the same internal vertex of the i-j path, so
pair_ij = sum over interior vertices v of the path of C(h_v, 2), where h_v is
the size of the subtree hanging off v. Rooting the tree anywhere, that sum
splits at the lowest common ancestor L of i and j:
  (up-sum from i to L's child) + (up-sum from j to L's other child)
  + C(size of the part of the tree outside L's two branches, 2),
so each tree costs O(n^2): every pair is touched once, at its LCA.

`python gene_tree_qubo.py --check` verifies Q against qaoa.py's own
quartet-based accumulator on small random gene trees.
"""

import argparse
import itertools
import random
import sys
import time
from pathlib import Path

import dendropy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "QWQFM" / "WQFM" / "src" / "wqfm" / "algo" / "quantum"))


def choose2(x):
    return x * (x - 1) / 2.0


def read_gene_trees(path):
    taxa = dendropy.TaxonNamespace()
    trees = dendropy.TreeList.get(path=str(path), schema="newick", taxon_namespace=taxa,
                                  rooting="force-unrooted")
    labels = sorted((t.label for t in taxa), key=lambda s: (len(s), s))
    return trees, labels


def pair_counts(tree, index, n):
    """pair_ij for one binary gene tree on all n taxa, as an n x n matrix (both triangles)."""
    leaves, up = {}, {}
    for node in tree.postorder_node_iter():
        if node.is_leaf():
            leaves[node] = np.array([index[node.taxon.label]], dtype=np.intp)
        else:
            leaves[node] = np.concatenate([leaves[c] for c in node.child_nodes()])
    if sum(len(leaves[c]) for c in tree.seed_node.child_nodes()) != n:
        raise ValueError("gene tree does not contain every taxon")
    # up[x]: sum of C(h, 2) over the vertices passed when walking from x to the root,
    # excluding the root; h is the subtree hanging off each vertex (x's sibling side).
    leaf_up = np.zeros(n)
    for node in tree.preorder_node_iter():
        children = node.child_nodes()
        if node is not tree.seed_node and len(children) not in (0, 2):
            raise ValueError("gene tree is not binary")
        base = up.get(node, 0.0) if node is not tree.seed_node else 0.0
        for child in children:
            up[child] = base + sum(choose2(len(leaves[s])) for s in children if s is not child)
            if child.is_leaf():
                leaf_up[leaves[child][0]] = up[child]
    if len(tree.seed_node.child_nodes()) > 3:
        raise ValueError("gene tree is not binary")

    P = np.zeros((n, n))
    for node in tree.postorder_node_iter():
        children = node.child_nodes()
        if not children:
            continue
        outside = n - len(leaves[node])
        for a, b in itertools.combinations(children, 2):
            hanging = choose2(outside) + sum(choose2(len(leaves[c])) for c in children if c is not a and c is not b)
            la, lb = leaves[a], leaves[b]
            P[np.ix_(la, lb)] += (leaf_up[la] - up[a])[:, None] + (leaf_up[lb] - up[b])[None, :] + hanging
    return P + P.T


def build_qubo(trees, labels, A=1.0, B=0.4):
    """Upper-triangular Q in qaoa.py's convention, plus the summed pair/cross matrices."""
    n = len(labels)
    index = {label: i for i, label in enumerate(labels)}
    pair = np.zeros((n, n))
    for tree in trees:
        pair += pair_counts(tree, index, n)
    k = len(trees)
    cross = k * choose2(n - 2) - pair
    np.fill_diagonal(cross, 0.0)
    omega = k * (n - 1) * (n - 2) * (n - 3) / 6.0  # quartets containing a given taxon
    Q = np.triu(-2 * A * pair + 2 * B * cross, k=1)
    Q[np.diag_indices(n)] = (A - 2 * B) * omega
    return Q, pair, cross


def quartet_counts(x, pair, cross, k):
    """Satisfied, deferred (3-1) and violated quartet weight of bipartition x (0/1 array).

    Separated sibling-pair weight p = D + 2V, separated cross weight c = 4S + 2D + 2V,
    and S + V = k C(|A|,2) C(|B|,2) for binary gene trees on all taxa.
    """
    x = np.asarray(x, dtype=bool)
    p = pair[np.ix_(x, ~x)].sum()
    c = cross[np.ix_(x, ~x)].sum()
    t22 = k * choose2(x.sum()) * choose2((~x).sum())
    s = (c - 2 * p + 2 * t22) / 6.0
    v = t22 - s
    return s, p - 2 * v, v


# ---------------------------------------------------------------- verification
def _leaf_distances(tree, labels):
    """Edge-count distances between leaves (four-point condition on topology)."""
    index = {label: i for i, label in enumerate(labels)}
    adj = {}
    for node in tree.preorder_node_iter():
        for child in node.child_nodes():
            adj.setdefault(node, []).append(child)
            adj.setdefault(child, []).append(node)
    leaves = [nd for nd in tree.leaf_node_iter()]
    n = len(labels)
    D = np.zeros((n, n), dtype=int)
    for leaf in leaves:
        dist, frontier = {leaf: 0}, [leaf]
        while frontier:
            nxt = []
            for u in frontier:
                for w in adj.get(u, []):
                    if w not in dist:
                        dist[w] = dist[u] + 1
                        nxt.append(w)
            frontier = nxt
        for other in leaves:
            D[index[leaf.taxon.label], index[other.taxon.label]] = dist[other]
    return D


def check(trials=3, n=13, genes=15, seed=7):
    import qaoa
    from dendropy.simulate import treesim

    rng = random.Random(seed)
    for trial in range(trials):
        species = treesim.birth_death_tree(birth_rate=1.0, death_rate=0.0, num_extant_tips=n, rng=rng)
        for i, leaf in enumerate(species.leaf_node_iter(), start=1):
            leaf.taxon.label = f"t{i}"
        taxa = species.taxon_namespace
        trees = dendropy.TreeList(taxon_namespace=taxa)
        for _ in range(genes):
            mapping = dendropy.TaxonNamespaceMapping.create_contained_taxon_mapping(taxa, 1)
            gene = treesim.contained_coalescent_tree(species, mapping, rng=rng)
            for leaf in gene.leaf_node_iter():  # gene lineage "t5 1" -> species "t5"
                leaf.taxon.label = leaf.taxon.label.rsplit(" ", 1)[0]
            newick = gene.as_string(schema="newick", suppress_edge_lengths=True, suppress_rooting=True)
            trees.append(dendropy.Tree.get(data=newick, schema="newick", taxon_namespace=taxa,
                                           rooting="force-unrooted"))
        labels = sorted((t.label for t in taxa), key=lambda s: (len(s), s))
        Q, pair, cross = build_qubo(trees, labels)

        acc = qaoa.StreamingQuboAccumulator(A=1.0, B=0.4)
        for label in labels:  # same index order as build_qubo
            acc._taxon_index(label)
        for tree in trees:
            D = _leaf_distances(tree, labels)
            for a, b, c, d in itertools.combinations(range(n), 4):
                sums = [(D[a, b] + D[c, d], (a, b, c, d)), (D[a, c] + D[b, d], (a, c, b, d)),
                        (D[a, d] + D[b, c], (a, d, b, c))]
                sums.sort()
                if sums[0][0] < sums[1][0]:  # resolved
                    p, q, r, s = sums[0][1]
                    acc.add(labels[p], labels[q], labels[r], labels[s], 1.0)
        reference, _, _ = acc.finish()
        ok = np.allclose(Q, reference)
        x = np.array([rng.random() < 0.5 for _ in range(n)])
        s, d, v = quartet_counts(x, pair, cross, len(trees))
        energy = float(x.astype(float) @ Q @ x.astype(float))
        ok_energy = np.isclose(energy, -1.6 * s + 0.2 * d + 1.2 * v)
        print(f"trial {trial}: Q matches quartet accumulator: {ok} (max |diff| "
              f"{np.abs(Q - reference).max():.2e}); energy = -1.6S + 0.2D + 1.2V: {ok_energy}")
        if not (ok and ok_energy):
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--gene-trees")
    args = parser.parse_args()
    if args.check:
        check()
    elif args.gene_trees:
        start = time.time()
        trees, labels = read_gene_trees(args.gene_trees)
        Q, _, _ = build_qubo(trees, labels)
        print(f"n={len(labels)} genes={len(trees)} QUBO built in {time.time() - start:.1f} s")
