# V1 namespace compatibility — 2026-10-06

Task 5 COMPLETE under the designer's 2026-10-06 compatibility ruling. V1 remains incomplete; this is neither live Gala evidence nor external audit closure.

The eleven V1 live-chain Python files moved from `runtime_trace/live_chain/` to `verified_driver/v1/live_chain/`. Changes are restricted to V1 imports, GDB/harness paths, worker module path, executable root depth, and the two V1 source enumeration locations. No V0 gate, approved pinset, V0 source byte, old Runtime Trace contract, or numerical verification criterion changed.

Ordered results on a source-identical native mirror of the combined V0+V1 product:

| Check | Result | Job |
|---|---|---|
| Previously failed V0 cases | 10 PASS | compat-failed10-final |
| Entire designated V0 regression | 83 PASS | compat-v0-final |
| V1 Tasks 1–5 regression | 100 PASS | compat-v1 |
| Runtime Trace acquisition/pipeline/raw/resources/public | 40 PASS | compat-runtime |
| Exact previous combined regression set | 183 PASS / 0 FAIL | compat-combined |

Source copying completed before the `-final` ordered runs. The earlier two exploratory runs during mirror synchronization are retained and charged; they are not used as the final evidence. `combined-source-mirror.json` binds all 179 copied Python files. Each job has execution, resource, storage, command and stdout evidence; JUnit files are adjacent to this report.

Protected baseline rehash: 7,232 files, zero changes (`../preservation/namespace-compatibility-final.json`). V1 pre-compatibility history: 152 files, zero changes (`verification.json` / `historical-before.json`). Both original mutable budget files remain explicitly excluded from the immutable inventory.

The combined runtime trust universe equals the original approved 89-file map byte-for-byte; approved pinset SHA-256 remains `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`. All eleven relocated files occur in the new 37-file V1 source snapshot (`v1-source-pinset.json`). The old namespace has no Python source files.

All Task 1–5 RED/GREEN/failure/conflict evidence and the Task 4 TEST_ONLY N=3 fixture remain pre-compatibility historical evidence. `pre-compatibility-source/` and `pre-compatibility-status.md` preserve the preceding source/status context. No result here is retroactively assigned to those executions.

Shared guarded time: before 3113.881535818022 s, after 3230.3961637530215 s, increment 116.5146279349995 s, remainder 369.6038362469785 s. Same 3600 s ledger; no reset, new ledger or increased ceiling. Development, metadata copying and read-only hashing are not counted as guarded execution time, consistently with the existing ledger. No new Gala acquisition ran.

`git diff --check`: exit 0. `git-status.txt` submits the worktree status; index remains empty. No staging, commit or push.
