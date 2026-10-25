#!/usr/bin/env bash
# 15 taxa never cross the n>20 QPU threshold, so this reuses the brute-force
# 11-taxa runner with one true tree for every file (all labels are A..O).
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"

export INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/WQFM/input_files/15-taxa-weighted-quartets}"
export OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_15_taxa.csv}"
export WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/results_15_taxa}"
export MODEL_TREE_FILE="${MODEL_TREE_FILE:-${WORKSPACE_DIR}/dataset/15-taxon/true_tree_trimmed}"

exec "${SCRIPT_DIR}/run_11_taxa_benchmark.sh" "$@"
