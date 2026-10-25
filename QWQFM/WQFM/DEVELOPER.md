# Developer Guide (wQFM Java)

This document summarizes module responsibilities and how to build, run, and debug the project locally.

## Build
- Requires: Java (JDK 8+), Ant.
- Build jar:
  - `cd WQFM && ant jar`
  - Output: `WQFM/dist/wQFM.jar`
- Runtime libs used by the app:
  - `WQFM/lib/picocli-4.6.1.jar` (CLI parsing)
  - `WQFM/lib/main.jar` (PhyloNet for rerooting)

## Run
You can use the helper scripts (recommended) or raw Java commands.

- Default mode (v1.4 CLI with flags):
  - `./run-wqfm.sh -i <input-wqrts-or-gene-trees> -o <output.tre> [flags]`
  - Examples:
    - Weighted quartets: `./run-wqfm.sh -i input_files/wqrts_toy_dataset_QFM_paper -o out.tre`
    - From gene trees: `./run-wqfm.sh -i input_files/gtree_11tax_est_5genes_R1.tre -o out.tre -im gene-trees`
    - Branch support: `./run-wqfm.sh -i ... -o ... -t 1`
    - Quartet scores: `./run-wqfm.sh -i ... -o ... -q 2 -qo qscore.txt`

- Verbose partition prints (legacy positional CLI):
  - `./run-wqfm-verbose.sh <input_wqrts> <output.tre> <alpha> <beta>`
  - Example: `./run-wqfm-verbose.sh input_files/wqrts_11Tax_est_5G_R1 out_11_verbose.tre 1 1`
  - Notes: Uses `jar files/wQFM-printing-more-info.jar`. Alpha/Beta control score S = alpha*[ws] - beta*[wv]. Use 1/1 to emulate default s-v; 1/0 to maximize satisfied weight only.

## Project Layout (selected)
- `src/wqfm/main/Main.java`: CLI entry; parses flags, sets config, runs wQFM, annotations, and quartet scores.
- `src/wqfm/algo/FMRunner.java`: Core orchestration of recursive FM bipartitioning and final tree assembly.
- `src/wqfm/bip/Bipartition_8_values.java`: Computes counts/weights w.r.t. a cut: satisfied/violated/deferred/blank and their weights.
- `src/wqfm/bip/WeightedPartitionScores.java`: Partition score computation and beta handling.
- `src/wqfm/ds/*`: Data structures for quartets, per-level state, and FM result object (left/right partitions, dummy-tax handling).
- `src/wqfm/feature/Bin.java`: Dynamic bin heuristic to auto-select beta from quartet weight distribution.
- `src/wqfm/utils/*`: Utilities for IO, rerooting (PhyloNet + DendroPy), annotations (`-t`), quartet scores (`-q`), and CLI helpers.
- `input_files/`: Example weighted quartets, gene trees, and reference trees.
- `jar files/`: Alternative/verbose jars for diagnostics and experiments.

## Python helpers
- `triplets.soda2103`: Linux tool to enumerate quartets from a tree.
- `quartet-controller.sh`, `quartet_count.sh`, `summarize-quartet-counts.py`, `generate_wqrts.py`: Generate weighted quartets from gene trees.
- `annotate_branches.py`, `compute_quartet_score.py`, `normalize_weights.py`: Branch support and quartet score utilities (require `pandas`, `dendroPy`).

## Tips
- Memory: use `-Xmx` for larger datasets (e.g., `-Xmx8G`).
- If Python is `python` not `python3`, pass `-pe python` (v1.4 CLI).
- Keep `WQFM/lib` next to the jar; reroot checks will fail otherwise.
