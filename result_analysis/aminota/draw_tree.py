#!/usr/bin/env python3
"""Draw one Newick tree as a rooted, ladderized cladogram using Bio.Phylo."""

import argparse
import io
from pathlib import Path

from Bio import Phylo
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tree", help="Newick tree file")
    source.add_argument("--newick", help="Newick tree string")
    parser.add_argument("--out", required=True, help="output figure path (.png/.pdf/.svg)")
    parser.add_argument("--outgroup", help="taxon to root the tree on")
    parser.add_argument("--title", default="", help="figure title")
    return parser.parse_args()


def main():
    args = parse_args()
    tree = Phylo.read(args.tree if args.tree else io.StringIO(args.newick), "newick")
    if args.outgroup:
        tree.root_with_outgroup(args.outgroup)
    tree.ladderize(reverse=True)

    leaves = tree.count_terminals()
    fig, ax = plt.subplots(figsize=(8, 0.4 * leaves + 1.5))
    Phylo.draw(tree, axes=ax, do_show=False)
    ax.set_title(args.title, fontsize=13)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure saved: {out}")


if __name__ == "__main__":
    main()
