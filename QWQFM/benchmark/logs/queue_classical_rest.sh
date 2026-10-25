#!/usr/bin/env bash
# One-off queue: after the running 101-taxon SA job, run the remaining
# classical-solver jobs one at a time with a small Java heap (laptop).
cd /home/niloy/Downloads/dwave
while pgrep -f '^bash result_analysis/classical solvers/run_classical.sh 101 sa' >/dev/null; do sleep 15; done
run() {  # group solver heap
    echo "=== $1 $2 (heap $3) start $(date)"
    JOBS=1 JAVA_TOOL_OPTIONS="-Xmx$3 -XX:+UseG1GC" bash "result_analysis/classical solvers/run_classical.sh" "$1" "$2" \
        > "QWQFM/benchmark/run_$1_$( [ "$2" = sa ] && echo simulated_annealing || echo tabu_search ).log" 2>&1
    echo "=== $1 $2 exit $? $(date)"
}
run 101 tabu 4g
run 144 sa 4500m
run 144 tabu 4500m
run 200 sa 4500m
run 200 tabu 4500m
echo "QUEUE_DONE $(date)"
