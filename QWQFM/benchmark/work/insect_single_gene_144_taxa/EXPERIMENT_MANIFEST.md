# 144-taxon insect single-gene experiment

Created: 2026-07-26 UTC

## Rollback checkpoint

- QWQFM commit before experiment: `3350f8c74b51bce23ee1f5fee40cde10fa9378cf`
- Pre-existing tracked edits, preserved and not modified by this experiment:
  - `WQFM/src/wqfm/algo/FMComputer.java`
  - `WQFM/src/wqfm/algo/FMRunner.java`
- The experiment did not modify algorithm source code.

To revert this experiment, remove only the paths listed under
`Experiment-created paths`.

## Source

- Repository: `https://github.com/shayesteh99/TCMM-Data.git`
- Source commit: `513855c67775131ef892d0e3f9c237b3183ef173`
- Source file: `TreeShrink_data/Insects/unfiltered.trees`
- Selected tree: line 713, the first complete 144-taxon tree
- Raw-tree SHA-256:
  `b0eec6f7e40d5b17076df4b839317e4036561708d7f9e5609158c72ed0f02333`

## Experiment-created paths

- `WQFM/input_files/144-taxa-insect-single-gene/`
- `WQFM/input_files/144-taxa-insect-single-gene-weighted-quartets/`
- `benchmark/work/insect_single_gene_144_taxa/`
- `benchmark/output_csv/biological/results_insect_single_gene_144_taxa.csv`

## Run

- Algorithm order: Algorithm 2 (D-Wave QPU plus brute force), then
  Algorithm 1 (classical FM)
- QUBO parameters: `A=1.0`, `B=0.4`
- QPU threshold: `n > 20`
- QPU reads per submitted bipartition: 1000
- Weighted-quartet count: 17,178,876
- Weighted-quartet SHA-256:
  `dc64e741c7d027cc970b9cf64f3f2b179af1bde914bbc6c527a804c2791806b1`

## Scoring note

The repository scorer normally lets DendroPy translate underscores in Newick
taxon labels to spaces. Scoring was therefore rerun from a temporary copy with
`preserve_underscores=True`. No repository scoring code was changed.
