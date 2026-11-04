package src;

import java.util.ArrayList;
import java.util.IdentityHashMap;

import src.DSPerLevel.TaxaPerLevelWithPartition;
import src.PreProcessing.GeneTrees;
import src.Tree.Tree;
import src.Tree.TreeNode;

/**
 * QUANTA's bipartition QUBO for one wQFM-TREE subproblem, built directly from
 * the gene trees.
 *
 * Units are the subproblem's real taxa followed by its dummy taxa. A quartet
 * of real taxa counts only if its four taxa lie in four different units; its
 * weight is the product of wQFM-TREE's taxon weights (1 for a real taxon of
 * the subproblem, nested normalisation for taxa under a dummy, so every unit
 * weighs 1). With pair[U][V] and cross[U][V] the weighted counts of quartets
 * in which U and V are siblings or on opposite sides, QUANTA's QUBO is
 *   Q[U][U] = (A - 2B) omega_U,  Q[U][V] = -2A pair[U][V] + 2B cross[U][V],
 * the same coefficients qaoa.StreamingQuboAccumulator adds per quartet.
 *
 * Per gene tree (on all taxa): subtrees whose leaves all belong to one unit are
 * folded into one leaf of their summed weight (a counted quartet uses at most
 * one taxon per unit, so this is exact). In an unrooted tree ab|cd holds iff c
 * and d lie in the same subtree hanging off one interior vertex v of the a-b
 * path; for the hanging subtree H the weight of valid {c,d} is
 *   F(H) - g(H,ua) - g(H,ub) + W_ua(H) W_ub(H),
 *   F(H) = (W(H)^2 - sum_U W_U(H)^2) / 2,  g(H,U) = W_U(H) (W(H) - W_U(H)),
 * where only dummy units can have W_U(H) > 0. These are summed along each
 * path with prefix sums from the root, so each pair of leaves is visited once,
 * at its lowest common ancestor. Since every unit weighs 1, a binary tree gives
 * pair + cross = C(M-2, 2) for every unit pair and omega_U = C(M-1, 3).
 *
 * A polytomy leaves some quartets unresolved, and those count for nothing, as
 * in QUANTA's quartet input: {a,b,c,d} is unresolved iff c and d lie in
 * different subtrees hanging off one vertex of the a-b path. With X the union
 * of the subtrees hanging off that vertex, their weight is term(X) - sum_H
 * term(H), for the same term as above. So pair + cross = C(M-2, 2) - unresolved
 * and omega_U = C(M-1, 3) - sum_V unresolved[U][V] / 3.
 */
public class QuboBuilder {

    static final class CompactTree {
        int[] parent;      // -1 for the root
        int[][] children;  // empty for leaves
        int[] taxon;       // real taxon id for leaves, -1 otherwise
        int[] post;        // postorder
        int root;
    }

    private final CompactTree[] trees;
    private final int taxaCount;
    private final double A, B;

    public QuboBuilder(GeneTrees geneTrees, double A, double B) {
        this.A = A;
        this.B = B;
        this.taxaCount = geneTrees.realTaxaCount;
        this.trees = new CompactTree[geneTrees.geneTrees.size()];
        for (int i = 0; i < trees.length; ++i) {
            trees[i] = compact(geneTrees.geneTrees.get(i));
        }
    }

    private CompactTree compact(Tree tree) {
        ArrayList<TreeNode> order = new ArrayList<>();
        IdentityHashMap<TreeNode, Integer> position = new IdentityHashMap<>();
        ArrayList<TreeNode> stack = new ArrayList<>();
        stack.add(tree.root);
        while (!stack.isEmpty()) {  // preorder
            TreeNode node = stack.remove(stack.size() - 1);
            position.put(node, order.size());
            order.add(node);
            if (!node.isLeaf()) stack.addAll(node.childs);
        }
        CompactTree t = new CompactTree();
        int n = order.size();
        t.parent = new int[n];
        t.children = new int[n][];
        t.taxon = new int[n];
        t.post = new int[n];
        int leaves = 0;
        for (int i = 0; i < n; ++i) {
            TreeNode node = order.get(i);
            t.parent[i] = node == tree.root ? -1 : position.get(node.parent);
            if (node.isLeaf()) {
                t.children[i] = new int[0];
                t.taxon[i] = node.taxon.id;
                leaves++;
            } else {
                t.children[i] = new int[node.childs.size()];
                for (int c = 0; c < node.childs.size(); ++c) t.children[i][c] = position.get(node.childs.get(c));
                t.taxon[i] = -1;
            }
            t.post[n - 1 - i] = i;  // reverse preorder visits children before parents
        }
        if (leaves != taxaCount)
            throw new IllegalStateException("QUBO mode needs every gene tree to contain every taxon");
        t.root = 0;
        return t;
    }

