#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BENCHMARK_DIR}/.." && pwd)"

export INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/WQFM/input_files/48-taxa-weighted-quartets}"
export OUTPUT_CSV="${OUTPUT_CSV:-${BENCHMARK_DIR}/output_csv/results_48_taxa_qpu_plus_bruteforce.csv}"
export WORK_DIR="${WORK_DIR:-${BENCHMARK_DIR}/work/48_taxa_qpu_plus_bruteforce}"
export MODEL_TREE="${MODEL_TREE:-(STRCA,(TINMA,((((CUCCA,(TAUER,CHLUN)),((CAPCA,(CALAN,CHAPE)),(((TYTAL,(CATAU,(HALLE,HALAL))),((COLST,(LEPDI,(APAVI,(BUCRH,(PICPU,MERNU))))),(CARCR,(FALPE,((ACACH,(MANVI,(CORBR,(TAEGU,GEOFO)))),(MELUN,NESNO)))))),(OPHHO,(((GAVST,((PHACA,(NIPNI,(PELCR,EGRGA))),(FULGL,(PYGAD,APTFO)))),(PHALE,EURHE)),(BALRE,CHAVO)))))),((COLLI,(MESUN,PTEGU)),(PHORU,PODCR))),((MELGA,GALGA),ANAPL))));}"

exec "${SCRIPT_DIR}/run_37_taxa_benchmark.sh" "$@"
