# 200-taxon dataset: ASTRAL, simulated annealing and tabu search

All commands are run from the **repository root**.

Input: one true gene tree of the s200 simulated dataset (replicate 1, 200 taxa)
and its 64,684,950 weighted quartets, in `QWQFM/WQFM/input_files/`:

- `200-taxa-s200-rep01-true-gene-tree/s200_rep01_true_gene_tree_001_200_taxa.tre`
- `200-taxa-s200-rep01-true-gene-tree-weighted-quartets/s200_rep01_true_gene_tree_001_200_taxa.weighted_quartets`

## Run

```bash
bash "result_analysis/200 Taxa/run_200_taxa.sh"              # astral, sa, tabu in turn
bash "result_analysis/200 Taxa/run_200_taxa.sh" astral       # one method
bash "result_analysis/200 Taxa/run_200_taxa.sh" sa tabu      # several
```

| Method | What runs |
|---|---|
| `astral` | ASTER `astral4` on the gene tree itself, single-threaded (`baselines/scripts/run_astral.py --only 200`) |
| `sa` | QUANTA with simulated annealing for partitions with n > 20 taxa, brute force below (`result_analysis/classical solvers/run_classical.sh 200 sa`) |
| `tabu` | the same with tabu search |

Requirements: the Python environment `QWQFM/.venv` (`requirements.txt`), Java
and Apache Ant (the script falls back to `~/.local/opt/apache-ant-1.10.15`).
No D-Wave token is used.

**Memory.** `sa` and `tabu` each use a 26 GB Java heap (`-Xms4g -Xmx26g`, set
by `run_classical.sh`). Run them together only on a machine with more than
about 56 GB of free RAM; otherwise run them one after the other. ASTRAL needs
very little memory.

Finished runs are skipped on rerun.

## Outputs

| What | Where |
|---|---|
| ASTRAL results | `result/astral_200_taxa.csv` |
| Simulated annealing results | `result/results_200_simulated_annealing_plus_bruteforce_n>20.csv` |
| Tabu search results | `result/results_200_tabu_search_plus_bruteforce_n>20.csv` |
| Run logs | `logs/` |
| Per-run trees, logs, scores | `baselines/results/astral/200/`, `QWQFM/benchmark/work/200_<solver>_n_gt_20/` |

Every tree is scored by its weighted quartet score against the input quartets
and by normalized RF distance to the input gene tree (the same scorer,
`baselines/scripts/score_tree.py`, for all methods). A perfect result has
quartet score fraction 1 and RF 0.
