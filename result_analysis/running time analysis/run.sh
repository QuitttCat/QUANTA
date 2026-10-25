#!/usr/bin/env bash
# Curate wQFM vs wQ²A timing from the benchmark run logs, then draw the figure.
# Needs no D-Wave token: it only reads finished runs.
# Usage: bash "result_analysis/running time analysis/run.sh"
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
PYTHON="${ROOT}/QWQFM/.venv/bin/python"

"$PYTHON" "${HERE}/curate_timing.py" --root "$ROOT" --out-dir "${HERE}/result"
"$PYTHON" "${HERE}/graph.py" --summary "${HERE}/result/timing_by_taxa.csv" \
    --out "${HERE}/figure/running_time.pdf"
"$PYTHON" "${HERE}/scaling.py" --summary "${HERE}/result/timing_by_taxa.csv" \
    --out "${HERE}/figure/scaling.pdf"
