#!/usr/bin/env bash
# 48-taxon benchmark: wQFM vs wQ²A with simulated annealing in place of the QPU
# (n > 20 -> simulated annealing, n <= 20 -> brute force, QUBO A=1, B=0.4).
# Needs no D-Wave token. Runs one file at a time; finished files are skipped on
# rerun. wQFM runs already done locally (WQFM_REUSE_DIR) are copied, not rerun.
# Usage: bash "result_analysis/simulated annealing/48 Taxa/run_48_taxa_sa.sh" [output_csv_name]
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"
APP_DIR="${ROOT}/QWQFM/WQFM"
PYTHON="${ROOT}/QWQFM/.venv/bin/python"

name="${1:-results_48_taxa_sa.csv}"
[[ "$name" == *.csv ]] || name="${name}.csv"
stem="${name%.csv}"

INPUT_DIR="${INPUT_DIR:-${APP_DIR}/input_files/48-taxa-weighted-quartets_full_data}"
WORK_DIR="${WORK_DIR:-${ROOT}/QWQFM/benchmark/work/${stem}}"
WQFM_REUSE_DIR="${WQFM_REUSE_DIR:-${ROOT}/QWQFM/benchmark/work/48_taxa_wqfm_only_local}"
MODEL_TREE_FILE="${MODEL_TREE_FILE:-${ROOT}/dataset/48-taxon/true_tree_trimmed}"
OUTPUT_CSV="${ROOT}/QWQFM/benchmark/output_csv/${name}"
RF_SCRIPT="${ROOT}/QWQFM/benchmark/robinson_foulds.py"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx6g -Xms6g}"
export WQ2A_SA_THRESHOLD="${WQ2A_SA_THRESHOLD:-20}" WQ2A_A="${WQ2A_A:-1.0}" WQ2A_B="${WQ2A_B:-0.4}"

mapfile -d '' files < <(find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z)
((${#files[@]})) || { echo "Error: no input files in $INPUT_DIR" >&2; exit 1; }
[[ -f "$MODEL_TREE_FILE" ]] || { echo "Error: true tree not found: $MODEL_TREE_FILE" >&2; exit 1; }
mkdir -p "$WORK_DIR" "${HERE}/result"

echo "Input: $INPUT_DIR (${#files[@]} files)"
echo "Work dir: $WORK_DIR"
echo "wQFM reuse dir: $WQFM_REUSE_DIR"
echo "QUBO: A=$WQ2A_A B=$WQ2A_B; simulated annealing for n > $WQ2A_SA_THRESHOLD; JVM: $JAVA_TOOL_OPTIONS"

echo "Building wQFM..."
(cd "$APP_DIR" && ant -q jar)

run() { # algo label out_dir input [extra flags]
    local algo="$1" label="$2" out="$3" input="$4"; shift 4
    (cd "$APP_DIR" && WQFM_PYTHON="$PYTHON" MPLCONFIGDIR="${WORK_DIR}/.matplotlib" \
        bash ./run-wqfm.sh -i "$input" -o "${out}/${label}.tre" -algo "$algo" "$@") >"${out}/${label}.log" 2>&1
    touch "${out}/${label}.done"
}

for ((i = 0; i < ${#files[@]}; i++)); do
    input="${files[$i]}"; file="$(basename "$input")"; out="${WORK_DIR}/${file}"
    mkdir -p "$out"
    echo "[$((i + 1))/${#files[@]}] $file"

    if [[ ! -f "${out}/wqfm.done" ]]; then
        if [[ -f "${WQFM_REUSE_DIR}/${file}/wqfm.done" ]]; then
            cp "${WQFM_REUSE_DIR}/${file}/wqfm.tre" "${WQFM_REUSE_DIR}/${file}/wqfm.log" "$out/"
            touch "${out}/wqfm.done"
            echo "  wQFM: copied from $WQFM_REUSE_DIR"
        else
            echo "  wQFM: running"
            run 1 wqfm "$out" "$input"
        fi
    fi
    if [[ ! -f "${out}/sa.done" ]]; then
        echo "  wQ2A (simulated annealing): running"
        run 2 sa "$out" "$input" --simulated_annealing
    fi

    "$PYTHON" "${HERE}/score_sa_row.py" --quartet-file "$input" --model-tree-file "$MODEL_TREE_FILE" \
        --wqfm-tree "${out}/wqfm.tre" --sa-tree "${out}/sa.tre" \
        --wqfm-log "${out}/wqfm.log" --sa-log "${out}/sa.log" \
        --rf-script "$RF_SCRIPT" --output-csv "$OUTPUT_CSV"
done

cp "$OUTPUT_CSV" "${HERE}/result/${name}"
echo "Done. CSV: $OUTPUT_CSV (copied to ${HERE}/result/${name})"

"$PYTHON" "${HERE}/graph.py" --csv "${HERE}/result/${name}" --out "${HERE}/figure/${stem}.pdf"
