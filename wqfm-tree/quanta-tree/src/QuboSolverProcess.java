package src;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;

/**
 * Persistent Python process running QUANTA's bipartition solvers
 * (qubo_solver.py: exhaustive search for at most 20 units, simulated annealing
 * above). Protocol: "QUBO M" then M lines, row i holding Q[i][i..M-1]; the
 * reply is "SOLUTION <bits> <solver seconds>". The solver's log goes to the
 * file in QUBO_SOLVER_LOG.
 */
public class QuboSolverProcess {

    private final Process process;
    private final BufferedWriter in;
    private final BufferedReader out;
    public double solverSeconds = 0;
    public int calls = 0;

    public QuboSolverProcess() throws IOException {
        String python = System.getenv().getOrDefault("QUBO_SOLVER_PYTHON", "python3");
        String script = System.getenv("QUBO_SOLVER_SCRIPT");
        if (script == null) throw new IllegalStateException("Set QUBO_SOLVER_SCRIPT to qubo_solver.py");
        String log = System.getenv().getOrDefault("QUBO_SOLVER_LOG", "qubo_solver.log");
        ProcessBuilder pb = new ProcessBuilder(python, script);
        pb.redirectError(ProcessBuilder.Redirect.appendTo(new File(log)));
        process = pb.start();
        in = new BufferedWriter(new OutputStreamWriter(process.getOutputStream()), 1 << 20);
        out = new BufferedReader(new InputStreamReader(process.getInputStream()));
    }

    public int[] solve(double[][] Q) throws IOException {
        int M = Q.length;
        StringBuilder sb = new StringBuilder();
        in.write("QUBO " + M + "\n");
        for (int i = 0; i < M; ++i) {
            sb.setLength(0);
            for (int j = i; j < M; ++j) {
                if (j > i) sb.append(' ');
                sb.append(Q[i][j]);
            }
            sb.append('\n');
            in.write(sb.toString());
        }
        in.flush();
        String line;
        while ((line = out.readLine()) != null) {
            if (!line.startsWith("SOLUTION ")) continue;
            String[] parts = line.split(" ");
            int[] x = new int[M];
            for (int i = 0; i < M; ++i) x[i] = parts[1].charAt(i) - '0';
            solverSeconds += Double.parseDouble(parts[2]);
            calls++;
            return x;
        }
        throw new IOException("QUBO solver exited; see its log");
    }

    public void close() throws IOException {
        in.close();
        try {
            process.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
