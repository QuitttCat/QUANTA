#!/bin/bash
# Usage: ./run_all.sh <target_dir> [input_mode]
#   target_dir  : subdirectory inside input_files/ (e.g. 11-taxa-weighted-quartets)
#   input_mode  : wqrts (default) | gene_trees
#
# Example:
#   ./run_all.sh 11-taxa-weighted-quartets
#   ./run_all.sh my_gene_tree_dir gene_trees

TARGET_DIR="${1:?Error: provide target_dir. Usage: $0 <target_dir> [input_mode]}"
INPUT_MODE="${2:-wqrts}"

INPUT_DIR="input_files/${TARGET_DIR}"
CSV_OUTPUT="results_${TARGET_DIR}.csv"
JAR="dist/wQFM.jar"

# ── Validate ────────────────────────────────────────────────────────────────
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: directory '$INPUT_DIR' not found."
    exit 1
fi

# ── Build once ───────────────────────────────────────────────────────────────
echo "Building wQFM..."
ant clean && ant jar
if [ $? -ne 0 ]; then
    echo "Build failed. Aborting."
    exit 1
fi
echo "Build successful."
echo ""

# ── CSV header ───────────────────────────────────────────────────────────────
echo "file_name,algo1_wqfm_tree,algo2_qubo_tree" > "$CSV_OUTPUT"

# ── Run loop ─────────────────────────────────────────────────────────────────
TOTAL=$(ls -1 "$INPUT_DIR" | wc -l)
COUNT=0

for INPUT_FILE in "$INPUT_DIR"/*; do
    [ -f "$INPUT_FILE" ] || continue       # skip subdirectories

    FNAME=$(basename "$INPUT_FILE")
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL] Processing: $FNAME"

    TMP1=$(mktemp /tmp/wqfm_algo1_XXXXX.tre)
    TMP2=$(mktemp /tmp/wqfm_algo2_XXXXX.tre)

    FILE_START=$SECONDS

    # algo 1 — run_FM_Algorithm_Whole
    T1_START=$SECONDS
    java -Xmx8g -cp "${JAR}:lib/*" wqfm.main.Main \
        -i "$INPUT_FILE" -im "$INPUT_MODE" -o "$TMP1" -algo 1 \
        > /dev/null 2>&1
    T1_ELAPSED=$((SECONDS - T1_START))
    TREE1=$(tr -d '\n\r' < "$TMP1" 2>/dev/null)

    # algo 2 — run_FM_Algorithm_Whole2 (QUBO)
    T2_START=$SECONDS
    java -Xmx8g -cp "${JAR}:lib/*" wqfm.main.Main \
        -i "$INPUT_FILE" -im "$INPUT_MODE" -o "$TMP2" -algo 2 \
        > /dev/null 2>&1
    T2_ELAPSED=$((SECONDS - T2_START))
    TREE2=$(tr -d '\n\r' < "$TMP2" 2>/dev/null)

    FILE_ELAPSED=$((SECONDS - FILE_START))

    # Write CSV row (fields quoted to handle commas inside Newick trees)
    printf '"%s","%s","%s"\n' "$FNAME" "$TREE1" "$TREE2" >> "$CSV_OUTPUT"

    rm -f "$TMP1" "$TMP2"
    echo "  algo1: ${T1_ELAPSED}s | algo2: ${T2_ELAPSED}s | total: ${FILE_ELAPSED}s"
    echo "  Done."
done

echo ""
echo "Finished. Results saved to: $CSV_OUTPUT"
