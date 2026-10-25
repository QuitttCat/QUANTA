# QUANTA with classical QUBO solvers: biological, 101, 144 and 200 taxa

All commands are run from the **repository root**.

These runs replace the D-Wave QPU (and, for partitions above 150 taxa, Leap
Hybrid) with a classical QUBO solver from `dwave-samplers` for every partition
with more than 20 taxa: simulated annealing (`sa`) or tabu search (`tabu`),
1000 reads, lowest-energy sample with at least two taxa per side. Partitions of
20 taxa or fewer are still solved by brute force, so only the solver changes.
The solver is plugged in through `WQFM_QUBO_SCRIPT`
(`QWQFM/WQFM/src/wqfm/algo/quantum/qaoa_classical.py`); `qaoa.py` is unchanged.
No D-Wave token is used.

The 37- and 48-taxon runs are in `result_analysis/37 Taxa/` and `48 Taxa/`
(`run_37_taxa_classical.sh`, `run_48_taxa_classical.sh`).

## Run

```bash
JOBS=4 bash "result_analysis/classical solvers/run_classical.sh" biological sa
JOBS=4 bash "result_analysis/classical solvers/run_classical.sh" biological tabu
```

`JOBS` is the number of inputs run at once. Finished inputs are skipped, so an
interrupted run resumes with the same command.

**Memory.** The biological runs need about 0.65 GB each and fit a laptop.
101, 144 and 200 taxa need the server, with the Java heap of their QPU runs
(set by the script): 16 GB for 101 and 144, 26 GB for 200. Pick `JOBS` so
`JOBS × heap` fits in the server's RAM:

```bash
JOBS=2 bash "result_analysis/classical solvers/run_classical.sh" 101 sa
JOBS=2 bash "result_analysis/classical solvers/run_classical.sh" 101 tabu
bash "result_analysis/classical solvers/run_classical.sh" 144 sa
bash "result_analysis/classical solvers/run_classical.sh" 144 tabu
bash "result_analysis/classical solvers/run_classical.sh" 200 sa
bash "result_analysis/classical solvers/run_classical.sh" 200 tabu
```

## Outputs

| What | Where |
|---|---|
| Results CSV | `result_analysis/classical solvers/result/results_<group>_<solver>_plus_bruteforce_n>20.csv` |
| Per-input trees, logs, scores | `QWQFM/benchmark/work/<group>_<solver>_n_gt_20/<input>/` |

Columns: `quartet_file_name`, the tree, `rf_<solver>_wrt_reference` and
`reference` (101: the replicate's true species tree; 144 and 200: the input
gene tree; empty for biological), the weighted quartet score, total quartet
weight and their fraction (four-point test, `baselines/scripts/score_tree.py`,
the scorer used for all methods), the solver's sampler time, brute-force time
and their sum, the number of sampler calls, and the number of balanced
fallbacks (inputs where no sample had at least two taxa per side).
