#!/usr/bin/env bash
# Run ASTRAL, simulated annealing (sa) and tabu search (tabu) on the 200-taxon
# input (s200 replicate 1, one true gene tree, 64.7 million weighted quartets)
# and collect each method's results CSV in "result_analysis/200 Taxa/result/".
#
#   astral  ASTER astral4 on the gene tree itself (baselines/scripts/run_astral.py)
#   sa      QUANTA with simulated annealing for partitions with n>20 taxa,
#           brute force below ("result_analysis/classical solvers/run_classical.sh")
#   tabu    the same with tabu search
#
# Every tree is scored by weighted quartet score and by RF distance to the
# input gene tree. sa and tabu use a 26 GB Java heap each (set by
# run_classical.sh); run them one after the other unless the machine has
# room for both. Finished runs are skipped on rerun.
#
# Inputs (QWQFM/WQFM/input_files/):
#   200-taxa-s200-rep01-true-gene-tree/s200_rep01_true_gene_tree_001_200_taxa.tre
#   200-taxa-s200-rep01-true-gene-tree-weighted-quartets/s200_rep01_true_gene_tree_001_200_taxa.weighted_quartets
#
# Usage, from anywhere: bash "result_analysis/200 Taxa/run_200_taxa.sh" [astral] [sa] [tabu]
#                       (no argument: all three, in that order)
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
PYTHON="${ROOT}/QWQFM/.venv/bin/python"
# Apache Ant builds the wQFM jar; use a local install if ant is not on PATH.
command -v ant >/dev/null || export PATH="${HOME}/.local/opt/apache-ant-1.10.15/bin:${PATH}"

mkdir -p "${HERE}/result"
methods=("$@")
[[ ${#methods[@]} -gt 0 ]] || methods=(astral sa tabu)

for method in "${methods[@]}"; do
    echo "=== 200 taxa ${method}: start $(date '+%F %T')"
    case "$method" in
        astral)
            (cd "$ROOT" && "$PYTHON" baselines/scripts/run_astral.py --only 200)
            "$PYTHON" - "${ROOT}/baselines/results/astral_results.csv" "${HERE}/result/astral_200_taxa.csv" <<'EOF'
import csv, sys
with open(sys.argv[1], newline="") as handle:
    reader = csv.DictReader(handle)
    rows = [r for r in reader if r["group"] == "200"]
with open(sys.argv[2], "w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"Saved {sys.argv[2]}")
EOF
            ;;
        sa|tabu)
            name=$([[ "$method" == sa ]] && echo simulated_annealing || echo tabu_search)
            bash "${ROOT}/result_analysis/classical solvers/run_classical.sh" 200 "$method"
            cp "${ROOT}/result_analysis/classical solvers/result/results_200_${name}_plus_bruteforce_n>20.csv" \
               "${HERE}/result/"
            echo "Saved ${HERE}/result/results_200_${name}_plus_bruteforce_n>20.csv"
            ;;
        *) echo "Unknown method: $method (use astral, sa or tabu)" >&2; exit 2 ;;
    esac
    echo "=== 200 taxa ${method}: done $(date '+%F %T')"
done
