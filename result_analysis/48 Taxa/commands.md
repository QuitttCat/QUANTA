# 48-taxon benchmark: wQFM vs wQ²A (D-Wave Advantage2, Zephyr Z12)

All commands are run from the **repository root** (the directory that contains
`QWQFM/` and `result_analysis/`). Every path below is relative to it.

## Requirements

- Java (JDK 17+) and Apache Ant — used to build and run wQFM
- Python virtual environment at `QWQFM/.venv` with `dwave-ocean-sdk`, `dendropy` and `matplotlib`
- Input quartet files in `QWQFM/WQFM/input_files/48-taxa-weighted-quartets/`
  (114 files, 7 conditions with 13–20 replicates each; the dataset itself has
  uneven replicate counts)
- **A D-Wave Leap API token with access to `Advantage2_system1`.** 48 taxa
  produce partitions with more than 20 taxa; wQ²A sends those to the QPU and
  solves smaller partitions (n ≤ 20) by brute force.

Provide the token in either of two ways:

```bash
export DWAVE_API_TOKEN="your-token-here"
```

or put this line in `.env` at the repository root:

```
DWAVE_API_TOKEN=your-token-here
```

Without a token the benchmark stops with `Error: DWAVE_API_TOKEN is not set`
before running anything.

## How these results were produced

The results come from two runs:

1. **Classical run** — `QWQFM/benchmark/scripts/run_48_taxa_benchmark.sh` ran
   wQFM (and wQ²A on the default solver) on all 114 files, giving
   `QWQFM/benchmark/output_csv/results_48_taxa_qpu_plus_bruteforce_n>20.csv`.
2. **Z12 run** — `QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh` reused
   the wQFM trees and timings from that CSV and reran only wQ²A on
   `Advantage2_system1` (Zephyr Z12 topology), giving the CSV used here.

## Results already included

`result_analysis/48 Taxa/result/results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv`
is the CSV from our Z12 run (QPU threshold n > 20). The figure
`result_analysis/48 Taxa/figure/results_48_taxa_z12_qpu_plus_bruteforce_n_gt_20.pdf`
is drawn from it. To redraw it without the QPU:

```bash
QWQFM/.venv/bin/python "result_analysis/48 Taxa/graph.py" \
  --csv "result_analysis/48 Taxa/result/results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv" \
  --out "result_analysis/48 Taxa/figure/results_48_taxa_z12_qpu_plus_bruteforce_n_gt_20.pdf"
```

## Reproduce the Z12 run (one command, needs the token)

Default output name (`results_48_taxa.csv`):

```bash
bash "result_analysis/48 Taxa/run_48_taxa.sh"
```

Custom output name:

```bash
bash "result_analysis/48 Taxa/run_48_taxa.sh" my_run.csv
```

The script:

1. reuses the wQFM trees and timings from the classical source CSV
   (`QWQFM/benchmark/output_csv/results_48_taxa_qpu_plus_bruteforce_n>20.csv`),
2. runs wQ²A on all 114 files on `Advantage2_system1` with the full JVM heap
   (`-Xmx6g -Xms6g`; override by exporting `JAVA_TOOL_OPTIONS` first),
3. scores both trees by normalized Robinson–Foulds distance against the
   48-taxon true species tree,
4. copies the CSV into `result_analysis/48 Taxa/result/`,
5. draws the figure into `result_analysis/48 Taxa/figure/`.

Because QPU sampling is stochastic, wQ²A trees can differ slightly between runs;
wQFM results are reused, so they do not change. A full run makes QPU calls for
every file and uses Leap QPU time.

Lower the heap if your machine has less than ~8 GB RAM:

```bash
JAVA_TOOL_OPTIONS="-Xmx3g" bash "result_analysis/48 Taxa/run_48_taxa.sh"
```

## Reproduce from scratch (classical run first)

To regenerate the wQFM results too, first run the classical benchmark, then
point the Z12 run at its CSV:

```bash
export JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g"
OUTPUT_CSV="$PWD/QWQFM/benchmark/output_csv/results_48_taxa_classical.csv" \
WORK_DIR="$PWD/QWQFM/benchmark/work/results_48_taxa_classical" \
bash QWQFM/benchmark/scripts/run_48_taxa_benchmark.sh

SOURCE_CSV="$PWD/QWQFM/benchmark/output_csv/results_48_taxa_classical.csv" \
bash "result_analysis/48 Taxa/run_48_taxa.sh"
```

(`$PWD` makes the paths absolute; these runners change directory internally.)

## Outputs

| What | Where |
|---|---|
| Results CSV | `result_analysis/48 Taxa/result/<name>.csv` |
| Figure | `result_analysis/48 Taxa/figure/<name>.pdf` |
| Per-file wQ²A trees and logs | `QWQFM/benchmark/work/<name>/<quartet_file>/` |

CSV columns: `quartet_file_name, wqfm_tree, quantum_annealing_tree,
quantum_solver, quantum_topology, rf_wqfm_wrt_base, rf_quantum_wrt_base, better,
wqfm_bipartition_time_seconds, quantum_qpu_access_time_seconds,
quantum_bruteforce_time_seconds, quantum_time_seconds`.
The `quantum_*` columns hold the wQ²A results. `better` is `1` if wQ²A has the
lower RF distance, `-1` if wQFM does, `0` for a tie.

The figure has two panels, each the mean RF distance over replicates with
standard-error bars; the replicate count is shown under each condition:
(a) ILS level 0.5X / 1X / 2X (1000 genes, 500 bp),
(b) number of genes 50–1000 (1X ILS, 500 bp).
The 1X / 1000-gene condition appears in both panels.

Re-running with the same name resumes from finished files; a new name starts a
fresh run.

---

## Extra: running the 48-taxon benchmark manually

**1. Check the setup without running anything** (shows the input folder, file
count, source CSV, solver and whether the token was found):

```bash
bash QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh --dry-run
```

**2. Run the Z12 benchmark** — set the output CSV and a checkpoint directory:

```bash
export JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g"
OUTPUT_CSV="$PWD/QWQFM/benchmark/output_csv/results_48_taxa.csv" \
WORK_DIR="$PWD/QWQFM/benchmark/work/results_48_taxa" \
bash QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh
```

Useful options:

```bash
bash QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh --limit 5   # first 5 files only (cheap QPU test)
bash QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh --force     # redo finished files
DWAVE_SOLVER=Advantage_system4 DWAVE_TOPOLOGY=pegasus \
  bash QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh           # a different QPU
```

`DWAVE_SOLVER` selects the QPU (the run stops if the log does not confirm that
solver); `DWAVE_TOPOLOGY` is only a label recorded in the CSV's
`quantum_topology` column.

**3. Copy the CSV and draw the figure:**

```bash
mkdir -p "result_analysis/48 Taxa/result" "result_analysis/48 Taxa/figure"
cp QWQFM/benchmark/output_csv/results_48_taxa.csv "result_analysis/48 Taxa/result/"
QWQFM/.venv/bin/python "result_analysis/48 Taxa/graph.py" \
  --csv "result_analysis/48 Taxa/result/results_48_taxa.csv" \
  --out "result_analysis/48 Taxa/figure/results_48_taxa.pdf"
```

**Running a single quartet file directly** (one algorithm, one tree; `-algo 2` needs the token):

```bash
export DWAVE_API_TOKEN="your-token-here"
cd QWQFM/WQFM
bash run-wqfm.sh -i input_files/48-taxa-weighted-quartets/1X-1000-500_R1_weighted_quartets -o wqfm.tre -algo 1
bash run-wqfm.sh -i input_files/48-taxa-weighted-quartets/1X-1000-500_R1_weighted_quartets -o wq2a.tre -algo 2
```

`-algo 1` is wQFM, `-algo 2` is wQ²A.
