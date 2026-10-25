#!/usr/bin/env bash
# Run QUANTA on the biological, 101-, 144- and 200-taxon datasets with a
# classical QUBO solver (simulated annealing or tabu search) in place of the
# D-Wave QPU / Leap Hybrid for partitions with n>20 taxa; smaller ones go to
# brute force, as in the QPU runs. No D-Wave token is used. Each tree is scored
# by weighted quartet score and, where a reference exists, by RF distance
# (101: true species tree of each replicate; 144 and 200: the input gene tree).
# See QWQFM/benchmark/scripts/run_classical_benchmark.sh.
# (The 37- and 48-taxon runs are in "result_analysis/37 Taxa" and "48 Taxa".)
#
# Memory: biological runs fit a laptop (about 0.65 GB each). 101, 144 and 200
# need the server, with the Java heap of their QPU runs (16, 16 and 26 GB).
#
# Usage: [JOBS=N] bash "result_analysis/classical solvers/run_classical.sh" biological|101|144|200 sa|tabu
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
INPUTS="${ROOT}/QWQFM/WQFM/input_files"

group="${1:-}"
case "${2:-}" in
    sa) name="simulated_annealing" ;;
    tabu) name="tabu_search" ;;
    *) echo "Usage: $0 biological|101|144|200 sa|tabu" >&2; exit 2 ;;
esac

case "$group" in
    biological)
        export INPUT_DIR="${INPUTS}/biological_dataset_weigted_quartets" ;;
    101)
        export INPUT_DIR="${INPUTS}/101-taxa-weighted-quartets"
        export REFERENCE_DIR="${INPUTS}/101-taxa-true-species-tree" REFERENCE_SUFFIX=".SPECIES_TREE"
        export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xms4g -Xmx16g -XX:+UseG1GC}" ;;
    144)
        export INPUT_DIR="${INPUTS}/144-taxa-insect-single-gene-weighted-quartets"
        export REFERENCE_FILE="${INPUTS}/144-taxa-insect-single-gene/insect_gene_tree_0713.tre"
        export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xms4g -Xmx16g -XX:+UseG1GC}" ;;
    200)
        export INPUT_DIR="${INPUTS}/200-taxa-s200-rep01-true-gene-tree-weighted-quartets"
        export REFERENCE_FILE="${INPUTS}/200-taxa-s200-rep01-true-gene-tree/s200_rep01_true_gene_tree_001_200_taxa.tre"
        export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xms4g -Xmx26g -XX:+UseG1GC}" ;;
    *) echo "Usage: $0 biological|101|144|200 sa|tabu" >&2; exit 2 ;;
esac

WORK_DIR="${ROOT}/QWQFM/benchmark/work/${group}_${name}_n_gt_20" \
RESULT_CSV="${HERE}/result/results_${group}_${name}_plus_bruteforce_n>20.csv" \
    bash "${ROOT}/QWQFM/benchmark/scripts/run_classical_benchmark.sh" "$2"
