#!/usr/bin/env bash
# Collect the results CSV and per-replicate timing from a finished 101-taxon
# benchmark run, then draw the figure. Needs no D-Wave token.
# Usage: bash "result_analysis/101 Taxa/collect_and_plot.sh"
# Point at another run with RESULTS_CSV=... WORK_DIR=... (paths from repo root).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
cd "$ROOT"

RESULTS_CSV="${RESULTS_CSV:-QWQFM/benchmark/output_csv/results_101_taxa_qpu_plus_bruteforce.csv}"
WORK_DIR="${WORK_DIR:-QWQFM/benchmark/work/101_taxa_qpu_plus_bruteforce}"
PYTHON="QWQFM/.venv/bin/python"

stem="$(basename "$RESULTS_CSV" .csv)"
result_csv="${HERE}/result/${stem}.csv"
timing_csv="${HERE}/result/timing_${stem}.csv"
figure="${HERE}/figure/${stem}.pdf"

mkdir -p "${HERE}/result" "${HERE}/figure"

cp "$RESULTS_CSV" "$result_csv"
echo "Copied results: $result_csv"

"$PYTHON" "${HERE}/collect_timing.py" --work-dir "$WORK_DIR" --out "$timing_csv"

"$PYTHON" "${HERE}/graph.py" --results-csv "$result_csv" --timing-csv "$timing_csv" --out "$figure"
