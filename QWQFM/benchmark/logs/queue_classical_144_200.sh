#!/usr/bin/env bash
# One-off queue: 144 and 200 taxa first (SA, then tabu), then the remaining
# 101-taxon tabu replicates; one run at a time with a small Java heap (laptop).
cd /home/niloy/Downloads/dwave
run() {  # group solver heap
    local name; [ "$2" = sa ] && name=simulated_annealing || name=tabu_search
    echo "=== $1 $2 (heap $3) start $(date)"
    JOBS=1 JAVA_TOOL_OPTIONS="-Xmx$3 -XX:+UseG1GC" bash "result_analysis/classical solvers/run_classical.sh" "$1" "$2" \
        >> "QWQFM/benchmark/run_$1_${name}.log" 2>&1
    echo "=== $1 $2 exit $? $(date)"
}
run 144 sa 4500m
run 200 sa 4500m
run 144 tabu 4500m
run 200 tabu 4500m
run 101 tabu 4g
echo "QUEUE_DONE $(date)"
