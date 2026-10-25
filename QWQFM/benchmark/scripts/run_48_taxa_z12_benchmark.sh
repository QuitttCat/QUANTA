#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/WQFM"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"

INPUT_DIR="${INPUT_DIR:-${APP_DIR}/input_files/48-taxa-weighted-quartets}"
SOURCE_CSV="${SOURCE_CSV:-${BENCHMARK_DIR}/output_csv/results_48_taxa_qpu_plus_bruteforce_n>20.csv}"
OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_48_taxa_z12_qpu_plus_bruteforce_n>20.csv}"
WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/48_taxa_z12_qpu_plus_bruteforce_n_gt_20}"
RF_SCRIPT="${RF_SCRIPT:-${BENCHMARK_DIR}/robinson_foulds.py}"
WQFM_PYTHON="${WQFM_PYTHON:-${REPO_DIR}/.venv/bin/python}"
RF_PYTHON="${RF_PYTHON:-${REPO_DIR}/.venv/bin/python}"
SCORER="${SCRIPT_DIR}/score_reused_classical_row.py"
ENV_FILE="${ENV_FILE:-${WORKSPACE_DIR}/.env}"
DWAVE_SOLVER="${DWAVE_SOLVER:-Advantage2_system1}"
DWAVE_TOPOLOGY="${DWAVE_TOPOLOGY:-zephyr_z12}"

MODEL_TREE="${MODEL_TREE:-(STRCA,(TINMA,((((CUCCA,(TAUER,CHLUN)),((CAPCA,(CALAN,CHAPE)),(((TYTAL,(CATAU,(HALLE,HALAL))),((COLST,(LEPDI,(APAVI,(BUCRH,(PICPU,MERNU))))),(CARCR,(FALPE,((ACACH,(MANVI,(CORBR,(TAEGU,GEOFO)))),(MELUN,NESNO)))))),(OPHHO,(((GAVST,((PHACA,(NIPNI,(PELCR,EGRGA))),(FULGL,(PYGAD,APTFO)))),(PHALE,EURHE)),(BALRE,CHAVO)))))),((COLLI,(MESUN,PTEGU)),(PHORU,PODCR))),((MELGA,GALGA),ANAPL))));}"

limit="${LIMIT:-0}"
force="${FORCE:-0}"
dry_run=0

usage() {
    cat <<'EOF'
Usage: benchmark/scripts/run_48_taxa_z12_benchmark.sh [options]

Reuses Algorithm 1 trees and timings from the existing 48-taxa CSV, runs
only Algorithm 2 on Advantage2_system1 (Zephyr Z12), and writes a separate
comparison CSV.

Options:
  --limit N       Process only the first N sorted inputs (0 means all).
  --force         Rerun completed Z12 quantum results.
  --dry-run       Validate and print the run configuration only.
  -h, --help      Show this help.

Environment overrides:
  INPUT_DIR, SOURCE_CSV, OUTPUT_CSV, WORK_DIR, RF_SCRIPT, WQFM_PYTHON,
  RF_PYTHON, DWAVE_SOLVER, DWAVE_TOPOLOGY, DWAVE_API_TOKEN, ENV_FILE
EOF
}

load_dwave_token_from_env_file() {
    local line value

    [[ -z "${DWAVE_API_TOKEN:-}" && -f "$ENV_FILE" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?DWAVE_API_TOKEN[[:space:]]*=(.*)$ ]]; then
            value="${BASH_REMATCH[2]}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            if [[ ${#value} -ge 2 ]]; then
                if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]] || \
                   [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
                    value="${value:1:${#value}-2}"
                fi
            fi
            if [[ -n "$value" ]]; then
                export DWAVE_API_TOKEN="$value"
                token_source="$ENV_FILE"
            fi
            return 0
        fi
    done < "$ENV_FILE"
}

while (($#)); do
    case "$1" in
        --limit)
            [[ $# -ge 2 ]] || {
                echo "Error: --limit needs a number" >&2
                exit 2
            }
            limit="$2"
            shift 2
            ;;
        --force)
            force=1
            shift
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ "$limit" =~ ^[0-9]+$ ]] || {
    echo "Error: limit must be a non-negative integer" >&2
    exit 2
}
[[ -d "$INPUT_DIR" ]] || {
    echo "Error: input directory not found: $INPUT_DIR" >&2
    exit 1
}
[[ -s "$SOURCE_CSV" ]] || {
    echo "Error: source CSV not found or empty: $SOURCE_CSV" >&2
    exit 1
}
[[ -x "$WQFM_PYTHON" ]] || {
    echo "Error: WQFM Python not executable: $WQFM_PYTHON" >&2
    exit 1
}
[[ -x "$RF_PYTHON" ]] || {
    echo "Error: RF Python not executable: $RF_PYTHON" >&2
    exit 1
}
[[ -f "$RF_SCRIPT" ]] || {
    echo "Error: RF script not found: $RF_SCRIPT" >&2
    exit 1
}

