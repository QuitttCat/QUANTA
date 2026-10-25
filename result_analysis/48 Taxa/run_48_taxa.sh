#!/usr/bin/env bash
# Rerun wQ²A on the 48-taxon dataset on D-Wave Advantage2 (Zephyr Z12), reusing
# the wQFM trees and timings from the classical source CSV, then plot.
# Partitions with n>20 taxa go to the QPU, smaller ones to brute force, so a
# D-Wave API token is required: export DWAVE_API_TOKEN or put DWAVE_API_TOKEN=...
# in .env at the repository root.
# Usage: bash "result_analysis/48 Taxa/run_48_taxa.sh" [output_csv_name]
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"

name="${1:-results_48_taxa.csv}"
[[ "$name" == *.csv ]] || name="${name}.csv"
stem="${name%.csv}"

benchmark_csv="${ROOT}/QWQFM/benchmark/output_csv/${name}"
work_dir="${ROOT}/QWQFM/benchmark/work/${stem}"
result_csv="${HERE}/result/${name}"
figure="${HERE}/figure/${stem//>/_gt_}.pdf"
python_bin="${ROOT}/QWQFM/.venv/bin/python"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx6g -Xms6g}"

mkdir -p "${HERE}/result" "${HERE}/figure"

OUTPUT_CSV="$benchmark_csv" WORK_DIR="$work_dir" \
    bash "${ROOT}/QWQFM/benchmark/scripts/run_48_taxa_z12_benchmark.sh"

cp "$benchmark_csv" "$result_csv"
echo "Copied results: $result_csv"

"$python_bin" "${HERE}/graph.py" --csv "$result_csv" --out "$figure"
