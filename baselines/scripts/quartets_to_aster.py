#!/usr/bin/env python3
"""Convert a weighted-quartet file into ASTER (wASTRAL) input.

Each input line ``((a,b),(c,d)); w`` becomes one four-taxon tree
``((a,b),(c,d));`` in TREES_OUT and its weight ``w`` on the same line of
WEIGHTS_OUT. Running ``wastral --mode 4 --treeweights WEIGHTS_OUT TREES_OUT``
then maximizes exactly the weighted quartet score: with --mode 4 every
quartet of a tree counts once, scaled linearly by that tree's weight.

Usage: quartets_to_aster.py QUARTET_FILE TREES_OUT WEIGHTS_OUT
"""

import sys


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    source, trees_path, weights_path = sys.argv[1:]
    count = 0
    with open(source) as quartets, open(trees_path, "w") as trees, open(weights_path, "w") as weights:
        for line_number, line in enumerate(quartets, start=1):
            line = line.strip()
            if not line:
                continue
            end = line.rfind(";")
            if not line.startswith("((") or end < 0:
                sys.exit(f"invalid quartet on line {line_number}: {line!r}")
            weight = line[end + 1:].strip()
            float(weight)  # fail early on a malformed weight
            trees.write(line[:end + 1] + "\n")
            weights.write(weight + "\n")
            count += 1
    print(f"converted {count} quartets")


if __name__ == "__main__":
    main()