    public long lastBuildNanos;

    /** Upper-triangular Q over the subproblem's units (real taxa, then dummy taxa). */
    public double[][] build(TaxaPerLevelWithPartition taxas) {
        long start = System.nanoTime();
        int R = taxas.realTaxonCount, q = taxas.dummyTaxonCount, M = R + q;
        int[] unitOf = new int[taxaCount];
        double[] weight = new double[taxaCount];
        for (int id = 0; id < taxaCount; ++id) {
            if (taxas.isInRealTaxa(id)) unitOf[id] = taxas.getRealTaxonIndex(id);
            else if (taxas.isInDummyTaxa(id)) unitOf[id] = R + taxas.inWhichDummyTaxa(id);
            else throw new IllegalStateException("taxon " + id + " is in no unit");
            weight[id] = taxas.getWeight(id);
        }
        double[][] pair = new double[M][M];
        double[][] unresolved = new double[M][M];
        for (CompactTree t : trees) accumulate(t, unitOf, weight, R, q, pair, unresolved);

        double k = trees.length;
        double omega = k * (M - 1.0) * (M - 2.0) * (M - 3.0) / 6.0;
        double resolved = k * (M - 2.0) * (M - 3.0) / 2.0;
        double[] lostOmega = new double[M];
        for (int u = 0; u < M; ++u)
            for (int v = u + 1; v < M; ++v) {
                double x = unresolved[u][v] + unresolved[v][u];
                lostOmega[u] += x / 3.0;
                lostOmega[v] += x / 3.0;
            }
        double[][] Q = new double[M][M];
        for (int u = 0; u < M; ++u) {
            Q[u][u] = (A - 2 * B) * (omega - lostOmega[u]);
            for (int v = u + 1; v < M; ++v) {
                double p = pair[u][v] + pair[v][u];
                double x = unresolved[u][v] + unresolved[v][u];
                Q[u][v] = -2 * A * p + 2 * B * (resolved - x - p);
            }
        }
        lastBuildNanos = System.nanoTime() - start;
        return Q;
    }

