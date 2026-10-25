# 37-taxon benchmark: wQFM vs wQ²A (D-Wave QPU)

All commands are run from the **repository root** (the directory that contains
`QWQFM/` and `result_analysis/`). Every path below is relative to it.

## Requirements

- Java (JDK 17+) and Apache Ant — used to build and run wQFM
- Python virtual environment at `QWQFM/.venv` with `dwave-ocean-sdk`, `dendropy` and `matplotlib`
- Input quartet files in `QWQFM/WQFM/input_files/37-taxa-weighted-quartets/`
  (240 files: 12 conditions × 20 replicates)
- **A D-Wave Leap API token with QPU access.** Unlike the 11- and 15-taxon
  datasets, 37 taxa produce partitions with more than 20 taxa; wQ²A sends those
  to the D-Wave QPU and solves smaller partitions (n ≤ 20) by brute force.

Provide the token in either of two ways:

```bash
export DWAVE_API_TOKEN="your-token-here"
```

or put this line in `.env` at the repository root:

```
DWAVE_API_TOKEN=your-token-here
```

Without a token the benchmark stops immediately with
`Error: DWAVE_API_TOKEN is not set`, before running anything.

**Cost note:** a full run makes QPU calls for every replicate (240 files) and
uses Leap QPU time from your account.

## Results already included

`result_analysis/37 Taxa/result/results_37_taxa_qpu_plus_bruteforce_n>20.csv`
is the CSV from our QPU run (threshold n > 20). The figure
`result_analysis/37 Taxa/figure/results_37_taxa_qpu_plus_bruteforce_n_gt_20.pdf`
is drawn from it, together with the wQMC and ASTRAL results in
`baselines/results/` (see `baselines/commands.md`). To redraw it without the QPU:

```bash
QWQFM/.venv/bin/python "result_analysis/37 Taxa/graph.py" \
  --csv "result_analysis/37 Taxa/result/results_37_taxa_qpu_plus_bruteforce_n>20.csv" \
  --out "result_analysis/37 Taxa/figure/results_37_taxa_qpu_plus_bruteforce_n_gt_20.pdf"
```

## Solver comparison (QPU vs simulated annealing vs tabu search)

QUANTA was also run with a classical QUBO solver in place of the QPU for
partitions with n > 20 taxa (simulated annealing or tabu search from
dwave-samplers, 1000 reads, same sample selection); smaller partitions are
still solved by brute force. No D-Wave token is used. `JOBS` runs that many
quartet files at once:

```bash
JOBS=6 bash "result_analysis/37 Taxa/run_37_taxa_classical.sh" sa
JOBS=6 bash "result_analysis/37 Taxa/run_37_taxa_classical.sh" tabu
```

Results: `result/results_37_taxa_{simulated_annealing,tabu_search}_plus_bruteforce_n>20.csv`.
The figure comparing the three solvers:

```bash
QWQFM/.venv/bin/python "result_analysis/37 Taxa/graph_solvers.py" \
  --qpu-csv "result_analysis/37 Taxa/result/results_37_taxa_qpu_plus_bruteforce_n>20.csv" \
  --sa-csv "result_analysis/37 Taxa/result/results_37_taxa_simulated_annealing_plus_bruteforce_n>20.csv" \
  --tabu-csv "result_analysis/37 Taxa/result/results_37_taxa_tabu_search_plus_bruteforce_n>20.csv" \
  --out "result_analysis/37 Taxa/figure/results_37_taxa_solver_comparison.pdf"
```

## Reproduce the benchmark (one command, needs the token)

Default output name (`results_37_taxa.csv`):

```bash
bash "result_analysis/37 Taxa/run_37_taxa.sh"
```

Custom output name:

```bash
bash "result_analysis/37 Taxa/run_37_taxa.sh" my_run.csv
```

The script:

1. runs wQFM and wQ²A on all 240 quartet files with the full JVM heap
   (`-Xmx6g -Xms6g`; override by exporting `JAVA_TOOL_OPTIONS` first),
2. scores both trees by normalized Robinson–Foulds distance against the
   37-taxon true species tree,