token_source="environment"
load_dwave_token_from_env_file

mapfile -d '' input_files < <(
    find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z
)
if ((${#input_files[@]} == 0)); then
    echo "Error: no input files found in $INPUT_DIR" >&2
    exit 1
fi

selected_count=${#input_files[@]}
if ((limit > 0 && limit < selected_count)); then
    selected_count=$limit
fi

echo "Input directory: $INPUT_DIR"
echo "Quartet files selected: $selected_count of ${#input_files[@]}"
echo "Classical source CSV: $SOURCE_CSV"
echo "Z12 output CSV: $OUTPUT_CSV"
echo "Checkpoint directory: $WORK_DIR"
echo "D-Wave solver: $DWAVE_SOLVER ($DWAVE_TOPOLOGY)"
if [[ -n "${DWAVE_API_TOKEN:-}" ]]; then
    echo "D-Wave token: available from $token_source"
else
    echo "D-Wave token: missing (set DWAVE_API_TOKEN or add it to $ENV_FILE)"
fi

if ((dry_run)); then
    exit 0
fi

if [[ -z "${DWAVE_API_TOKEN:-}" ]]; then
    echo "Error: DWAVE_API_TOKEN is not set" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_CSV")" "$WORK_DIR" "$WORK_DIR/matplotlib"

exec 9>"${WORK_DIR}/.benchmark.lock"
if ! flock -n 9; then
    echo "Error: another Z12 benchmark is already using $WORK_DIR" >&2
    exit 1
fi

"$RF_PYTHON" "$SCORER" \
    --initialize \
    --source-csv "$SOURCE_CSV" \
    --output-csv "$OUTPUT_CSV"

for ((index = 0; index < selected_count; index++)); do
    input_file="${input_files[$index]}"
    file_name="$(basename "$input_file")"
    result_dir="${WORK_DIR}/${file_name}"
    tree_path="${result_dir}/quantum.tre"
    log_path="${result_dir}/quantum.log"
    done_path="${result_dir}/quantum.done"
    mkdir -p "$result_dir"

    echo "[Z12 $((index + 1))/$selected_count] $file_name"
    if [[ "$force" != "1" && -f "$done_path" && -s "$tree_path" && -s "$log_path" ]]; then
        echo "  Reusing completed Z12 quantum result"
    else
        tmp_tree="${tree_path}.tmp.$$"
        tmp_log="${log_path}.tmp.$$"
        rm -f "$done_path"
        if (
            cd "$APP_DIR"
            DWAVE_SOLVER="$DWAVE_SOLVER" \
            WQFM_PYTHON="$WQFM_PYTHON" \
            MPLCONFIGDIR="$WORK_DIR/matplotlib" \
            bash ./run-wqfm.sh -i "$input_file" -o "$tmp_tree" -algo 2
        ) >"$tmp_log" 2>&1; then
            if [[ ! -s "$tmp_tree" ]]; then
                echo "Error: Algorithm 2 completed without a tree" >&2
                mv -f "$tmp_log" "${log_path}.failed"
                exit 1
            fi
            if ! grep -q "^QPU solver: ${DWAVE_SOLVER}$" "$tmp_log"; then
                echo "Error: run did not confirm solver ${DWAVE_SOLVER}" >&2
                mv -f "$tmp_log" "${log_path}.failed"
                exit 1
            fi
            mv -f "$tmp_tree" "$tree_path"
            mv -f "$tmp_log" "$log_path"
            touch "$done_path"
        else
            exit_code=$?
            mv -f "$tmp_log" "${log_path}.failed"
            echo "Error: Z12 run failed for $file_name" >&2
            tail -n 30 "${log_path}.failed" >&2 || true
            exit "$exit_code"
        fi
    fi

    "$RF_PYTHON" "$SCORER" \
        --source-csv "$SOURCE_CSV" \
        --output-csv "$OUTPUT_CSV" \
        --quartet-file "$input_file" \
        --model-tree "$MODEL_TREE" \
        --quantum-tree "$tree_path" \
        --quantum-log "$log_path" \
        --rf-script "$RF_SCRIPT" \
        --quantum-solver "$DWAVE_SOLVER" \
        --quantum-topology "$DWAVE_TOPOLOGY"
done

echo "Z12 benchmark complete: $OUTPUT_CSV"
