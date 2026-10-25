#!/usr/bin/env bash
# Run QUANTA on the 48-taxon dataset with a classical QUBO solver (simulated
# annealing or tabu search) in place of the D-Wave QPU for partitions with
# n>20 taxa; smaller ones go to brute force, as in the QPU run. No D-Wave token
# is used. See QWQFM/benchmark/scripts/run_classical_benchmark.sh.
# Usage: [JOBS=N] bash "result_analysis/48 Taxa/run_48_taxa_classical.sh" sa|tabu
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"

case "${1:-}" in
    sa) name="simulated_annealing" ;;
    tabu) name="tabu_search" ;;
    *) echo "Usage: $0 sa|tabu" >&2; exit 2 ;;
esac

INPUT_DIR="${ROOT}/QWQFM/WQFM/input_files/48-taxa-weighted-quartets" \
WORK_DIR="${ROOT}/QWQFM/benchmark/work/48_taxa_${name}_n_gt_20" \
MODEL_TREE_SCRIPT="${ROOT}/QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh" \
QPU_CSV="${HERE}/result/results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv" \
RESULT_CSV="${HERE}/result/results_48_taxa_${name}_plus_bruteforce_n>20.csv" \
    bash "${ROOT}/QWQFM/benchmark/scripts/run_classical_benchmark.sh" "$1"
