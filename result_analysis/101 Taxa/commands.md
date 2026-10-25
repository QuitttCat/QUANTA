# 101-taxon benchmark: wQFM vs wQ²A (D-Wave QPU) — accuracy and timing

All commands are run from the **repository root** (the directory that contains
`QWQFM/` and `result_analysis/`). Every path below is relative to it.

## What is in this folder

| File | Purpose |
|---|---|
| `collect_and_plot.sh` | One command: copies the results CSV, collects timing from the run logs, draws the figure |
| `collect_timing.py` | Reads every replicate's `wqfm.log` / `quantum.log` and writes the timing CSV |
| `graph.py` | Draws the figure from the results CSV and the timing CSV |
| `result/results_101_taxa_qpu_plus_bruteforce.csv` | RF distances and trees, one row per replicate |
| `result/timing_results_101_taxa_qpu_plus_bruteforce.csv` | Timing, one row per replicate |
| `figure/results_101_taxa_qpu_plus_bruteforce.pdf` | The figure |

## The data

101 taxa, true gene trees, 19 replicates (`01`–`04`, `06`–`10`, `41`–`50`).
Inputs are `QWQFM/WQFM/input_files/101-taxa-weighted-quartets/<NN>.true.wqrts`
(about 12 million weighted quartets each); true species trees are
`QWQFM/WQFM/input_files/101-taxa-true-species-tree/<NN>.SPECIES_TREE`.

## Collect and draw (one command, no D-Wave token needed)

Uses the finished run in `QWQFM/benchmark/work/101_taxa_qpu_plus_bruteforce/`:

```bash
bash "result_analysis/101 Taxa/collect_and_plot.sh"
```

To collect from a different run, point it at that run's CSV and work directory:

```bash
RESULTS_CSV="QWQFM/benchmark/output_csv/my_run.csv" \
WORK_DIR="QWQFM/benchmark/work/my_run" \
bash "result_analysis/101 Taxa/collect_and_plot.sh"
```

## The figure

Every bar is the mean over replicates with standard-error bars.

- **(a) Accuracy** — normalized Robinson–Foulds distance to the true species tree.
- **(b) End-to-end running time** — the whole run, from each log's
  `Time taken = N ms` line.
- **(c) Sum of division-step times** (log scale) — the total time of all
  bipartition steps in a run, from the `BENCHMARK_BIPARTITION_TIME_NS` markers.
  wQ²A is shown twice:
  - *wall clock* — the full time of its division steps, including building the
    QUBO from the quartets and the round trip to D-Wave;
  - *QPU access + brute force* — only the time spent solving: D-Wave
    `qpu_access_time` for partitions with n > 20 plus brute-force time for
    partitions with n ≤ 20.

## Timing CSV columns (all times in seconds)

| Column | Meaning |
|---|---|
| `wqfm_end_to_end_seconds`, `wq2a_end_to_end_seconds` | whole run |
| `wqfm_division_seconds`, `wq2a_division_seconds` | sum of division steps, wall clock |
| `wq2a_qpu_access_seconds` | sum of D-Wave `qpu_access_time` |
| `wq2a_bruteforce_seconds` | sum of brute-force solves (n ≤ 20) |
| `wq2a_qpu_calls` | number of QPU calls in the run |

## Rerun the benchmark (needs a D-Wave token)

101 taxa produce partitions with more than 20 taxa, which wQ²A sends to the
D-Wave QPU. Provide a Leap API token:

```bash
export DWAVE_API_TOKEN="your-token-here"
```

or put `DWAVE_API_TOKEN=your-token-here` in `.env` at the repository root.

Then run the benchmark and collect it:

```bash
export JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g"
bash QWQFM/benchmark/scripts/run_101_taxa_benchmark.sh
bash "result_analysis/101 Taxa/collect_and_plot.sh"
```

The benchmark's default output paths are the ones `collect_and_plot.sh` reads.
It runs all wQ²A (QPU) jobs first, then wQFM. Expect about 4 minutes per
replicate for wQ²A and about 20 minutes for wQFM, and Leap QPU time for
every replicate. Re-running resumes from finished replicates.

Useful options:

```bash
bash QWQFM/benchmark/scripts/run_101_taxa_benchmark.sh --dry-run   # paths, file count, token check
bash QWQFM/benchmark/scripts/run_101_taxa_benchmark.sh --limit 1   # one replicate only
```

QPU sampling is stochastic, so wQ²A trees and times can differ slightly between runs.

---

## Extra: running the steps manually

**1. Collect timing from a work directory:**

```bash
QWQFM/.venv/bin/python "result_analysis/101 Taxa/collect_timing.py" \
  --work-dir QWQFM/benchmark/work/101_taxa_qpu_plus_bruteforce \
  --out "result_analysis/101 Taxa/result/timing_results_101_taxa_qpu_plus_bruteforce.csv"
```

**2. Copy the results CSV:**

```bash
cp QWQFM/benchmark/output_csv/results_101_taxa_qpu_plus_bruteforce.csv "result_analysis/101 Taxa/result/"
```

**3. Draw the figure:**

```bash
QWQFM/.venv/bin/python "result_analysis/101 Taxa/graph.py" \
  --results-csv "result_analysis/101 Taxa/result/results_101_taxa_qpu_plus_bruteforce.csv" \
  --timing-csv "result_analysis/101 Taxa/result/timing_results_101_taxa_qpu_plus_bruteforce.csv" \
  --out "result_analysis/101 Taxa/figure/results_101_taxa_qpu_plus_bruteforce.pdf"
```

**Running a single replicate directly** (`-algo 2` needs the token):

```bash
export DWAVE_API_TOKEN="your-token-here"
cd QWQFM/WQFM
bash run-wqfm.sh -i input_files/101-taxa-weighted-quartets/01.true.wqrts -o wqfm.tre -algo 1 > wqfm.log 2>&1
bash run-wqfm.sh -i input_files/101-taxa-weighted-quartets/01.true.wqrts -o wq2a.tre -algo 2 > quantum.log 2>&1
```

`-algo 1` is wQFM, `-algo 2` is wQ²A. Each log ends with a `Time taken` line
and contains one `BENCHMARK_BIPARTITION_TIME_NS` marker per division step.
