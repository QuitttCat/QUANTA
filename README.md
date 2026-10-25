# QUANTA

QUANTA estimates species trees from weighted quartets. It keeps the
divide-and-conquer framework of wQFM and solves each bipartition step as a
QUBO on a quantum annealer (D-Wave).

## Input data

The weighted-quartet inputs are about 15 GB, too large for GitHub. They are
shared as one compressed archive per dataset (2.0 GB in total) here:

**[QUANTA input files (Google Drive)](https://drive.google.com/drive/folders/146aYkrE9gcgDiJst78e6Bp7wWcDZxZVR?usp=sharing)**

Download the archives you need, check them, and unpack them into
`QWQFM/WQFM/input_files/`, where all run scripts look for their input:

```bash
cd /path/to/downloads
sha256sum -c --ignore-missing SHA256SUMS.txt
mkdir -p /path/to/repo/QWQFM/WQFM/input_files
for f in *.tar.gz; do tar -xzf "$f" -C /path/to/repo/QWQFM/WQFM/input_files; done
```

| Archive | Contents | Size (compressed) |
|---|---|---|
| `11-taxa-weighted-quartets` | 11-taxon simulated dataset: 200 files (estimated and true gene trees, 5–100 genes, strong ILS, 20 replicates) | < 1 MB |
| `15-taxa-weighted-quartets` | 15-taxon simulated dataset: 60 files (100 and 1000 genes; 100 bp, 1000 bp and true gene trees; 10 replicates) | < 1 MB |
| `37-taxa-weighted-quartets` | 37-taxon mammalian simulated dataset: 240 files (12 conditions × 20 replicates) | 146 MB |
| `48-taxa-weighted-quartets` | 48-taxon avian simulated dataset: the 114 files used in our experiments | 267 MB |
| `48-taxa-weighted-quartets_full_data` | all 140 files of the 48-taxon dataset (7 conditions × 20 replicates) | 327 MB |
| `101-taxa-weighted-quartets` | 101-taxon simulated dataset: 19 replicates, about 12.2 million quartets each | 845 MB |
| `101-taxa-true-species-tree` | true species trees of the 101-taxon replicates | < 1 MB |
| `144-taxa-insect-single-gene` | 144-taxon insect gene tree | < 1 MB |
| `144-taxa-insect-single-gene-weighted-quartets` | weighted quartets of the 144-taxon gene tree | 76 MB |
| `150-taxa-s201-rep01-true-gene-trees` | 150-taxon true gene trees (s201, replicate 1) | < 1 MB |
| `150-taxa-s201-rep01-true-gene-trees-weighted-quartets` | weighted quartets of the 150-taxon gene trees | 192 MB |
| `200-taxa-s200-rep01-true-gene-tree` | 200-taxon true gene tree (s200, replicate 1) | < 1 MB |
| `200-taxa-s200-rep01-true-gene-tree-weighted-quartets` | weighted quartets of the 200-taxon gene tree | 170 MB |
| `biological_dataset_weigted_quartets` | Amniota (AA, NT), angiosperm, avian (all, exon, intron, UCE) and mammalian datasets | 14 MB |
| `gtree_11tax_sim_5gR1`, `15_taxa`, `37_taxa` | one example input file each, for quick tests | < 1 MB |

The simulated and biological datasets come from earlier studies, collected in
the wQFM dataset release (see [QWQFM/README.md](QWQFM/README.md#datasets));
please cite their original publications when you use them.
