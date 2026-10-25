# Running time analysis: wQFM vs wQ²A across datasets

All commands are run from the **repository root** (the directory that contains
`QWQFM/` and `result_analysis/`). Every path below is relative to it.

Drawing the figures only reads finished benchmark runs and needs no D-Wave
token.

## Reproduce the figures (one command)

```bash
bash "result_analysis/running time analysis/run.sh"
```

It runs two steps:

1. `curate_timing.py` reads the run logs and writes
   - `result/timing_per_file.csv` — one row per input file,
   - `result/timing_summary.csv` — one row per dataset (mean over its files),
   - `result/timing_by_taxa.csv` — one row per number of taxa (mean over every
     sample with that many taxa, across datasets);
2. `graph.py` draws `figure/running_time.pdf` and `scaling.py` draws
   `figure/scaling.pdf`, both from `timing_by_taxa.csv`.

## Groups

Samples are grouped by number of taxa and averaged over all samples in a group:

| Group | Samples |
|---|---|
| 37 taxa | 240 simulated + 1 mammals = 241 |
| 46 taxa | 1 angiosperm |
| 48 taxa | 4 avian (all, exon, intron, UCE) |
| 101 taxa | 19 simulated |
| 144 taxa | 1 insect |
| 200 taxa | 1 simulated |

## Per-group figure (`figure/running_time.pdf`)

One panel per group, ordered by number of taxa, each with its own time axis
(seconds, minutes or hours, whichever fits). Every panel shows:

- **End-to-end** — the whole run of wQFM and of wQ²A.
- **Division steps** — the total time of all division (bipartition) steps. The
  wQ²A bar is split into:
  - *QPU access* — D-Wave `qpu_access_time` of every QPU call (and of the Leap
    Hybrid job, for 200 taxa);
  - *Brute force* — partitions with n ≤ 20, solved exactly;
  - *Leap Hybrid solver* — classical part of the Leap Hybrid job (run time
    minus its QPU access); only the 200-taxon run uses it (for n > 150);
  - *Other overhead* — the rest of the division-step time: building the QUBO
    from the quartets, network round trips to D-Wave, and bookkeeping.

A group can carry a caveat note inside its panel (set with `note` in
`curate_timing.py`; none currently).

## Scaling figure (`figure/scaling.pdf`)

Running time (minutes) against number of taxa, both axes linear; one point per
group, joined by lines (46 has an unlabeled tick, since it sits too close to 48
to label).

- **(a)** End-to-end time of wQFM and wQ²A.
- **(b)** Total division-step time: wQFM, wQ²A wall clock, and wQ²A solve time
  only (QPU access + brute force + Leap Hybrid solver), dashed.

## Where every number comes from

All times are read from benchmark logs. The results CSV of each dataset is only
used to decide which input files belong to it.

| Dataset | Files | wQFM logs (`QWQFM/benchmark/work/...`) | wQ²A logs (`QWQFM/benchmark/work/...`) | File list from (`QWQFM/benchmark/output_csv/...`) |
|---|---|---|---|---|
| 37 taxa (simulated) | 240 | `37_taxa_quantum_A1_B1_n_gt_20/` | same | `results_37_taxa_qpu_plus_bruteforce_n>20.csv` |
| 37 taxa (mammals) | 1 | `biological_qpu_plus_bruteforce/` | same | `biological/results_biological_qpu_plus_bruteforce_n>20.csv` |
| 46 taxa (angiosperm) | 1 | `biological_qpu_plus_bruteforce/` | same | same as above |
| 48 taxa (avian: all, exon, intron, UCE) | 1 each | `biological_qpu_plus_bruteforce/` | same | same as above |
| 101 taxa (simulated) | 19 | `101_taxa_qpu_plus_bruteforce/` | same | `results_101_taxa_qpu_plus_bruteforce.csv` |
| 144 taxa (insect) | 1 | `insect_single_gene_144_taxa/` | same | `biological/results_insect_single_gene_144_taxa.csv` |
| 200 taxa (simulated) | 1 | `200_taxa_full/` | same | (single run) |

`timing_per_file.csv` records, for every row, the exact wQFM and wQ²A log it was
read from (`wqfm_log`, `wq2a_log`).

**37-taxon simulated and biological datasets:** the logs of the runs that
produced the two `n>20` CSVs no longer exist. Their timing is taken from the
closest runs of the same input files:
`37_taxa_quantum_A1_B1_n_gt_20` (same 240 files, same n > 20 QPU threshold, QUBO
weight B = 1) and `biological_qpu_plus_bruteforce` (same files, QPU threshold
n > 18). The amniota files in the biological run are not included.

