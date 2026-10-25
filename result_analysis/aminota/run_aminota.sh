#!/usr/bin/env bash
# Run wQFM and wQ²A on the amniota DNA (nt) and AA quartet files, score both
# trees by weighted quartet score, collect the CSV, and draw every tree.
# Usage: bash result_analysis/aminota/run_aminota.sh [output_csv_name]
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
APP_DIR="${ROOT}/QWQFM/WQFM"
INPUT_DIR="${APP_DIR}/input_files/biological_dataset_weigted_quartets"
SCORER="${ROOT}/QWQFM/benchmark/scripts/score_biological_row.py"
PYTHON="${ROOT}/QWQFM/.venv/bin/python"

name="${1:-results_aminota.csv}"
[[ "$name" == *.csv ]] || name="${name}.csv"
stem="${name%.csv}"

benchmark_csv="${ROOT}/QWQFM/benchmark/output_csv/${name}"
work_dir="${ROOT}/QWQFM/benchmark/work/${stem}"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx6g -Xms6g}"

mkdir -p "${HERE}/result" "${HERE}/figure" "$(dirname "$benchmark_csv")"
rm -f "$benchmark_csv"

echo "Building wQFM..."
(cd "$APP_DIR" && ant -q jar)

# 16 taxa never cross the n>20 QPU threshold, so algorithm 2 (wQ²A) is brute
# force here and needs no D-Wave token.
for dataset in aminota-nt aminota-aa; do
    quartets="${INPUT_DIR}/${dataset}.weighted_quartets"
    result_dir="${work_dir}/${dataset}.weighted_quartets"
    mkdir -p "$result_dir"
    for algo in 1 2; do
        label=$([[ $algo == 1 ]] && echo wqfm || echo wq2a)
        echo "[$dataset] algorithm $algo ($label)"
        (
            cd "$APP_DIR"
            WQFM_PYTHON="$PYTHON" MPLCONFIGDIR="${work_dir}/.matplotlib" \
                bash ./run-wqfm.sh -i "$quartets" -o "${result_dir}/${label}.tre" -algo "$algo"
        ) >"${result_dir}/${label}.log" 2>&1
    done

    "$PYTHON" "$SCORER" \
        --quartet-file "$quartets" \
        --wqfm-tree "${result_dir}/wqfm.tre" \
        --quantum-tree "${result_dir}/wq2a.tre" \
        --wqfm-log "${result_dir}/wqfm.log" \
        --quantum-log "${result_dir}/wq2a.log" \
        --output-csv "$benchmark_csv" \
        --progress-every 0

    for label in wqfm wq2a; do
        "$PYTHON" "${HERE}/draw_tree.py" \
            --tree "${result_dir}/${label}.tre" \
            --outgroup protopterus \
            --title "${dataset} (${label})" \
            --out "${HERE}/figure/${stem}_${dataset}_${label}.pdf"
    done
done

cp "$benchmark_csv" "${HERE}/result/${name}"
echo "Copied results: ${HERE}/result/${name}"
