package src;

import java.io.IOException;

import src.DSPerLevel.TaxaPerLevelWithPartition;
import src.PreProcessing.GeneTrees;
import src.Taxon.DummyTaxon;
import src.Taxon.RealTaxon;
import src.Tree.Tree;
import src.Tree.TreeNode;

/**
 * wQFM-TREE's divide-and-conquer (QFM2) with the bipartition step replaced by
 * QUANTA's QUBO: no consensus-based initial partition and no FM iterations.
 * Each subproblem's QUBO is built from the gene trees (QuboBuilder) and solved
 * by QUANTA's solvers (QuboSolverProcess); dividing with dummy taxa and
 * merging the two subtrees are unchanged from QFM2.
 */
public class QFMQubo {

    private final RealTaxon[] realTaxa;
    private final GeneTrees geneTrees;
    private final QuboBuilder builder;
    private final QuboSolverProcess solver;
    public double buildSeconds = 0;
    public int subproblems = 0;
    public int maxUnits = 0;

    public QFMQubo(GeneTrees trees, RealTaxon[] realTaxa, QuboBuilder builder, QuboSolverProcess solver) {
        this.geneTrees = trees;
        this.realTaxa = realTaxa;
        this.builder = builder;
        this.solver = solver;
    }

    public Tree run() throws IOException {
        var taxas = new TaxaPerLevelWithPartition(realTaxa, new DummyTaxon[0], new int[realTaxa.length],
                new int[0], realTaxa.length);
        return recurse(taxas);
    }

    private void bipartition(TaxaPerLevelWithPartition taxas) throws IOException {
        double[][] Q = builder.build(taxas);
        buildSeconds += builder.lastBuildNanos / 1e9;
        subproblems++;
        maxUnits = Math.max(maxUnits, Q.length);
        int[] x = solver.solve(Q);
        int R = taxas.realTaxonCount;
        String dump = System.getenv("QUBO_DUMP_DIR");
        if (dump != null) dumpSubproblem(dump, taxas, Q);
        for (int i = 0; i < R; ++i)
            if (taxas.realTaxonPartition[i] != x[i]) taxas.swapPartitionRealTaxon(i);
        for (int d = 0; d < taxas.dummyTaxonCount; ++d)
            if (taxas.dummyTaxonPartition[d] != x[R + d]) taxas.swapPartitionDummyTaxon(d);
    }

    /** For verification: each unit's members with their weights, then Q. */
    private void dumpSubproblem(String dir, TaxaPerLevelWithPartition taxas, double[][] Q) throws IOException {
        StringBuilder sb = new StringBuilder();
        for (var x : taxas.realTaxa) sb.append(x.label).append(':').append(taxas.getWeight(x.id)).append('\n');
        for (var d : taxas.dummyTaxa) {
            for (int j = 0; j < d.flattenedRealTaxa.length; ++j) {
                var x = d.flattenedRealTaxa[j];
                sb.append(j > 0 ? " " : "").append(x.label).append(':').append(taxas.getWeight(x.id));
            }
            sb.append('\n');
        }
        sb.append("Q\n");
        for (double[] row : Q) {
            for (int j = 0; j < row.length; ++j) sb.append(j > 0 ? " " : "").append(row[j]);
            sb.append('\n');
        }
        java.nio.file.Files.writeString(java.nio.file.Path.of(dir, "subproblem_" + subproblems + ".txt"), sb);
    }

    /** BookKeepingPerLevelv2.divide without the initial-partition heuristic. */
    private TaxaPerLevelWithPartition[] divide(TaxaPerLevelWithPartition taxas) {
        RealTaxon[][] rts = new RealTaxon[2][];
        DummyTaxon[][] dts = new DummyTaxon[2][];
        for (int i = 0; i < 2; ++i) {
            rts[i] = new RealTaxon[taxas.getRealTaxonCountInPartition(i)];
            dts[i] = new DummyTaxon[taxas.getDummyTaxonCountInPartition(i)];
        }
        int[] index = new int[2];
        for (var x : taxas.realTaxa) {
            int part = taxas.inWhichPartition(x.id);
            rts[part][index[part]++] = x;
        }
        index[0] = 0;
        index[1] = 0;
        int i = 0;
        for (var x : taxas.dummyTaxa) {
            int part = taxas.inWhichPartitionDummyTaxonByIndex(i++);
            dts[part][index[part]++] = x;
        }
        TaxaPerLevelWithPartition[] result = new TaxaPerLevelWithPartition[2];
        for (i = 0; i < 2; ++i) {
            DummyTaxon newDt = new DummyTaxon(rts[1 - i], dts[1 - i]);
            DummyTaxon[] withNew = new DummyTaxon[dts[i].length + 1];
            System.arraycopy(dts[i], 0, withNew, 0, dts[i].length);
            withNew[withNew.length - 1] = newDt;
            boolean small = rts[i].length + withNew.length <= 3;
            result[i] = new TaxaPerLevelWithPartition(rts[i], withNew,
                    small ? null : new int[rts[i].length], small ? null : new int[withNew.length],
                    geneTrees.realTaxaCount);
        }
        return result;
    }

    /** QFM2.recurse with the QUBO bipartition in place of FM. */
    private Tree recurse(TaxaPerLevelWithPartition taxas) throws IOException {
        bipartition(taxas);
        Tree[] trees = new Tree[2];
        int[] dummyIds = new int[2];
        var parts = divide(taxas);
        for (int i = 0; i < 2; ++i) {
            var part = parts[i];
            trees[i] = part.smallestUnit ? part.createStar() : recurse(part);
            dummyIds[i] = part.dummyTaxa[part.dummyTaxonCount - 1].id;
        }

        TreeNode[] dtNodes = new TreeNode[2];
        for (int i = 0; i < 2; ++i) {
            for (var node : trees[i].nodes)
                if (node.info.dummyTaxonId == dummyIds[i]) dtNodes[i] = node;
            if (dtNodes[i] == null || dtNodes[i].childs != null)
                throw new IllegalStateException("dummy node missing or not a leaf");
        }
        trees[0].reRootTree(dtNodes[0]);
        if (dtNodes[0].childs.size() > 1)
            throw new IllegalStateException("dummy node should have one child after reroot");
        dtNodes[0].childs.get(0).setParent(dtNodes[1].parent);
        dtNodes[1].parent.childs.remove(dtNodes[1]);
        dtNodes[1].parent.childs.add(dtNodes[0].childs.get(0));
        trees[1].nodes.addAll(trees[0].nodes);
        return trees[1];
    }
}