**48-taxon simulated dataset (114 samples) — not included yet.** Its wQ²A times
exist (Zephyr Z12 run on the server), but that run reused wQFM results without
keeping wQFM logs. A local wQFM rerun (`48_taxa_wqfm_only_local/`) gave
topologically identical trees but ran on a machine a median 3.3× slower than
the server (range 2.7×–4.3×), so it would not be a fair comparison. To include
these samples, rerun wQFM on the server (next section), then uncomment the
`48 taxa (simulated)` entry in `DATASETS` in `curate_timing.py` and rerun
`run.sh`.

Log markers used:

| Quantity | Log line |
|---|---|
| End-to-end | `Time taken = N ms` |
| Division steps | `BENCHMARK_BIPARTITION_TIME_NS algorithm=1|2 ... duration_ns=N` |
| QPU access | `'qpu_access_time': N` (microseconds) in `QPU timing:` / `LEAP_HYBRID timing:` lines |
| Brute force | `QUANTUM_BRUTE_FORCE_TIME_NS n=... duration_ns=N` |
| Leap Hybrid run time | `'run_time': N` (microseconds) in `LEAP_HYBRID timing:` lines |

## Timing CSV columns (seconds)

`wqfm_end_to_end_seconds`, `wq2a_end_to_end_seconds`, `wqfm_division_seconds`,
`wq2a_division_seconds`, `wq2a_qpu_access_seconds`, `wq2a_bruteforce_seconds`,
`wq2a_hybrid_solver_seconds`, `wq2a_other_overhead_seconds`.

`timing_summary.csv` and `timing_by_taxa.csv` also have `files` (samples
averaged), `end_to_end_files` (samples with end-to-end times for both methods;
end-to-end means use only those) and `note`.

## Adding or changing a dataset

Datasets are listed in `DATASETS` at the top of `curate_timing.py`. Each entry
names the results CSV that lists its files (`files_from`, optionally narrowed with
`only`) and the run directory holding `<file>/quantum.log` (`run`). wQFM logs
(`<file>/wqfm.log`) are read from `run` too, or from `wqfm_run` if set. A run
with its logs directly in one directory uses `single_run` with `wqfm_log` /
`wq2a_log`. An optional `note` is shown in that group's panel. Then rerun
`run.sh`.

---

## Extra: rerunning wQFM on the server (48-taxon simulated)

For a fair comparison, wQFM must run on the same machine as the wQ²A run it is
compared with — the server, `root@2.25.83.243`. `run_wqfm_only.sh` runs wQFM
only, one file at a time, with the full heap (`-Xmx6g -Xms6g`; override with
`JAVA_TOOL_OPTIONS`), writes `<WORK_DIR>/<file>/wqfm.{tre,log}` and skips
finished files when rerun (`FORCE=1` redoes them). No D-Wave token is needed.

```bash
# 1. Copy the runner to the server (same place relative to the repo root)
ssh root@2.25.83.243 'mkdir -p "/root/dwave/result_analysis/running time analysis"'
scp "result_analysis/running time analysis/run_wqfm_only.sh" \
    'root@2.25.83.243:"/root/dwave/result_analysis/running time analysis/"'

# 2. On the server: run wQFM only on the 114 files (detached, survives logout)
ssh root@2.25.83.243
cd /root/dwave
JAVA_TOOL_OPTIONS="-Xmx6g -Xms6g" setsid nohup bash "result_analysis/running time analysis/run_wqfm_only.sh" \
  QWQFM/WQFM/input_files/48-taxa-weighted-quartets \
  QWQFM/benchmark/work/48_taxa_wqfm_only_server > 48_wqfm_server.log 2>&1 &

# 3. Back on this machine: copy the logs back
scp -r root@2.25.83.243:/root/dwave/QWQFM/benchmark/work/48_taxa_wqfm_only_server QWQFM/benchmark/work/
```

Keep other heavy jobs off the server while it runs so the times are not skewed.

## Extra: running the steps manually

```bash
QWQFM/.venv/bin/python "result_analysis/running time analysis/curate_timing.py" \
  --root . --out-dir "result_analysis/running time analysis/result"

QWQFM/.venv/bin/python "result_analysis/running time analysis/graph.py" \
  --summary "result_analysis/running time analysis/result/timing_by_taxa.csv" \
  --out "result_analysis/running time analysis/figure/running_time.pdf"

QWQFM/.venv/bin/python "result_analysis/running time analysis/scaling.py" \
  --summary "result_analysis/running time analysis/result/timing_by_taxa.csv" \
  --out "result_analysis/running time analysis/figure/scaling.pdf"
```

`graph.py` and `scaling.py` also accept `timing_summary.csv` to draw one panel
(or point) per dataset instead of per group.

To regenerate the underlying runs, use each dataset's own runner (see
`result_analysis/37 Taxa/commands.md`, `result_analysis/48 Taxa/commands.md`,
`result_analysis/101 Taxa/commands.md` and the scripts in
`QWQFM/benchmark/scripts/`); then point `curate_timing.py` at the new run
directories.
