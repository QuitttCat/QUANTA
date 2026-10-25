# Amniota dataset: wQFM vs wQ²A (bruteforce)

All commands are run from the **repository root** (the directory that contains
`QWQFM/` and `result_analysis/`). Every path below is relative to it.

## Requirements

- Java (JDK 17+) and Apache Ant — used to build and run wQFM
- Python virtual environment at `QWQFM/.venv` with `dendropy`, `biopython` and `matplotlib`
- Input quartet files in `QWQFM/WQFM/input_files/biological_dataset_weigted_quartets/`:
  - `aminota-nt.weighted_quartets` — DNA gene trees
  - `aminota-aa.weighted_quartets` — amino-acid (AA) gene trees

No D-Wave token is needed: the amniota dataset has 16 taxa, so wQ²A never
crosses the n>20 QPU threshold and solves every partition by brute force.

This is a biological dataset, so there is no true species tree and no
Robinson–Foulds score. Instead, each tree is scored by its **weighted quartet
score**: the total weight of input quartets the tree agrees with (higher is better).

## Reproduce the results (one command)

Default output name (`results_aminota.csv`):

```bash
bash result_analysis/aminota/run_aminota.sh
```

Custom output name:

```bash
bash result_analysis/aminota/run_aminota.sh my_run.csv
```

The script:

1. builds wQFM,
2. runs wQFM (algorithm 1) and wQ²A (algorithm 2) on both amniota files with the
   full JVM heap (`-Xmx6g -Xms6g`; override by exporting `JAVA_TOOL_OPTIONS` first),
3. scores both trees by weighted quartet score,
4. copies the CSV into `result_analysis/aminota/result/`,
5. draws each of the four trees into `result_analysis/aminota/figure/`.

Lower the heap if your machine has less than ~8 GB RAM:

```bash
JAVA_TOOL_OPTIONS="-Xmx3g" bash result_analysis/aminota/run_aminota.sh
```

## Outputs

| What | Where |
|---|---|
| Results CSV | `result_analysis/aminota/result/<name>.csv` |
| Tree figures | `result_analysis/aminota/figure/<name>_aminota-{nt,aa}_{wqfm,wq2a}.pdf` |
| Trees and logs | `QWQFM/benchmark/work/<name>/aminota-{nt,aa}.weighted_quartets/{wqfm,wq2a}.{tre,log}` |

CSV columns: `quartet_file_name, taxa_count, wqfm_tree, quantum_annealing_tree,
wqfm_weighted_quartet_score, quantum_weighted_quartet_score,
better_by_weighted_quartet_score, wqfm_bipartition_time_seconds,
quantum_qpu_access_time_seconds, quantum_bruteforce_time_seconds, quantum_time_seconds`.
The `quantum_*` columns hold the wQ²A results (the column names come from the
shared biological scorer). `better_by_weighted_quartet_score` is `1` if wQ²A
scores higher, `-1` if wQFM does, `0` for a tie.

Every run starts fresh: the CSV is rewritten and both algorithms rerun on both files.

## Redraw one tree only

```bash
QWQFM/.venv/bin/python result_analysis/aminota/draw_tree.py \
  --tree QWQFM/benchmark/work/results_aminota/aminota-nt.weighted_quartets/wqfm.tre \
  --outgroup protopterus \
  --title "aminota-nt (wqfm)" \
  --out result_analysis/aminota/figure/results_aminota_aminota-nt_wqfm.pdf
```

`--outgroup` roots the tree on that taxon; leave it out to draw the tree as written.

To redraw all four trees from the results CSV alone (no benchmark run needed),
pass each tree as a Newick string with `--newick`:

```bash
QWQFM/.venv/bin/python - <<'EOF'
import csv, subprocess
R = "result_analysis/aminota"
for row in csv.DictReader(open(f"{R}/result/results_aminota.csv")):
    dataset = row["quartet_file_name"].removesuffix(".weighted_quartets")
    for label, column in (("wqfm", "wqfm_tree"), ("wq2a", "quantum_annealing_tree")):
        subprocess.run(["QWQFM/.venv/bin/python", f"{R}/draw_tree.py", "--newick", row[column],
                        "--outgroup", "protopterus", "--title", f"{dataset} ({label})",
                        "--out", f"{R}/figure/results_aminota_{dataset}_{label}.pdf"], check=True)
EOF
```

---

## Extra: running the amniota benchmark manually

`run_aminota.sh` is a thin wrapper. The same result can be produced step by step.

**1. Build wQFM:**

```bash
(cd QWQFM/WQFM && ant jar)
```

**2. Run both algorithms on one file** (repeat with `aminota-aa` for the AA data):

```bash
cd QWQFM/WQFM
bash run-wqfm.sh -i input_files/biological_dataset_weigted_quartets/aminota-nt.weighted_quartets -o wqfm.tre -algo 1 > wqfm.log 2>&1
bash run-wqfm.sh -i input_files/biological_dataset_weigted_quartets/aminota-nt.weighted_quartets -o wq2a.tre -algo 2 > wq2a.log 2>&1
cd ../..
```

`-algo 1` is wQFM, `-algo 2` is wQ²A. Keep the logs: the scorer reads the
timing markers in them.

**3. Score both trees and add a row to the CSV:**

```bash
QWQFM/.venv/bin/python QWQFM/benchmark/scripts/score_biological_row.py \
  --quartet-file QWQFM/WQFM/input_files/biological_dataset_weigted_quartets/aminota-nt.weighted_quartets \
  --wqfm-tree QWQFM/WQFM/wqfm.tre \
  --quantum-tree QWQFM/WQFM/wq2a.tre \
  --wqfm-log QWQFM/WQFM/wqfm.log \
  --quantum-log QWQFM/WQFM/wq2a.log \
  --output-csv result_analysis/aminota/result/results_aminota.csv
```

Running it for the second file adds that file's row to the same CSV
(an existing row for the same file is replaced).

**4. Draw a tree:**

```bash
QWQFM/.venv/bin/python result_analysis/aminota/draw_tree.py \
  --tree QWQFM/WQFM/wqfm.tre --outgroup protopterus \
  --title "aminota-nt (wqfm)" --out result_analysis/aminota/figure/aminota-nt_wqfm.pdf
```
