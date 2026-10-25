#!/usr/bin/env bash
# Package each dataset folder (and example file) of WQFM/input_files as <name>.tar.gz for the
# shared Google Drive copy (linked from the repository README), plus
# SHA256SUMS.txt. Archives that pass an integrity test are kept, so an
# interrupted run resumes; each new archive is flushed to disk before use.
# Usage: bash package_input_files.sh [output_dir]   (default ~/Downloads/QUANTA_input_files)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "${SCRIPT_DIR}/../../WQFM/input_files" && pwd)"
OUT="${1:-${HOME}/Downloads/QUANTA_input_files}"
mkdir -p "$OUT"

cd "$SRC"
for d in *; do
    archive="${OUT}/${d}.tar.gz"
    if [[ -f "$archive" ]] && nice -n 19 gzip -t "$archive" 2>/dev/null; then
        echo "ok      $d"
        continue
    fi
    echo "packing $d"
    nice -n 19 tar -czf "${archive}.part" "$d" && sync "${archive}.part" &&
        mv -f "${archive}.part" "$archive" && sync "$OUT" || { echo "FAILED  $d"; exit 1; }
done
cd "$OUT" && sha256sum *.tar.gz > SHA256SUMS.txt && sync SHA256SUMS.txt && echo "PACKAGING_DONE $(date)"
