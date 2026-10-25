#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper to run wQFM (local build) with correct classpath
# Usage: ./run-wqfm.sh -i <input_wqrts_or_gene_trees> -o <output_tree> [flags]
#   --simulated_annealing  with -algo 2: solve the QUBO bipartitions by simulated
#                          annealing instead of the D-Wave QPU (no token needed)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

args=()
for arg in "$@"; do
  if [[ "$arg" == "--simulated_annealing" ]]; then
    export WQFM_QUBO_SCRIPT="${ROOT_DIR}/src/wqfm/algo/quantum/qaoa_simulated_annealing.py"
  else
    args+=("$arg")
  fi
done
set -- "${args[@]}"
JAR="${ROOT_DIR}/dist/wQFM.jar"
PICOCLI="${ROOT_DIR}/lib/picocli-4.6.1.jar"
PHYLONET="${ROOT_DIR}/lib/main.jar"

if [[ ! -f "$JAR" ]]; then
  echo "Error: ${JAR} not found. Build first: (cd WQFM && ant jar)" >&2
  exit 1
fi

exec java -cp "${JAR}:${PICOCLI}:${PHYLONET}" wqfm.main.Main "$@"
