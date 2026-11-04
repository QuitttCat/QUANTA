# S201 replicate 01, 100 true gene trees pruned to 150 taxa

Created: 2026-07-26 UTC

## Rollback checkpoint

- QWQFM commit before experiment:
  `3350f8c74b51bce23ee1f5fee40cde10fa9378cf`
- Pre-existing tracked edits, preserved and not modified by this experiment:
  - `WQFM/src/wqfm/algo/FMComputer.java`
  - `WQFM/src/wqfm/algo/FMRunner.java`
- Pre-existing untracked result, preserved and not modified:
  - `benchmark/output_csv/biological/results_insect_single_gene_144_taxa.csv`
- This experiment does not modify algorithm source code.

To revert this experiment, remove only the paths under
`Experiment-created paths`.

## Source

- Repository: `https://github.com/shayesteh99/TCMM-Data.git`
- Source commit: `513855c67775131ef892d0e3f9c237b3183ef173`
- Source file: `S200-perturbed/01/truegenetrees_100`
- Source contents: 100 fully binary simulated true gene trees, each with
  the same 201 taxa (`0` through `200`)
- Source SHA-256:
  `33fead57dc1419431736716df7833fcd3bf85e913a6310ea44ce9f8039c94fbd`

## Pruning

- Every source tree was restricted to taxa `0` through `149`.
- Unary nodes created by pruning were suppressed.
- Branch lengths and rooting annotations were omitted because quartet
  topology and WQFM do not use them.
- Pruned-tree SHA-256:
  `29e281ecb8fe20bf154f8f5d46c7b1abc83712c5a64db9b9bf8c277e236ac7b6`

## Weighted quartets

- Four-taxon subsets: `C(150,4) = 20,260,275`
- Gene-tree observations per subset: 100
- Total quartet weight: 2,026,027,500
- Nonzero weighted-quartet records: 56,713,973
- Weighted-quartet SHA-256:
  `2c3b6562f33c7f403f1a088e8d730cf134ee9edf24a7f40e1cddfcae73406a68`
- Generation wall time: 12.50 seconds
- Generator peak RSS: 51,456 KB
- Compact generator source SHA-256:
  `8e846695857a01fc7c4aea1b7a69d5ca2b92ab92979c9df312ecca8457a3212a`
- Correctness validation: its complete 8-taxon output (70 quartets) matched
  the repository's `triplets.soda2103` enumerator exactly.

## Algorithm 2 memory handling

- The repository's normal QUBO script stores every quartet as nested Python
  tuples before building the QUBO. The 56,713,973-record root problem would
  require excessive memory.
- This experiment uses the isolated runtime copy `qaoa_streaming.py`, which
  accumulates exactly the same diagonal and pairwise QUBO coefficients while
  reading the Java stream.
- No repository algorithm source was modified.
- Runtime QUBO script SHA-256:
  `9fa4168e7c8e1dfcf742670e0d7bc37fd5429c28ba48103c1a29b31833782d9d`
- Exactness validation: for 10,000 deterministic random weighted quartets,
  the normal and streaming builders produced identical taxon mappings and
  QUBO matrices (`max_abs_difference = 0.0`).

## Experiment-created paths

- `WQFM/input_files/150-taxa-s201-rep01-true-gene-trees/`
- `WQFM/input_files/150-taxa-s201-rep01-true-gene-trees-weighted-quartets/`
- `benchmark/work/s201_rep01_true_gene_trees_100_pruned_150/`
- `benchmark/output_csv/true_gene_tree/results_s201_rep01_true_gene_trees_100_pruned_150.csv`

## Completed benchmark

- Algorithm order: Algorithm 2 first, then Algorithm 1.
- Both algorithms completed 147 bipartitions and produced saved trees.
- Weighted-quartet scoring used all 56,713,973 nonzero records and the
  original total weight of 2,026,027,500.
- Classical WQFM score: 1,456,684,958 (71.8985777834%).
- Quantum WQFM score: 1,456,676,328 (71.8981518267%).
- Result code: `-1` (classical WQFM better).
- Classical advantage: 8,630 weighted quartet observations, or
  0.0004259567 percentage points of total weight.

## Timing

- Classical summed bipartition time: 3,725.409899797 seconds.
- Classical summed core-division time: 3,711.740219037 seconds.
- Classical root bipartition time: 3,180.772619005 seconds.
- Classical root core-division time: 3,169.149306604 seconds.
- Algorithm 2 QPU jobs: 11, all on `Advantage_system4`.
- Algorithm 2 summed QPU access time: 2.053958360 seconds.
- Algorithm 2 summed brute-force time: 8.561456847 seconds.
- Algorithm 2 QPU-plus-brute-force benchmark time: 10.615415207 seconds.
- Algorithm 2 summed full bipartition wall time, including QUBO construction
  and embedding overhead: 483.044948167 seconds.

## Result integrity

- CSV SHA-256:
  `3551a7fcb6840cf1d17ca1107d31b3d2d46d206833cdd146038884cf0941db69`
- Classical tree SHA-256:
  `4624845530716a951b89fd6aebfdc0859a69cb051503175bbcda5e0df0d1cd14`
- Quantum tree SHA-256:
  `3cf534055ec35783c643928b3e0461dfad6b4bffb5f428cff03dc62ab563b96b`
- Classical log SHA-256:
  `b8c8a8e37c20ba96055dc63e8a0a7b8135ea64f5fe0ada7577f54ce000eaae47`
- Quantum log SHA-256:
  `f7fe4223c8cbc8f74413993c13adfdd8da164d09af0a3c78b6cfc27e150c8e4b`
