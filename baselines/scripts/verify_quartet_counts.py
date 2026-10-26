#!/usr/bin/env python3
"""Check that a set of gene trees reproduces a weighted-quartet file.

A weighted-quartet file built by counting the quartets of a set of gene
trees ("((a,b),(c,d)); w" = w gene trees induce ab|cd) carries exactly the
quartet information ASTRAL scores on those gene trees. This script draws
random four-taxon sets, counts the three topologies over the gene trees
(by the four-point condition on edge-count distances) and compares them
with the weights in the file. Every count must match.

    QWQFM/.venv/bin/python baselines/scripts/verify_quartet_counts.py \
        --gene-trees GENE_TREES --quartets QUARTETS [--samples 2000]
"""

import argparse
import itertools
import random
import re
import sys
from collections import Counter

import dendropy

QUARTET = re.compile(r"^\(\(([^,()]+),([^,()]+)\),\(([^,()]+),([^,()]+)\)\);?\s*([0-9.eE+-]+)\s*$")


def split(a, b, c, d):
    return frozenset((frozenset((a, b)), frozenset((c, d))))


def leaf_distances(tree):
    """Edge-count distance between every pair of leaf labels of one tree."""
    adjacency = {}
    for node in tree.preorder_node_iter():
        adjacency.setdefault(node, [])
        if node.parent_node is not None:
            adjacency[node].append(node.parent_node)
            adjacency[node.parent_node].append(node)
    leaves = {leaf: leaf.taxon.label for leaf in tree.leaf_node_iter()}
    distances = {}
    for leaf, label in leaves.items():
        seen, frontier, depth = {leaf}, [leaf], 0
        row = {}
        while frontier:
            depth += 1
            nxt = []
            for node in frontier:
                for other in adjacency[node]:
                    if other not in seen:
                        seen.add(other)
                        nxt.append(other)
                        if other in leaves:
                            row[leaves[other]] = depth
            frontier = nxt
        distances[label] = row
    return distances


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gene-trees", required=True)
    parser.add_argument("--quartets", required=True)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    trees = dendropy.TreeList.get(path=args.gene_trees, schema="newick", preserve_underscores=True,
                                  rooting="force-unrooted")
    taxa = sorted({leaf.taxon.label for tree in trees for leaf in tree.leaf_node_iter()})
    rng = random.Random(args.seed)
    sample = set()
    while len(sample) < args.samples:
        sample.add(frozenset(rng.sample(taxa, 4)))

    expected = Counter()  # split -> weight in the file, for the sampled four-taxon sets
    with open(args.quartets) as handle:
        for line in handle:
            match = QUARTET.match(line)
            if not match:
                continue
            a, b, c, d, weight = match.groups()
            if frozenset((a, b, c, d)) in sample:
                expected[split(a, b, c, d)] += float(weight)

    observed = Counter()
    for tree in trees:
        dist = leaf_distances(tree)
        for four in sample:
            a, b, c, d = sorted(four)
            sums = {split(a, b, c, d): dist[a][b] + dist[c][d],
                    split(a, c, b, d): dist[a][c] + dist[b][d],
                    split(a, d, b, c): dist[a][d] + dist[b][c]}
            best = min(sums.values())
            winners = [s for s, v in sums.items() if v == best]
            if len(winners) == 1:  # an unresolved quartet supports no topology
                observed[winners[0]] += 1

    keys = set(expected) | set(observed)
    mismatches = [k for k in keys if abs(expected[k] - observed[k]) > 1e-9]
    print(f"{len(trees)} gene trees, {len(taxa)} taxa, {len(sample)} random four-taxon sets, "
          f"{len(keys)} topologies compared, {len(mismatches)} mismatches")
    for key in itertools.islice(mismatches, 5):
        print("  mismatch", sorted(map(sorted, key)), "file", expected[key], "gene trees", observed[key])
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
