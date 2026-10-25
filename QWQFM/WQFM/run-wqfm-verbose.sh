#!/usr/bin/env bash
set -euo pipefail

# Verbose/legacy wrapper that prints division/partition states using the debug jar
# Usage (positional, legacy):
#   ./run-wqfm-verbose.sh <input_wqrts> <output_tree> <alpha> <beta>
# Example to mimic default s-v scoring (alpha=1, beta=1):
#   ./run-wqfm-verbose.sh input_files/wqrts_11Tax_est_5G_R1 out_11_verbose.tre 1 1

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEBUG_JAR="${ROOT_DIR}/jar files/wQFM-printing-more-info.jar"
PHYLONET="${ROOT_DIR}/lib/main.jar"

if [[ ! -f "$DEBUG_JAR" ]]; then
  echo "Error: ${DEBUG_JAR} not found." >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <input_wqrts> <output_tree> [alpha beta]" >&2
  exit 2
fi

INPUT="$1"; OUTPUT="$2"; ALPHA="${3:-1}"; BETA="${4:-0}"

exec java -cp "${PHYLONET}:${DEBUG_JAR}" wqfm.main.Main "$INPUT" "$OUTPUT" "$ALPHA" "$BETA"