    private void accumulate(CompactTree t, int[] unitOf, double[] weight, int R, int q, double[][] pair,
                            double[][] unresolved) {
        int n = t.parent.length;
        // 1. unit of each subtree if pure (-1 if mixed), and its summed weight
        int[] pure = new int[n];
        double[] sumW = new double[n];
        for (int v : t.post) {
            if (t.children[v].length == 0) {
                pure[v] = unitOf[t.taxon[v]];
                sumW[v] = weight[t.taxon[v]];
            } else {
                int u = pure[t.children[v][0]];
                double s = 0;
                for (int c : t.children[v]) {
                    if (pure[c] != u) u = -1;
                    s += sumW[c];
                }
                pure[v] = u;
                sumW[v] = s;
            }
        }
        // 2. compressed tree: mixed nodes, with pure subtrees folded into leaves
        int[] map = new int[n];
        int m = 0;
        int[] cNode = new int[n];
        int[] stack = new int[n];
        int sp = 0;
        stack[sp++] = t.root;
        while (sp > 0) {  // preorder over kept nodes
            int v = stack[--sp];
            map[v] = m;
            cNode[m++] = v;
            if (pure[v] < 0) for (int c : t.children[v]) stack[sp++] = c;
        }
        int[] cParent = new int[m];
        int[][] cChildren = new int[m][];
        int[] cUnit = new int[m];
        double[] cWeight = new double[m];
        for (int i = 0; i < m; ++i) {
            int v = cNode[i];
            cParent[i] = v == t.root ? -1 : map[t.parent[v]];
            if (pure[v] >= 0) {
                cChildren[i] = new int[0];
                cUnit[i] = pure[v];
                cWeight[i] = sumW[v];
            } else {
                cChildren[i] = new int[t.children[v].length];
                for (int c = 0; c < t.children[v].length; ++c) cChildren[i][c] = map[t.children[v][c]];
                cUnit[i] = -1;
            }
        }
        // 3. subtree totals (reverse preorder = postorder), leaf ranges in DFS order
        double[] W = new double[m];
        double[] singles = new double[m];
        double[][] WD = new double[m][q];
        int[] lo = new int[m], hi = new int[m];
        int[] leafOrder = new int[m];
        int leafCount = 0;
        // leaf order: preorder index order restricted to leaves is a valid DFS order
        for (int i = 0; i < m; ++i) if (cChildren[i].length == 0) leafOrder[leafCount++] = i;
        int[] leafPos = new int[m];
        for (int p = 0; p < leafCount; ++p) leafPos[leafOrder[p]] = p;
        for (int i = m - 1; i >= 0; --i) {
            if (cChildren[i].length == 0) {
                W[i] = cWeight[i];
                if (cUnit[i] < R) singles[i] = 1;
                else WD[i][cUnit[i] - R] = cWeight[i];
                lo[i] = leafPos[i];
                hi[i] = leafPos[i] + 1;
            } else {
                lo[i] = Integer.MAX_VALUE;
                hi[i] = -1;
                for (int c : cChildren[i]) {
                    W[i] += W[c];
                    singles[i] += singles[c];
                    for (int d = 0; d < q; ++d) WD[i][d] += WD[c][d];
                    lo[i] = Math.min(lo[i], lo[c]);
                    hi[i] = Math.max(hi[i], hi[c]);
                }
            }
        }
        // preorder of a stack-based DFS keeps every subtree's leaves contiguous
        // 4. per node: its own hanging-subtree terms, and their sums over its children, so that
        //    "all children but one or two" costs O(1) at a polytomy
        int qq = q * (q - 1) / 2;
        int[][] tri = new int[q][q];
        for (int d1 = 0, idx = 0; d1 < q; ++d1)
            for (int d2 = d1 + 1; d2 < q; ++d2) { tri[d1][d2] = idx; tri[d2][d1] = idx; idx++; }
        boolean polytomy = false;  // can a vertex hang several subtrees off a path?
        double[] nodeF = new double[m];
        double[] sumF = new double[m];
        double[][] sumG = new double[m][q];
        double[][] sumP = new double[m][qq];
        for (int i = m - 1; i >= 0; --i) {
            nodeF[i] = F(W[i], singles[i], WD[i]);
            if (cChildren[i].length > (cParent[i] < 0 ? 3 : 2)) polytomy = true;
            for (int c : cChildren[i]) {
                sumF[i] += nodeF[c];
                for (int d = 0; d < q; ++d) sumG[i][d] += WD[c][d] * (W[c] - WD[c][d]);
                for (int d1 = 0; d1 < q; ++d1)
                    for (int d2 = d1 + 1; d2 < q; ++d2) sumP[i][tri[d1][d2]] += WD[c][d1] * WD[c][d2];
            }
        }
        // 5. prefix sums from the root of the hanging-subtree terms; upX* are the same for the
        //    unresolved quartets, term(X) - sum_H term(H), zero at a degree-3 vertex
        double[] upF = new double[m];
        double[][] upG = new double[m][q];
        double[][] upP = new double[m][qq];
        double[] upXF = polytomy ? new double[m] : null;
        double[][] upXG = polytomy ? new double[m][q] : null;
        double[][] upXP = polytomy ? new double[m][qq] : null;
        double[] xWD = new double[q];
        for (int i = 0; i < m; ++i) {  // preorder: parent before child
            int u = cParent[i];
            if (u < 0) continue;
            if (cParent[u] < 0) continue;  // the root is never passed through below an LCA
            double hangF = sumF[u] - nodeF[i];
            upF[i] = upF[u] + hangF;
            for (int d = 0; d < q; ++d) upG[i][d] = upG[u][d] + sumG[u][d] - WD[i][d] * (W[i] - WD[i][d]);
            for (int d1 = 0; d1 < q; ++d1)
                for (int d2 = d1 + 1; d2 < q; ++d2) {
                    int x = tri[d1][d2];
                    upP[i][x] = upP[u][x] + sumP[u][x] - WD[i][d1] * WD[i][d2];
                }
            if (!polytomy) continue;
            upXF[i] = upXF[u];
            System.arraycopy(upXG[u], 0, upXG[i], 0, q);
            System.arraycopy(upXP[u], 0, upXP[i], 0, qq);
            if (cChildren[u].length <= 2) continue;
            double xW = W[u] - W[i];
            for (int d = 0; d < q; ++d) xWD[d] = WD[u][d] - WD[i][d];
            upXF[i] += F(xW, singles[u] - singles[i], xWD) - hangF;
            for (int d = 0; d < q; ++d)
                upXG[i][d] += xWD[d] * (xW - xWD[d]) - (sumG[u][d] - WD[i][d] * (W[i] - WD[i][d]));
            for (int d1 = 0; d1 < q; ++d1)
                for (int d2 = d1 + 1; d2 < q; ++d2) {
                    int x = tri[d1][d2];
                    upXP[i][x] += xWD[d1] * xWD[d2] - (sumP[u][x] - WD[i][d1] * WD[i][d2]);
                }
        }
        // 6. every pair of folded leaves at its LCA
        double totalW = W[0], totalSingles = singles[0];
        double[] outWD = new double[q];
        double[] outG = new double[q];
        double[] outP = new double[qq];
        for (int L = 0; L < m; ++L) {
            int[] ch = cChildren[L];
            if (ch.length == 0) continue;
            // the subtrees hanging off L on a path between two of its children: its other
            // children and, unless L is the root, everything outside L
            boolean hasOutside = cParent[L] >= 0;
            double outF = 0;
            if (hasOutside) {
                double ow = totalW - W[L], os = totalSingles - singles[L];
                for (int d = 0; d < q; ++d) outWD[d] = 1.0 - WD[L][d];
                outF = F(ow, os, outWD);
                for (int d = 0; d < q; ++d) outG[d] = outWD[d] * (ow - outWD[d]);
                for (int d1 = 0; d1 < q; ++d1)
                    for (int d2 = d1 + 1; d2 < q; ++d2) outP[tri[d1][d2]] = outWD[d1] * outWD[d2];
            } else {
                java.util.Arrays.fill(outG, 0);
                java.util.Arrays.fill(outP, 0);
            }
            boolean others = ch.length > 2;
            boolean several = polytomy && ch.length - 2 + (hasOutside ? 1 : 0) >= 2;
            for (int i = 0; i < ch.length; ++i) {
                for (int j = i + 1; j < ch.length; ++j) {
                    int ci = ch[i], cj = ch[j];
                    double HF = outF + (others ? sumF[L] - nodeF[ci] - nodeF[cj] : 0);
                    // X, the union of the hanging subtrees (only needed if there are several)
                    double xW = 0, XF = 0;
                    if (several) {
                        xW = totalW - W[ci] - W[cj];
                        for (int d = 0; d < q; ++d) xWD[d] = 1.0 - WD[ci][d] - WD[cj][d];
                        XF = F(xW, totalSingles - singles[ci] - singles[cj], xWD) - HF;
                    }
                    for (int pa = lo[ci]; pa < hi[ci]; ++pa) {
                        int a = leafOrder[pa], ua = cUnit[a], da = ua - R;
                        double wa = cWeight[a];
                        double baseA = upF[a] - upF[ci] + HF - upF[cj];
                        double hgA = 0, xgA = 0;
                        if (da >= 0) {
                            hgA = outG[da] + (others ? sumG[L][da] - WD[ci][da] * (W[ci] - WD[ci][da])
                                    - WD[cj][da] * (W[cj] - WD[cj][da]) : 0);
                            if (several) xgA = xWD[da] * (xW - xWD[da]) - hgA;
                        }
                        double[] pairRow = pair[ua];
                        double[] unresolvedRow = unresolved[ua];
                        for (int pb = lo[cj]; pb < hi[cj]; ++pb) {
                            int b = leafOrder[pb], ub = cUnit[b];
                            if (ua == ub) continue;
                            double val = baseA + upF[b];
                            int db = ub - R;
                            double hgB = 0, xgB = 0;
                            if (db >= 0) {
                                hgB = outG[db] + (others ? sumG[L][db] - WD[ci][db] * (W[ci] - WD[ci][db])
                                        - WD[cj][db] * (W[cj] - WD[cj][db]) : 0);
                                if (several) xgB = xWD[db] * (xW - xWD[db]) - hgB;
                            }
                            if (da >= 0)
                                val -= upG[a][da] - upG[ci][da] + upG[b][da] - upG[cj][da] + hgA;
                            if (db >= 0)
                                val -= upG[a][db] - upG[ci][db] + upG[b][db] - upG[cj][db] + hgB;
                            double hp = 0;
                            if (da >= 0 && db >= 0) {
                                int x = tri[da][db];
                                hp = outP[x] + (others ? sumP[L][x] - WD[ci][da] * WD[ci][db] - WD[cj][da] * WD[cj][db] : 0);
                                val += upP[a][x] - upP[ci][x] + upP[b][x] - upP[cj][x] + hp;
                            }
                            pairRow[ub] += wa * cWeight[b] * val;
                            if (polytomy) {
                                double u = upXF[a] - upXF[ci] + XF + upXF[b] - upXF[cj];
                                if (da >= 0)
                                    u -= upXG[a][da] - upXG[ci][da] + upXG[b][da] - upXG[cj][da] + xgA;
                                if (db >= 0)
                                    u -= upXG[a][db] - upXG[ci][db] + upXG[b][db] - upXG[cj][db] + xgB;
                                if (da >= 0 && db >= 0) {
                                    int x = tri[da][db];
                                    u += upXP[a][x] - upXP[ci][x] + upXP[b][x] - upXP[cj][x]
                                            + (several ? xWD[da] * xWD[db] - hp : 0);
                                }
                                unresolvedRow[ub] += wa * cWeight[b] * u;
                            }
                        }
                    }
                }
            }
        }
    }

    /** Weight of pairs of distinct units inside a subtree: (W^2 - sum_U W_U^2) / 2. */
    private static double F(double w, double singles, double[] wd) {
        double s2 = singles;
        for (double x : wd) s2 += x * x;
        return (w * w - s2) / 2.0;
    }
}
