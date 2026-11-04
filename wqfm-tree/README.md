# QUANTA's QUBO from gene trees (wQFM-TREE setting)

Builds QUANTA's bipartition QUBO directly from gene trees, without listing
quartets, for the root division step of 200-, 500- and 1000-taxon datasets.
It solves the QUBO with D-Wave as QUANTA does for partitions above 150 taxa, and
scores the bipartition against the true species tree. The whole folder is
git-ignored.

| Path | What |
|---|---|
| `official/` | official wQFM-TREE (github.com/abdur-rafi/wQFM-TREE, commit 7d7c24b) |
| `simulate.py` | DendroPy simulation: Yule species tree (height 20 coalescent units) + 200 multispecies-coalescent gene trees, one replicate per size |
| `data/<n>_taxa/` | `species_tree.tre`, `gene_trees.tre` (wQFM-TREE input format), `info.json` |
| `gene_tree_qubo.py` | Q from gene trees in O(n^2) per tree (pair counts summed at each pair's LCA); `--check` verifies Q against `qaoa.py`'s quartet accumulator |
| `solve_root.py` | builds Q, solves with `qaoa.leap_hybrid_annealing` (Leap Hybrid, 30 s, at least 2 taxa per side), scores against the species tree |
| `results/` | `root_bipartition_<n>_taxa_<solver>.json`, `summary_<solver>.csv`, `compare.csv` |
| `quanta-tree/` | wQFM-TREE source + QUANTA's QUBO in place of consensus start and FM (`QuboBuilder`, `QFMQubo`, `QuboSolverProcess`; `Main ... A QUBO`), solved by `qubo_solver.py` (QUANTA's exhaustive search / SA) |
| `quanta-tree/check_qubo.py` | verifies every subproblem's Q (with dummy taxa) against brute-force quartet counting |
| `compare.py` | end-to-end runs: official wQFM-TREE vs QUANTA in wQFM-TREE; RF to the true tree, time, memory |

Build and compare:

```bash
cd quanta-tree && javac -d build -sourcepath . src/Main.java && cd ..
../QWQFM/.venv/bin/python compare.py --taxa 200 500 1000    # runs/<n>_taxa/, results/compare.csv
```

Run from this folder with the project environment (`../QWQFM/.venv/bin/python`):

```bash
python simulate.py                       # data/ (already generated, seed 1)
python gene_tree_qubo.py --check         # Q equals the quartet-based Q
python solve_root.py --reference-only    # species-tree reference, no D-Wave
DWAVE_ENV_FILE=../.env source ../load-dwave-token.sh
python solve_root.py                     # Leap Hybrid on 200, 500, 1000 taxa
```

Dense QUBOs of 200 or more variables cannot be embedded on the QPU directly
(the largest clique is about 177-180), so the hybrid solver is used, as in
QUANTA's 200-taxon run.