3. copies the CSV into `result_analysis/37 Taxa/result/`,
4. draws the figure into `result_analysis/37 Taxa/figure/`.

Because QPU sampling is stochastic, wQ²A trees can differ slightly between runs;
wQFM results are deterministic.

Lower the heap if your machine has less than ~8 GB RAM:

```bash
JAVA_TOOL_OPTIONS="-Xmx3g" bash "result_analysis/37 Taxa/run_37_taxa.sh"
```

## Outputs

| What | Where |
|---|---|
| Results CSV | `result_analysis/37 Taxa/result/<name>.csv` |
| Figure | `result_analysis/37 Taxa/figure/<name>.pdf` |
| Per-file trees and logs | `QWQFM/benchmark/work/<name>/<quartet_file>/{wqfm,quantum}.{tre,log}` |

CSV columns: `quartet_file_name, wqfm_tree, quantum_annealing_tree,
rf_wqfm_wrt_base, rf_quantum_wrt_base, better, wqfm_bipartition_time_seconds,
quantum_qpu_access_time_seconds, quantum_bruteforce_time_seconds, quantum_time_seconds`.
The `quantum_*` columns hold the wQ²A results. `better` is `1` if wQ²A has the
lower RF distance, `-1` if wQFM does, `0` for a tie.

The figure has three panels, each the mean RF distance over 20 replicates with
standard-error bars:
(a) ILS level 0.5X / 1X / 2X (200 genes, 500 bp),
(b) sequence length 250–1500 bp and true gene trees (200 genes, 1X ILS),
(c) number of genes 25–800 (500 bp, 1X ILS).

Re-running with the same name resumes from finished files (useful if a run is
interrupted, so finished QPU calls are not repeated); a new name starts a fresh run.

---

## Extra: running the 37-taxon benchmark manually

`run_37_taxa.sh` is a thin wrapper. The same result can be produced step by step.

**1. Check the setup without running anything** (shows the input folder, file
count, output paths and whether the token was found):

```bash
bash QWQFM/benchmark/scripts/run_37_taxa_benchmark.sh --dry-run
```

**2. Run the benchmark** — set the output CSV and a checkpoint directory:

```bash
export JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g"
OUTPUT_CSV="$PWD/QWQFM/benchmark/output_csv/results_37_taxa.csv" \
WORK_DIR="$PWD/QWQFM/benchmark/work/results_37_taxa" \
bash QWQFM/benchmark/scripts/run_37_taxa_benchmark.sh
```

(`$PWD` makes the paths absolute; this runner changes directory internally.)

Useful options:

```bash
bash QWQFM/benchmark/scripts/run_37_taxa_benchmark.sh --limit 5   # first 5 files only (cheap QPU test)
bash QWQFM/benchmark/scripts/run_37_taxa_benchmark.sh --force     # redo finished files
QUANTUM_FIRST=1 bash QWQFM/benchmark/scripts/run_37_taxa_benchmark.sh   # all QPU runs first, then wQFM
```

**3. Copy the CSV and draw the figure:**

```bash
mkdir -p "result_analysis/37 Taxa/result" "result_analysis/37 Taxa/figure"
cp QWQFM/benchmark/output_csv/results_37_taxa.csv "result_analysis/37 Taxa/result/"
QWQFM/.venv/bin/python "result_analysis/37 Taxa/graph.py" \
  --csv "result_analysis/37 Taxa/result/results_37_taxa.csv" \
  --out "result_analysis/37 Taxa/figure/results_37_taxa.pdf"
```

**Running a single quartet file directly** (one algorithm, one tree; `-algo 2` needs the token):

```bash
export DWAVE_API_TOKEN="your-token-here"
cd QWQFM/WQFM
bash run-wqfm.sh -i input_files/37-taxa-weighted-quartets/noscale.200g.500b_R1_weighted_quartets -o wqfm.tre -algo 1
bash run-wqfm.sh -i input_files/37-taxa-weighted-quartets/noscale.200g.500b_R1_weighted_quartets -o wq2a.tre -algo 2
```

`-algo 1` is wQFM, `-algo 2` is wQ²A.
