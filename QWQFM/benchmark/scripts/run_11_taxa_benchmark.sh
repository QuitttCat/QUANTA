#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/WQFM"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"

INPUT_DIR="${INPUT_DIR:-${APP_DIR}/input_files/11-taxa-weighted-quartets}"
OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_11_taxa_bruteforce.csv}"
WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/11_taxa_bruteforce}"
RF_SCRIPT="${RF_SCRIPT:-${BENCHMARK_DIR}/robinson_foulds.py}"
WQFM_PYTHON="${WQFM_PYTHON:-${REPO_DIR}/.venv/bin/python}"
RF_PYTHON="${RF_PYTHON:-${REPO_DIR}/.venv/bin/python}"
SCORER="${SCRIPT_DIR}/score_11_taxa_row.py"

# Algorithms run after `cd "$APP_DIR"`, so caller-relative paths must be anchored now.
INPUT_DIR="$(realpath -m "$INPUT_DIR")"
OUTPUT_CSV="$(realpath -m "$OUTPUT_CSV")"
WORK_DIR="$(realpath -m "$WORK_DIR")"
RF_SCRIPT="$(realpath -m "$RF_SCRIPT")"

# The 11-taxon dataset mixes two label conventions sharing the same topology:
# "estimated_*" files use plain integer leaf labels (1..11) and need
# true_tree_trimmed; "simulated_*" files use decimal labels (1.1..11.11) and
# need model_tree. Picked per-file by filename prefix below.
ESTIMATED_MODEL_TREE_FILE="${ESTIMATED_MODEL_TREE_FILE:-${WORKSPACE_DIR}/dataset/11-taxon/true_tree_trimmed}"
SIMULATED_MODEL_TREE_FILE="${SIMULATED_MODEL_TREE_FILE:-${WORKSPACE_DIR}/dataset/11-taxon/model_tree}"

# Datasets with a single label convention set MODEL_TREE_FILE to score every
# file against one true tree, bypassing the estimated/simulated split above.
MODEL_TREE_FILE="${MODEL_TREE_FILE:-}"
if [[ -n "$MODEL_TREE_FILE" ]]; then
    MODEL_TREE_FILE="$(realpath -m "$MODEL_TREE_FILE")"
fi

# This dataset never exceeds n=11 per partition, so Algorithm 2 never crosses
# the n>20 QPU threshold -- it is pure brute force. No D-Wave token needed.

limit="${LIMIT:-0}"
force="${FORCE:-0}"
dry_run=0

