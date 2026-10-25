#!/usr/bin/env bash
# Run the 11-taxon wQFM vs wQ²A benchmark, collect the CSV, and plot it.
# Usage: bash "result_analysis/11 Taxa/run_11_taxa.sh" [output_csv_name]
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"

name="${1:-results_11_taxa.csv}"
[[ "$name" == *.csv ]] || name="${name}.csv"
stem="${name%.csv}"

benchmark_csv="${ROOT}/QWQFM/benchmark/output_csv/${name}"
work_dir="${ROOT}/QWQFM/benchmark/work/${stem}"
result_csv="${HERE}/result/${name}"
figure="${HERE}/figure/${stem}.pdf"
python_bin="${ROOT}/QWQFM/.venv/bin/python"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx6g -Xms6g}"

mkdir -p "${HERE}/result" "${HERE}/figure"

OUTPUT_CSV="$benchmark_csv" WORK_DIR="$work_dir" \
    bash "${ROOT}/QWQFM/benchmark/scripts/run_11_taxa_benchmark.sh"

cp "$benchmark_csv" "$result_csv"
echo "Copied results: $result_csv"

"$python_bin" "${HERE}/graph.py" --csv "$result_csv" --out "$figure"
