#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/WQFM"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"

INPUT_DIR="${INPUT_DIR:-${APP_DIR}/input_files/37-taxa-weighted-quartets}"
OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_37_taxa_qpu_plus_bruteforce.csv}"
WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/37_taxa_qpu_plus_bruteforce}"
RF_SCRIPT="${RF_SCRIPT:-${BENCHMARK_DIR}/robinson_foulds.py}"
WQFM_PYTHON="${WQFM_PYTHON:-${REPO_DIR}/.venv/bin/python}"
RF_PYTHON="${RF_PYTHON:-${REPO_DIR}/.venv/bin/python}"
SCORER="${SCRIPT_DIR}/score_benchmark_row.py"
ENV_FILE="${ENV_FILE:-${WORKSPACE_DIR}/.env}"

MODEL_TREE="${MODEL_TREE:-(GAL,(ORN,(((((PRO,LOX),ECH),(DAS,CHO)),((((OTO,MIC),((CAL,((PON,(GOR,(HOM,PAN))),NEW)),TAR)),(((OCH,ORY),(SPE,((DIP,(RAT,MUS)),CAV))),TUP)),(((PTE,MYO),((EQU,(FEL,CAN)),((SUS,(BOS,TUR)),VIC))),(ERI,SOR)))),(MON,MAC))));}"
MODEL_TREE_DIR="${MODEL_TREE_DIR:-}"
MODEL_TREE_SUFFIX="${MODEL_TREE_SUFFIX:-.SPECIES_TREE}"

limit="${LIMIT:-0}"
force="${FORCE:-0}"
quantum_first="${QUANTUM_FIRST:-0}"
dry_run=0

