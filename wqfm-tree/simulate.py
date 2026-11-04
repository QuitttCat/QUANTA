#!/usr/bin/env python3
"""Simulate one replicate of gene trees per taxon count with DendroPy.

Species tree: Yule (pure birth) with the given number of tips, rescaled to a
fixed height in coalescent units. Gene trees: the multispecies coalescent
inside that species tree, one lineage per species (DendroPy's
contained_coalescent_tree, population size 1, so branch lengths are in
coalescent units). Gene trees are written unrooted, without branch lengths,
one per line, which is the input format of wQFM-TREE.

Writes data/<n>_taxa/{species_tree.tre,gene_trees.tre,info.json}.
Usage: python simulate.py [--taxa 200 500 1000] [--genes 200] [--height 20] [--seed 1]
"""

import argparse
import json
import random
import time
from multiprocessing import Pool
from pathlib import Path

import dendropy
from dendropy.calculate import treecompare
from dendropy.simulate import treesim

HERE = Path(__file__).resolve().parent


def species_tree(n, height, seed):
    tree = treesim.birth_death_tree(birth_rate=1.0, death_rate=0.0, num_extant_tips=n,
                                    rng=random.Random(seed))
    for i, leaf in enumerate(tree.leaf_node_iter(), start=1):
        leaf.taxon.label = f"t{i}"
    tree.calc_node_ages()
    scale = height / tree.seed_node.age
    for edge in tree.postorder_edge_iter():
        if edge.length is not None:
            edge.length *= scale
    return tree


def one_gene(job):
    newick, seed = job
    species = dendropy.Tree.get(data=newick, schema="newick", rooting="force-rooted")
    mapping = dendropy.TaxonNamespaceMapping.create_contained_taxon_mapping(
        containing_taxon_namespace=species.taxon_namespace, num_contained=1)
    gene = treesim.contained_coalescent_tree(species, mapping, rng=random.Random(seed))
    for leaf in gene.leaf_node_iter():  # gene lineage "t5 1" -> species "t5"
        leaf.taxon.label = leaf.taxon.label.rsplit(" ", 1)[0]
    return gene.as_string(schema="newick", suppress_edge_lengths=True, suppress_rooting=True,
                          suppress_internal_node_labels=True).strip()


def discordance(species, gene_lines, sample=50):
    """Mean normalised RF between the species tree and the first `sample` gene trees."""
    taxa = species.taxon_namespace
    species = dendropy.Tree.get(data=species.as_string(schema="newick"), schema="newick",
                                taxon_namespace=taxa, rooting="force-unrooted")
    n = len(taxa)
    total = 0.0
    for line in gene_lines[:sample]:
        gene = dendropy.Tree.get(data=line, schema="newick", taxon_namespace=taxa, rooting="force-unrooted")
        total += treecompare.symmetric_difference(species, gene) / (2 * (n - 3))
    return total / min(sample, len(gene_lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxa", type=int, nargs="+", default=[200, 500, 1000])
    parser.add_argument("--genes", type=int, default=200)
    parser.add_argument("--height", type=float, default=20.0, help="species tree height (coalescent units)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()

    for n in args.taxa:
        out = HERE / "data" / f"{n}_taxa"
        out.mkdir(parents=True, exist_ok=True)
        start = time.time()
        species = species_tree(n, args.height, args.seed)
        newick = species.as_string(schema="newick", suppress_rooting=False).strip()
        (out / "species_tree.tre").write_text(newick + "\n")
        jobs = [(newick, args.seed * 1_000_003 + n * 10_007 + g) for g in range(args.genes)]
        with Pool(args.jobs) as pool:
            genes = pool.map(one_gene, jobs, chunksize=4)
        (out / "gene_trees.tre").write_text("\n".join(genes) + "\n")
        info = {"taxa": n, "genes": args.genes, "species_tree_height_cu": args.height, "seed": args.seed,
                "model": "Yule species tree + multispecies coalescent (DendroPy "
                         f"{dendropy.__version__}), one lineage per species",
                "mean_gene_species_nrf_first50": round(discordance(species, genes), 4),
                "simulation_seconds": round(time.time() - start, 1)}
        (out / "info.json").write_text(json.dumps(info, indent=2) + "\n")
        print(json.dumps(info), flush=True)


if __name__ == "__main__":
    main()
