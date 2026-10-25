#!/usr/bin/env python3
"""
Draw unrooted phylogenetic tree from Newick format.
Usage: python draw_tree.py "<newick_string>" [output_file]
       python draw_tree.py --file <tree_file> [output_file]
"""

import sys
import os
import tempfile

try:
    from Bio import Phylo
    import matplotlib.pyplot as plt
except ImportError:
    print("Installing required packages...")
    os.system("pip install biopython matplotlib")
    from Bio import Phylo
    import matplotlib.pyplot as plt

def draw_unrooted_tree(tree_string, output_file=None):
    """Draw an unrooted phylogenetic tree from a Newick string."""
    
    # Write string to temp file for Biopython
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tre', delete=False) as f:
        f.write(tree_string.strip())
        temp_file = f.name
    
    try:
        tree = Phylo.read(temp_file, "newick")
    finally:
        os.unlink(temp_file)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 14))
    
    # Draw tree
    Phylo.draw(tree, axes=ax, do_show=False)
    
    ax.set_title("Phylogenetic Tree", fontsize=14)
    
    # Save
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Tree saved to: {output_file}")
    
    plt.close()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_png = os.path.join(script_dir, "tree_output.png")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--file":
            # Read from file
            tree_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(script_dir, "quantum_output.tre")
            with open(tree_file, 'r') as f:
                tree_string = f.read().strip()
            if len(sys.argv) > 3:
                output_png = sys.argv[3]
        else:
            # Direct string input
            tree_string = sys.argv[1]
            if len(sys.argv) > 2:
                output_png = sys.argv[2]
    else:
        # Default: read from quantum_output.tre
        tree_file = os.path.join(script_dir, "quantum_output.tre")
        with open(tree_file, 'r') as f:
            tree_string = f.read().strip()
    
    draw_unrooted_tree(tree_string, output_png)

