# 15-taxon benchmark: wQFM vs wQ²A (bruteforce)

All commands are run from the **repository root** (the directory that contains
`QWQFM/`, `dataset/` and `result_analysis/`). Every path below is relative to it.

## Requirements

- Java (JDK 17+) and Apache Ant — used to build and run wQFM
- Python virtual environment at `QWQFM/.venv` with `dendropy` and `matplotlib`
- Input quartet files in `QWQFM/WQFM/input_files/15-taxa-weighted-quartets/` (60 files:
  6 conditions × 10 replicates)
- True tree at `dataset/15-taxon/true_tree_trimmed`

No D-Wave token is needed: the 15-taxon dataset never exceeds 15 taxa per
partition, so wQ²A never crosses the n>20 QPU threshold and solves every
partition by brute force.

## Reproduce the benchmark (one command)

Default output name (`results_15_taxa.csv`):

```bash
bash "result_analysis/15 Taxa/run_15_taxa.sh"
```

Custom output name:

```bash
bash "result_analysis/15 Taxa/run_15_taxa.sh" my_run.csv
```

The script:

1. runs wQFM and wQ²A on all 60 quartet files with the full JVM heap
   (`-Xmx6g -Xms6g`; override by exporting `JAVA_TOOL_OPTIONS` first),
2. scores both trees by normalized Robinson–Foulds distance against the true tree,
3. copies the CSV into `result_analysis/15 Taxa/result/`,
4. draws the figure into `result_analysis/15 Taxa/figure/`.

Lower the heap if your machine has less than ~8 GB RAM:

```bash
JAVA_TOOL_OPTIONS="-Xmx3g" bash "result_analysis/15 Taxa/run_15_taxa.sh"
```

## Outputs

| What | Where |
|---|---|
| Results CSV | `result_analysis/15 Taxa/result/<name>.csv` |
| Figure | `result_analysis/15 Taxa/figure/<name>.pdf` |
| Per-file trees and logs | `QWQFM/benchmark/work/<name>/<quartet_file>/{wqfm,bruteforce}.{tre,log}` |

CSV columns: `quartet_file_name, wqfm_tree, bruteforce_tree, rf_wqfm_wrt_base, rf_bruteforce_wrt_base`.

The figure has two panels — (a) 100 genes, (b) 1000 genes — each comparing
100 bp and 1000 bp estimated gene trees with true gene trees; bars are the mean
RF distance over 10 replicates with standard-error bars.

Re-running with the same name resumes from finished files; a new name starts
a fresh run.

## Redraw the figure only

```bash
QWQFM/.venv/bin/python "result_analysis/15 Taxa/graph.py" \
  --csv "result_analysis/15 Taxa/result/results_15_taxa.csv" \
  --out "result_analysis/15 Taxa/figure/results_15_taxa.pdf"
```

---

## Extra: running the 15-taxon benchmark manually

`run_15_taxa.sh` is a thin wrapper. The same result can be produced step by step.

**1. Build wQFM** (the benchmark script also does this, shown here for completeness):

```bash
(cd QWQFM/WQFM && ant jar)
```

**2. Run the benchmark** — set the output CSV and a checkpoint directory:

```bash
export JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g"
OUTPUT_CSV="QWQFM/benchmark/output_csv/results_15_taxa.csv" \
WORK_DIR="QWQFM/benchmark/work/results_15_taxa" \
bash QWQFM/benchmark/scripts/run_15_taxa_benchmark.sh
```

Useful options:

```bash
bash QWQFM/benchmark/scripts/run_15_taxa_benchmark.sh --dry-run   # show resolved paths, run nothing
bash QWQFM/benchmark/scripts/run_15_taxa_benchmark.sh --limit 5   # first 5 files only
bash QWQFM/benchmark/scripts/run_15_taxa_benchmark.sh --force     # redo finished files
```

**3. Copy the CSV and draw the figure:**

```bash
mkdir -p "result_analysis/15 Taxa/result" "result_analysis/15 Taxa/figure"
cp QWQFM/benchmark/output_csv/results_15_taxa.csv "result_analysis/15 Taxa/result/"
QWQFM/.venv/bin/python "result_analysis/15 Taxa/graph.py" \
  --csv "result_analysis/15 Taxa/result/results_15_taxa.csv" \
  --out "result_analysis/15 Taxa/figure/results_15_taxa.pdf"
```

**Running a single quartet file directly** (one algorithm, one tree):

```bash
cd QWQFM/WQFM
bash run-wqfm.sh -i input_files/15-taxa-weighted-quartets/100gene-100bp_R1_weighted_quartets -o wqfm.tre -algo 1
bash run-wqfm.sh -i input_files/15-taxa-weighted-quartets/100gene-100bp_R1_weighted_quartets -o bruteforce.tre -algo 2
```

`-algo 1` is wQFM, `-algo 2` is wQ²A.

Score a tree against the true tree (run from the repository root):

```bash
QWQFM/.venv/bin/python QWQFM/benchmark/robinson_foulds.py dataset/15-taxon/true_tree_trimmed QWQFM/WQFM/wqfm.tre
```

**Where the input files come from:** each file in
`QWQFM/WQFM/input_files/15-taxa-weighted-quartets/` is a copy of
`dataset/15-taxon/<condition>/R<i>/weighted_quartets`, renamed to
`<condition>_R<i>_weighted_quartets`. To rebuild the folder:

```bash
mkdir -p QWQFM/WQFM/input_files/15-taxa-weighted-quartets
for cond in dataset/15-taxon/*/; do
  c=$(basename "$cond")
  for rep in "$cond"R*/; do
    cp "${rep}weighted_quartets" \
       "QWQFM/WQFM/input_files/15-taxa-weighted-quartets/${c}_$(basename "$rep")_weighted_quartets"
  done
done
```
