#!/usr/bin/env bash
# Run QUANTA (Algorithm 2) with a classical QUBO solver in place of the D-Wave
# QPU: partitions with n>20 taxa go to simulated annealing (sa) or tabu search
# (tabu), smaller ones to brute force, exactly as in the QPU runs. The solver
# is plugged in through WQFM_QUBO_SCRIPT (WQFM/src/wqfm/algo/quantum/qaoa_classical.py);
# qaoa.py is not changed. No D-Wave token is used. wQFM is deterministic, so
# its columns are taken from the QPU run's CSV instead of being recomputed.
#
# Usage: [JOBS=N] INPUT_DIR=... WORK_DIR=... RESULT_CSV=... [scoring] \
#        bash run_classical_benchmark.sh sa|tabu
#   INPUT_DIR          weighted-quartet files to run
#   WORK_DIR           per-file trees and logs (finished files are skipped)
#   RESULT_CSV         output CSV
#   JOBS               quartet files run at once (default 1); each run is single-threaded
# Scoring, one of:
#   MODEL_TREE_SCRIPT + QPU_CSV   one shared true tree (37, 48 taxa): RF, wQFM
#                                 columns copied from the QPU run (summarize_classical.py)
#   REFERENCE_DIR + REFERENCE_SUFFIX, REFERENCE_FILE, or neither:
#                                 weighted quartet score, plus RF against a
#                                 per-input or single reference (score_classical.py)
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
app_dir="${REPO_DIR}/WQFM"
python_bin="${REPO_DIR}/.venv/bin/python"

solver="${1:-}"
[[ "$solver" == sa || "$solver" == tabu ]] || { echo "Usage: $0 sa|tabu" >&2; exit 2; }
: "${INPUT_DIR:?}" "${WORK_DIR:?}" "${RESULT_CSV:?}"
work_dir="$WORK_DIR"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx1g}"
export WQFM_PYTHON="$python_bin"
export WQFM_QUBO_SCRIPT="${app_dir}/src/wqfm/algo/quantum/qaoa_classical.py"
export WQ2A_CLASSICAL_SOLVER="$solver"
export MPLCONFIGDIR="${work_dir}/matplotlib"
# One thread per run, so JOBS parallel runs do not oversubscribe the CPU.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# These runs must never reach the QPU: without a token, any QPU call fails.
unset DWAVE_API_TOKEN

mkdir -p "$work_dir" "$MPLCONFIGDIR" "$(dirname "$RESULT_CSV")"
(cd "$app_dir" && ant -q jar)

run_one() {
    local input_file="$1" file_name result_dir
    file_name="$(basename "$input_file")"
    result_dir="${work_dir}/${file_name}"
    mkdir -p "$result_dir"
    if [[ -f "${result_dir}/quantum.done" ]]; then
        return 0
    fi
    if (cd "$app_dir" && bash ./run-wqfm.sh -i "$input_file" -o "${result_dir}/quantum.tre.tmp" -algo 2) \
            >"${result_dir}/quantum.log.tmp" 2>&1 && [[ -s "${result_dir}/quantum.tre.tmp" ]]; then
        # Flush before marking done: a WSL restart once left finished files empty.
        sync "${result_dir}/quantum.tre.tmp" "${result_dir}/quantum.log.tmp"
        mv -f "${result_dir}/quantum.tre.tmp" "${result_dir}/quantum.tre"
        mv -f "${result_dir}/quantum.log.tmp" "${result_dir}/quantum.log"
        touch "${result_dir}/quantum.done"
        sync "$result_dir"
        echo "[$(find "$work_dir" -name quantum.done | wc -l)/$total done] $file_name"
    else
        mv -f "${result_dir}/quantum.log.tmp" "${result_dir}/quantum.log.failed"
        echo "Error: $solver run failed for $file_name; see ${result_dir}/quantum.log.failed" >&2
        tail -n 20 "${result_dir}/quantum.log.failed" >&2 || true
        return 1
    fi
}

total="$(find "$INPUT_DIR" -maxdepth 1 -type f | wc -l)"
export -f run_one
export app_dir work_dir solver total
find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z |
    xargs -0 -P "${JOBS:-1}" -I{} bash -c 'run_one "$1"' _ {}

if [[ -n "${MODEL_TREE_SCRIPT:-}" ]]; then
    "$python_bin" "${SCRIPT_DIR}/summarize_classical.py" --solver "$solver" --work-dir "$work_dir" \
        --model-tree-script "$MODEL_TREE_SCRIPT" --qpu-csv "${QPU_CSV:?}" --out "$RESULT_CSV"
else
    reference_args=()
    [[ -n "${REFERENCE_DIR:-}" ]] && reference_args+=(--reference-dir "$REFERENCE_DIR" --reference-suffix "${REFERENCE_SUFFIX:-}")
    [[ -n "${REFERENCE_FILE:-}" ]] && reference_args+=(--reference-file "$REFERENCE_FILE")
    "$python_bin" "${SCRIPT_DIR}/score_classical.py" --solver "$solver" --work-dir "$work_dir" \
        --input-dir "$INPUT_DIR" "${reference_args[@]}" --out "$RESULT_CSV"
fi
sync "$RESULT_CSV"
