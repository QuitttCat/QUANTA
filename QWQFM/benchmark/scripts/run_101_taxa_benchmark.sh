#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"

export INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/WQFM/input_files/101-taxa-weighted-quartets}"
export MODEL_TREE_DIR="${MODEL_TREE_DIR:-${REPO_DIR}/WQFM/input_files/101-taxa-true-species-tree}"
export MODEL_TREE_SUFFIX="${MODEL_TREE_SUFFIX:-.SPECIES_TREE}"
export OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_101_taxa_qpu_plus_bruteforce.csv}"
export WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/101_taxa_qpu_plus_bruteforce}"
export QUANTUM_FIRST=1

exec "${SCRIPT_DIR}/run_37_taxa_benchmark.sh" "$@"