usage() {
    cat <<'EOF'
Usage: benchmark/scripts/run_<taxa>_taxa_benchmark.sh [options]

Runs Algorithm 1 (WQFM) and Algorithm 2 (D-Wave quantum annealing) for every
regular file in the configured INPUT_DIR and writes one CSV row per quartet
file.

Options:
  --limit N       Process only the first N sorted input files (0 means all).
  --force         Rerun completed algorithms and replace their saved results.
  --dry-run       Show the resolved paths and file count without running jobs.
  -h, --help      Show this help.

Environment overrides:
  INPUT_DIR, OUTPUT_CSV, WORK_DIR, RF_SCRIPT, WQFM_PYTHON, RF_PYTHON,
  MODEL_TREE, MODEL_TREE_DIR, MODEL_TREE_SUFFIX, LIMIT, FORCE,
  QUANTUM_FIRST, DWAVE_API_TOKEN, ENV_FILE
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
            [[ $# -ge 2 ]] || { echo "Error: --limit needs a number" >&2; exit 2; }
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

[[ "$limit" =~ ^[0-9]+$ ]] || { echo "Error: limit must be a non-negative integer" >&2; exit 2; }
[[ "$quantum_first" =~ ^[01]$ ]] || { echo "Error: QUANTUM_FIRST must be 0 or 1" >&2; exit 2; }
[[ -d "$INPUT_DIR" ]] || { echo "Error: input directory not found: $INPUT_DIR" >&2; exit 1; }
[[ -f "$APP_DIR/run-wqfm.sh" ]] || { echo "Error: run-wqfm.sh not found" >&2; exit 1; }
[[ -f "$SCORER" ]] || { echo "Error: scorer not found: $SCORER" >&2; exit 1; }
[[ -f "$RF_SCRIPT" ]] || { echo "Error: RF script not found: $RF_SCRIPT" >&2; exit 1; }
[[ -x "$WQFM_PYTHON" ]] || { echo "Error: WQFM Python not executable: $WQFM_PYTHON" >&2; exit 1; }
[[ -x "$RF_PYTHON" ]] || { echo "Error: RF Python not executable: $RF_PYTHON" >&2; exit 1; }
if [[ -n "$MODEL_TREE_DIR" && ! -d "$MODEL_TREE_DIR" ]]; then
    echo "Error: model-tree directory not found: $MODEL_TREE_DIR" >&2
    exit 1
fi

token_source="environment"
load_dwave_token_from_env_file

mapfile -d '' input_files < <(find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z)
if ((${#input_files[@]} == 0)); then
    echo "Error: no input files found in $INPUT_DIR" >&2
    exit 1
fi

selected_count=${#input_files[@]}
if ((limit > 0 && limit < selected_count)); then
    selected_count=$limit
fi

model_tree_files=()
if [[ -n "$MODEL_TREE_DIR" ]]; then
    for ((index = 0; index < selected_count; index++)); do
        file_name="$(basename "${input_files[$index]}")"
        model_key="${file_name%%.*}"
        model_tree_file="${MODEL_TREE_DIR}/${model_key}${MODEL_TREE_SUFFIX}"
        if [[ ! -s "$model_tree_file" ]]; then
            echo "Error: no true tree for $file_name; expected $model_tree_file" >&2
            exit 1
        fi
        model_tree_files+=("$model_tree_file")
    done
fi

echo "Input directory: $INPUT_DIR"
echo "Quartet files selected: $selected_count of ${#input_files[@]}"
echo "CSV output: $OUTPUT_CSV"
echo "Checkpoint directory: $WORK_DIR"
if ((quantum_first)); then
    echo "Algorithm order: all 2 (quantum), then all 1 (wqfm)"
else
    echo "Algorithm order: 1 (wqfm), then 2 (quantum)"
fi
if [[ -n "$MODEL_TREE_DIR" ]]; then
    echo "True-tree directory: $MODEL_TREE_DIR"
    echo "True-tree mapping: <quartet prefix>${MODEL_TREE_SUFFIX}"
fi
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

echo "Building wQFM..."
(cd "$APP_DIR" && ant jar)

run_algorithm() {
    local input_file="$1"
    local algorithm="$2"
    local result_dir="$3"
    local label tree_path log_path done_path tmp_tree tmp_log

    if [[ "$algorithm" == "1" ]]; then
        label="wqfm"
    else
        label="quantum"
    fi

    tree_path="${result_dir}/${label}.tre"
    log_path="${result_dir}/${label}.log"
    done_path="${result_dir}/${label}.done"

    if [[ "$force" != "1" && -f "$done_path" && -s "$tree_path" && -s "$log_path" ]]; then
        echo "  Reusing completed Algorithm $algorithm ($label)"
        return
    fi

    tmp_tree="${tree_path}.tmp.$$"
    tmp_log="${log_path}.tmp.$$"
    rm -f "$done_path"
    echo "  Running Algorithm $algorithm ($label)..."

    if (
        cd "$APP_DIR"
        WQFM_PYTHON="$WQFM_PYTHON" \
        MPLCONFIGDIR="$WORK_DIR/matplotlib" \
        bash ./run-wqfm.sh -i "$input_file" -o "$tmp_tree" -algo "$algorithm"
    ) >"$tmp_log" 2>&1; then
        if [[ ! -s "$tmp_tree" ]]; then
            echo "Error: Algorithm $algorithm completed without producing a tree" >&2
            mv -f "$tmp_log" "${log_path}.failed"
            return 1
        fi
        mv -f "$tmp_tree" "$tree_path"
        mv -f "$tmp_log" "$log_path"
        touch "$done_path"
    else
        local exit_code=$?
        mv -f "$tmp_log" "${log_path}.failed"
        echo "Error: Algorithm $algorithm failed for $(basename "$input_file")" >&2
        echo "See ${log_path}.failed" >&2
        tail -n 30 "${log_path}.failed" >&2 || true
        return "$exit_code"
    fi
}

if ((quantum_first)); then
    echo "Quantum-first phase: running Algorithm 2 for all selected files"
    for ((index = 0; index < selected_count; index++)); do
        input_file="${input_files[$index]}"
        file_name="$(basename "$input_file")"
        result_dir="${WORK_DIR}/${file_name}"
        mkdir -p "$result_dir"

        echo "[quantum $((index + 1))/$selected_count] $file_name"
        run_algorithm "$input_file" 2 "$result_dir"
    done
fi

for ((index = 0; index < selected_count; index++)); do
    input_file="${input_files[$index]}"
    file_name="$(basename "$input_file")"
    result_dir="${WORK_DIR}/${file_name}"
    mkdir -p "$result_dir"

    if ((quantum_first)); then
        echo "[wqfm $((index + 1))/$selected_count] $file_name"
        run_algorithm "$input_file" 1 "$result_dir"
    else
        echo "[$((index + 1))/$selected_count] $file_name"
        run_algorithm "$input_file" 1 "$result_dir"
        run_algorithm "$input_file" 2 "$result_dir"
    fi

    model_args=(--model-tree "$MODEL_TREE")
    if [[ -n "$MODEL_TREE_DIR" ]]; then
        model_args=(--model-tree-file "${model_tree_files[$index]}")
    fi

    "$RF_PYTHON" "$SCORER" \
        --quartet-file "$input_file" \
        "${model_args[@]}" \
        --wqfm-tree "${result_dir}/wqfm.tre" \
        --quantum-tree "${result_dir}/quantum.tre" \
        --wqfm-log "${result_dir}/wqfm.log" \
        --quantum-log "${result_dir}/quantum.log" \
        --rf-script "$RF_SCRIPT" \
        --output-csv "$OUTPUT_CSV"
done

echo "Benchmark complete: $OUTPUT_CSV"