usage() {
    cat <<'EOF'
Usage: benchmark/scripts/run_11_taxa_benchmark.sh [options]

Runs Algorithm 1 (WQFM) and Algorithm 2 (brute force -- this dataset never
crosses the n>20 QPU threshold) for every file in INPUT_DIR and writes one
CSV row per quartet file: quartet_file_name, wqfm_tree, bruteforce_tree,
rf_wqfm_wrt_base, rf_bruteforce_wrt_base.

Options:
  --limit N       Process only the first N sorted input files (0 means all).
  --force         Rerun completed algorithms and replace their saved results.
  --dry-run       Show the resolved paths and file count without running jobs.
  -h, --help      Show this help.

Environment overrides:
  INPUT_DIR, OUTPUT_CSV, WORK_DIR, RF_SCRIPT, WQFM_PYTHON, RF_PYTHON,
  ESTIMATED_MODEL_TREE_FILE, SIMULATED_MODEL_TREE_FILE, MODEL_TREE_FILE,
  LIMIT, FORCE
EOF
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
[[ -d "$INPUT_DIR" ]] || { echo "Error: input directory not found: $INPUT_DIR" >&2; exit 1; }
[[ -f "$APP_DIR/run-wqfm.sh" ]] || { echo "Error: run-wqfm.sh not found" >&2; exit 1; }
[[ -f "$SCORER" ]] || { echo "Error: scorer not found: $SCORER" >&2; exit 1; }
[[ -f "$RF_SCRIPT" ]] || { echo "Error: RF script not found: $RF_SCRIPT" >&2; exit 1; }
[[ -x "$WQFM_PYTHON" ]] || { echo "Error: WQFM Python not executable: $WQFM_PYTHON" >&2; exit 1; }
[[ -x "$RF_PYTHON" ]] || { echo "Error: RF Python not executable: $RF_PYTHON" >&2; exit 1; }
if [[ -n "$MODEL_TREE_FILE" ]]; then
    [[ -f "$MODEL_TREE_FILE" ]] || { echo "Error: model tree not found: $MODEL_TREE_FILE" >&2; exit 1; }
else
    [[ -f "$ESTIMATED_MODEL_TREE_FILE" ]] || { echo "Error: estimated model tree not found: $ESTIMATED_MODEL_TREE_FILE" >&2; exit 1; }
    [[ -f "$SIMULATED_MODEL_TREE_FILE" ]] || { echo "Error: simulated model tree not found: $SIMULATED_MODEL_TREE_FILE" >&2; exit 1; }
fi

mapfile -d '' input_files < <(find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z)
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
echo "CSV output: $OUTPUT_CSV"
echo "Checkpoint directory: $WORK_DIR"
echo "Algorithm order: 1 (wqfm), then 2 (bruteforce)"
if [[ -n "$MODEL_TREE_FILE" ]]; then
    echo "Model tree (all files): $MODEL_TREE_FILE"
else
    echo "Estimated-mode model tree: $ESTIMATED_MODEL_TREE_FILE"
    echo "Simulated-mode model tree: $SIMULATED_MODEL_TREE_FILE"
fi
if [[ -n "${JAVA_TOOL_OPTIONS:-}" ]]; then
    echo "JVM options: $JAVA_TOOL_OPTIONS"
fi

if ((dry_run)); then
    exit 0
fi

mkdir -p "$(dirname "$OUTPUT_CSV")" "$WORK_DIR" "$WORK_DIR/matplotlib"

{
    echo "# Run started: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "# Working directory: $(pwd)"
    echo "JAVA_TOOL_OPTIONS=${JAVA_TOOL_OPTIONS:-} \\"
    echo "INPUT_DIR=$INPUT_DIR \\"
    echo "OUTPUT_CSV=$OUTPUT_CSV \\"
    echo "WORK_DIR=$WORK_DIR \\"
    echo "bash ${SCRIPT_DIR}/run_11_taxa_benchmark.sh $*"
} >> "${WORK_DIR}/RUN_COMMANDS.txt"

echo "Building wQFM..."
(cd "$APP_DIR" && ant jar)

model_tree_file_for() {
    local file_name="$1"
    if [[ -n "$MODEL_TREE_FILE" ]]; then
        echo "$MODEL_TREE_FILE"
        return
    fi
    case "$file_name" in
        estimated_*) echo "$ESTIMATED_MODEL_TREE_FILE" ;;
        simulated_*) echo "$SIMULATED_MODEL_TREE_FILE" ;;
        *)
            echo "Error: cannot infer estimated/simulated mode from file name: $file_name" >&2
            exit 1
            ;;
    esac
}

run_algorithm() {
    local input_file="$1"
    local algorithm="$2"
    local result_dir="$3"
    local label tree_path log_path done_path tmp_tree tmp_log

    if [[ "$algorithm" == "1" ]]; then
        label="wqfm"
    else
        label="bruteforce"
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

for ((index = 0; index < selected_count; index++)); do
    input_file="${input_files[$index]}"
    file_name="$(basename "$input_file")"
    result_dir="${WORK_DIR}/${file_name}"
    mkdir -p "$result_dir"

    echo "[$((index + 1))/$selected_count] $file_name"
    run_algorithm "$input_file" 1 "$result_dir"
    run_algorithm "$input_file" 2 "$result_dir"

    model_tree_file="$(model_tree_file_for "$file_name")"

    "$RF_PYTHON" "$SCORER" \
        --quartet-file "$input_file" \
        --model-tree-file "$model_tree_file" \
        --wqfm-tree "${result_dir}/wqfm.tre" \
        --bruteforce-tree "${result_dir}/bruteforce.tre" \
        --rf-script "$RF_SCRIPT" \
        --output-csv "$OUTPUT_CSV"
done

echo "Benchmark complete: $OUTPUT_CSV"
