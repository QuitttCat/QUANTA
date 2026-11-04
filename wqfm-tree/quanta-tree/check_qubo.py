#!/usr/bin/env python3
"""Verify QuboBuilder (Java) against brute-force quartet counting.

For every subproblem dumped by QFMQubo (QUBO_DUMP_DIR), enumerate all
quartets of every gene tree, keep those whose four taxa lie in four different
units, weight each by the product of the taxon weights, and feed them to
QUANTA's own qaoa.StreamingQuboAccumulator. The result must equal the Java Q.
Usage: python check_qubo.py gene_trees.tre dump_dir
"""

import itertools
import sys
from pathlib import Path

import dendropy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gene_tree_qubo import _leaf_distances  # noqa: E402
import qaoa  # noqa: E402  (path added by gene_tree_qubo)


def main(gene_trees, dump_dir):
    taxa = dendropy.TaxonNamespace()
    trees = dendropy.TreeList.get(path=gene_trees, schema="newick", taxon_namespace=taxa, rooting="force-unrooted")
    labels = sorted(t.label for t in taxa)
    topologies = []  # per tree: list of (a, b, c, d) meaning ab|cd
    for tree in trees:
        D = _leaf_distances(tree, labels)
        resolved = []
        for a, b, c, d in itertools.combinations(range(len(labels)), 4):
            sums = sorted([(D[a, b] + D[c, d], (a, b, c, d)), (D[a, c] + D[b, d], (a, c, b, d)),
                           (D[a, d] + D[b, c], (a, d, b, c))])
            if sums[0][0] < sums[1][0]:
                resolved.append(sums[0][1])
        topologies.append(resolved)

    worst = 0.0
    files = sorted(Path(dump_dir).glob("subproblem_*.txt"), key=lambda p: int(p.stem.split("_")[1]))
    for path in files:
        lines = path.read_text().splitlines()
        split = lines.index("Q")
        unit_of, weight = {}, {}
        for u, line in enumerate(lines[:split]):
            for item in line.split():
                label, w = item.rsplit(":", 1)
                unit_of[labels.index(label)] = u
                weight[labels.index(label)] = float(w)
        m = split
        Q_java = np.array([[float(v) for v in row.split()] for row in lines[split + 1:]])
        acc = qaoa.StreamingQuboAccumulator(A=1.0, B=0.4)
        for u in range(m):
            acc._taxon_index(u)
        for resolved in topologies:
            for a, b, c, d in resolved:
                units = (unit_of[a], unit_of[b], unit_of[c], unit_of[d])
                if len(set(units)) == 4:
                    acc.add(*units, weight[a] * weight[b] * weight[c] * weight[d])
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            Q_ref, _, _ = acc.finish()
        diff = np.abs(np.triu(Q_ref) - Q_java).max() / max(1.0, np.abs(Q_ref).max())
        worst = max(worst, diff)
        dummies = sum(1 for line in lines[:split] if " " in line or float(line.rsplit(":", 1)[1]) != 1.0)
        print(f"{path.name}: units={m} dummies={dummies} max relative diff={diff:.2e}")
    print(f"{len(files)} subproblems, worst relative difference {worst:.2e}")
    sys.exit(0 if worst < 1e-9 else 1)


if __name__ == "__main__":
    main(*sys.argv[1:])
