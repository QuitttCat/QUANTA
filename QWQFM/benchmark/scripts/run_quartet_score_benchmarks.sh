#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"

QUARTET_SCORE_PYTHON="${QUARTET_SCORE_PYTHON:-${WORKSPACE_DIR}/benchmark/.venv/bin/python}"

if [[ ! -x "$QUARTET_SCORE_PYTHON" ]]; then
    echo "Error: Python executable not found: $QUARTET_SCORE_PYTHON" >&2
    exit 1
fi

exec "$QUARTET_SCORE_PYTHON" \
    "${SCRIPT_DIR}/build_quartet_score_csvs.py" \
    "$@"
