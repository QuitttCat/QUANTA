# QWQFM D-Wave QPU inspection

- Input: `1X-50-500_R9_weighted_quartets`
- Selection: largest quantum RF advantage found across RF benchmark CSVs
- WQFM normalized RF: `0.288888888889`
- Quantum normalized RF: `0.222222222222`
- Quantum match advantage: `6.666667` percentage points
- QUBO: `A=1`, `B=0.4`, `48` variables
- QPU solver: `Advantage_system4`
- Problem ID: `8aa3dfd5-24b8-47cc-a07f-6907f07c6b3e`
- Reads: `1000`
- Selected valid sample energy rank: `1`
- Partition sizes: `29 & 19`
- Logical variables embedded: `48`
- Physical qubits used: `296`
- Chain length range: `4–8`
- Reads with chain breaks: `1/1000`
- Unique returned samples: `3`
- Inspector URL: `http://127.0.0.1:18000/?problemId=8aa3dfd5-24b8-47cc-a07f-6907f07c6b3e`

The URL is served from the remote host. Forward its port through VS Code or SSH
while the `qwqfm-qpu-inspection.service` service is active.

Saved machine-readable artifacts include the full Inspector problem and solver
payloads, QUBO matrix, embedding context, returned samples, selected partition,
QPU timing, and the benchmark CSV evidence.
