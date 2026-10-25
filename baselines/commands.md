# Baselines: ASTRAL (ASTER) and wQMC

All commands are run from the **repository root** (the directory that contains
`QWQFM/`, `baselines/` and `result_analysis/`). Every path below is relative to it.

Both baselines run on the **same inputs** as wQFM and wQ²A
(`QWQFM/WQFM/input_files/`) and are scored with the **same code**:

- RF: normalized Robinson–Foulds distance, `QWQFM/benchmark/robinson_foulds.py`
  (101 taxa: against the true species tree; 144 and 200 taxa: against the input gene tree).
- Weighted quartet score: four-point test from
  `QWQFM/benchmark/scripts/build_quartet_score_csvs.py`, against the same weighted quartets.
- Time: wall clock of the method's own process, end to end (includes reading the input),
  single-threaded, like wQFM's `Time taken`. Format conversion is timed separately
  (`conversion_seconds`) and not included.

## Folder layout

| Path | What |
|---|---|
| `baselines/tools/ASTER/` | ASTER source, commit `ddc3dc6` (June 25, 2026), built binaries in `bin/` |
| `baselines/tools/wQMC/` | wQMC (`max-cut-tree`) from the authors' Dryad package (see below) |
| `baselines/scripts/` | conversion, run and scoring scripts |
| `baselines/results/astral_results.csv`, `wqmc_results.csv` | one row per input |
| `baselines/results/{astral,wqmc}/<group>/<input>/` | tree, log, `time.txt`, `run.json`, `score.json` |

## ASTRAL (ASTER v1.25.4.8)

Build (already done):

```bash
git clone https://github.com/chaoszhang/ASTER.git baselines/tools/ASTER
(cd baselines/tools/ASTER && make astral wastral)
```

How ASTRAL is run on weighted quartets: ASTRAL normally takes gene trees. Each
weighted quartet `((a,b),(c,d)); w` is written as a four-taxon tree, with `w` in a
matching weights file, and run with

```bash
baselines/tools/ASTER/bin/wastral --mode 4 --treeweights WEIGHTS -t 1 -u 0 -o OUT TREES
```

`--mode 4` turns off support/length weighting and `--treeweights` (an option of
ASTER's `wastral`, see `src/astral-hybrid.cpp`) scales each tree's quartets
linearly by its weight, so ASTRAL maximizes exactly the weighted quartet score
that wQFM and wQ²A maximize. Check: on Amniota AA, ASTER reports `Score: 83604`,
the same value our scorer computes for its tree.

The 144- and 200-taxon inputs are single gene trees; ASTRAL runs on the gene tree
itself with `astral4` (same quartet information as their weighted-quartet files).

Run (finished inputs are skipped on rerun; runs for different groups can go at
the same time, since each merges its rows into `astral_results.csv` under a lock):

```bash
QWQFM/.venv/bin/python baselines/scripts/run_astral.py --only 37 48 --jobs 4
QWQFM/.venv/bin/python baselines/scripts/run_astral.py --only biological 144 200
QWQFM/.venv/bin/python baselines/scripts/run_astral.py --only 101
```

**Memory for 101 taxa:** each replicate has 12.2 million quartets, i.e. 12.2
million input trees. ASTER needs about 1.6 KB per tree (measured on the
angiosperm dataset), so roughly 20 GB of RAM per replicate. Run the 101-taxon
group on a machine with at least 24 GB of RAM.

## wQMC (weighted Quartet MaxCut, Avni, Cohen & Snir 2015)

The binary comes from the authors' Dryad package
(https://datadryad.org/dataset/doi:10.5061/dryad.r9k57, version of Feb 6, 2015),
downloaded by hand because Dryad blocks scripted downloads:

1. The Dryad zip (`doi_10_5061_dryad_r9k57__v20150206.zip`) is kept in
   `baselines/tools/wQMC/download/`. Every file in it matches the MD5 checksum
   Dryad publishes (e.g. `maxCutPack.rar` = `8a29db06cafe034fd4a0b454e153ca9c`).
2. `maxCutPack.rar` is extracted to `baselines/tools/wQMC/maxCutPack/` with
   libarchive (`baselines/tools/.venv-extract`, `pip install libarchive-c`), and its
   64-bit Linux `max-cut-tree` is copied to `baselines/tools/wQMC/max-cut-tree`.

Checks: the binary is deterministic (repeated runs give identical trees) and
recovers a known 20-taxon tree exactly (RF 0) from all of its quartets. The
example output bundled in the package does not correspond to the bundled example
inputs, so it is not used as a check.

Run:

```bash
QWQFM/.venv/bin/python baselines/scripts/run_wqmc.py
```

wQMC needs integer taxon names; `run_wqmc.py` converts each input to wQMC's
format (`a,b|c,d:weight`, as in the wQFM benchmark scripts), runs
`max-cut-tree qrtt=... weights=on otre=...`, and maps the tree back to the
original names.
