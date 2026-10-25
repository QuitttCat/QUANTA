#!/usr/bin/env bash
# Run wQFM (algorithm 1) only, one quartet file at a time, saving
# <WORK_DIR>/<file>/wqfm.{tre,log}. Needs no D-Wave token. Finished files are
# skipped on rerun (FORCE=1 to redo them).
# Usage: bash "result_analysis/running time analysis/run_wqfm_only.sh" INPUT_DIR WORK_DIR
set -Eeuo pipefail

[[ $# -eq 2 ]] || { echo "Usage: $0 INPUT_DIR WORK_DIR" >&2; exit 2; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
APP_DIR="${ROOT}/QWQFM/WQFM"
INPUT_DIR="$(realpath "$1")"
WORK_DIR="$(realpath -m "$2")"

export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Xmx6g -Xms6g}"

mapfile -d '' files < <(find "$INPUT_DIR" -maxdepth 1 -type f -print0 | sort -z)
((${#files[@]})) || { echo "Error: no files in $INPUT_DIR" >&2; exit 1; }
mkdir -p "$WORK_DIR"
echo "JVM options: $JAVA_TOOL_OPTIONS"

echo "Building wQFM..."
(cd "$APP_DIR" && ant -q jar)

for ((i = 0; i < ${#files[@]}; i++)); do
    name="$(basename "${files[$i]}")"
    out="${WORK_DIR}/${name}"
    if [[ "${FORCE:-0}" != 1 && -f "${out}/wqfm.done" ]]; then
        echo "[$((i + 1))/${#files[@]}] $name (done, skipped)"
        continue
    fi
    mkdir -p "$out"
    echo "[$((i + 1))/${#files[@]}] $name"
    (cd "$APP_DIR" && bash ./run-wqfm.sh -i "${files[$i]}" -o "${out}/wqfm.tre" -algo 1) \
        >"${out}/wqfm.log" 2>&1
    touch "${out}/wqfm.done"
done
echo "wQFM-only run complete: $WORK_DIR"
