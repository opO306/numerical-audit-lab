# Task 2 report: independent caller transition / error-continuity checker

Date: 2026-10-03

Branch: `caller-error-continuity-regular-1step`

Starting commit: `e8bad02ac990ae7ff888296f5f7c5204a5ed98a3`

Task result: **DONE** for the Task 2 checker, its dedicated tests, and its saved
evidence. Repository-wide integration tests and the final 805+27 preservation
check remain explicitly assigned to the root integrator.

## Result and claim boundary

The independent checker accepts both allowed producer outputs and derives the
same corridor measurements from the raw acquisitions without importing the
producer, acquisition write decoder, module resolver, legacy V2 checker or
adapter, or production Form evaluator.

| Accepted case | PID | capture SHA-256 | trace SHA-256 | producer transition SHA-256 | records / decoded | possible writes | same-value writes | carry lanes | gradient coverage | second-body instructions |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| `attempt-05` | 403 | `3b8287a197513975ffab3037ac1056d902ba0ddff18435783d638bc5073cbcb7` | `7c6ee3ccdc6d269bee21a108faa70ab8674f3ff55823bb16560a1bd97e187f06` | `460001cb5c13c8060dc7c6c63ae3351ee92f7ad72b84f37f34068f8c067c3479` | 728 / 728 | 108 | 20 | 6 | 16 bytes | 0 |
| `closure-fresh-01` | 458 | `88e5c9822b0b5f3388a53124e80e9b0a5d5b3b88bf46effa7d48df50c030a886` | `1a5ae81a9862380caf66445726271cec39ce9648f20a731a13b99a08a2cbef2c` | `3873fdfd00a07c783fbe872eafd1ef414d775668bd32976926695ffeca706499` | 728 / 728 | 108 | 20 | 6 | 16 bytes | 0 |

The two acquisitions have different capture/trace hashes and PIDs. They are
same-machine, separate-process evidence only. The checker establishes a
prospective second-step input at the second native entry; it does not execute
the second body. Native execution contains no Form objects. All Form claims are
conditional on the byte-pinned, previously external-audited antecedent
semantics. This Task 2 checker did not perform a new external audit.

## Independent algorithm

`runtime_trace/caller_transition/checker.py` uses the Python standard library
and an external GNU `objdump` only.

1. It rejects duplicate JSON keys, unsupported schemas, unsupported antecedent
   identities, path escapes, hash mismatches, and widened scope claims.
2. Its own ELF64 little-endian parser reads program headers and `PT_LOAD`
   segments, maps every recorded PC to one of the three pinned module files,
   recomputes load base, ELF virtual address, file offset, and instruction
   bytes, and checks complete module SHA-256 values.
3. It invokes GNU `objdump` on the pinned bytes and independently matches all
   728 decoded instructions. It checks dense sequence numbers, the SHA-256 row
   chain, pre/post state continuity, thread/all-stop receipts, and first-return
   through final-call control flow including PC and stack effects.
4. It independently derives explicit and implicit x86-64 memory writes from
   the decoded instruction and pre/post register state. The implemented forms
   cover every instruction in this corridor, including calls, pushes/pops,
   read/modify/write instructions, `cmpxchg`, `xchg`, scalar stores, and the
   16-byte vector stores. A decoded memory-destination form outside the closed
   implementation is `REFUSED`; it is never treated as a no-write instruction.
5. It checks the actual System V call boundary: the initial return, final call,
   target native entry, `rdi/rsi/rdx`, `xmm0/xmm1`, `rcx/r8/r9`, the pushed
   gradient pointer, and the controlled stop before any second-body instruction.
6. It traverses the frozen numeric IR and correspondence files as data. For
   each of `q[0]`, `q[1]`, `full_v[0]`, `full_v[1]`, `latent[0]`, and
   `latent[1]`, it derives the latest storage-terminal `COPY_BITS`, its explicit
   source, and either the direct state binding or the Form-bearing COPY
   ancestor. This specifically permits the accepted full-v/latent terminal
   values whose Form binding is on the source ancestor, while still enforcing
   exact storage state/value IDs, source IDs, center bits, Form, and namespace.
7. It derives no-overlap carry regions, pointer identity, all gradient writes,
   complete 16-byte exact-zero coverage including the protected same-value
   store, old-gradient before bits, fresh exact-zero roots, the two scalar load
   roots for `t` and `dt`, schedule index 2, scratch roots, write-set receipts,
   and the absence of a second imported/executed V2 block.

The checker hashes acquisition source files named by `execution.json`, but it
does not import or parse their proof logic. In particular,
`write_effects.py` and `module_resolver.py` are only byte-hash-bound source
receipts.

## Read inputs

The implementation work fully read these binding/interface documents:

- `.superpowers/sdd/caller-plan/task-2-brief.md`
- `D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/user-caller-scope.md`
- `.superpowers/sdd/caller-plan/task-1-report.md`
- `.superpowers/sdd/caller-plan/task-1-fix-round1-review.md`
- `runtime_trace/caller_transition/CONTINUITY_CONTRACT.md`
- `runtime_trace/caller_transition/SOURCE_PATH.md`
- `runtime_trace/numeric_ir/CONTRACT.md`
- `runtime_trace/numeric_ir/v2/CONTRACT.md`

The checker read the following accepted inputs for each of
`audited-attempt-05` and `fresh-closure-fresh-01`:

- raw `capture.json`, `caller_trace.jsonl`, `execution.json`, and
  `harness_diff.json` under `runtime_trace/caller_transition/artifacts/<case>/`;
- only the accepted `transition.json` under
  `runtime_trace/caller_transition/artifacts/producer-fix-round1/<case>/`;
- `runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json` and
  `runtime_trace/numeric_ir/v2/artifacts/attempt-05/correspondence.json`;
- `runtime_trace/numeric_ir/artifacts/closure-fresh-01/numeric_ir.json` and
  `runtime_trace/numeric_ir/v2/artifacts/closure-fresh-01/correspondence.json`;
- the source-receipt files named in each `execution.json` and all three frozen
  ELF resolver files named by each `capture.json`.

The superseded `transition.json` files directly inside the raw acquisition
directories were not accepted as checker inputs. The producer, acquisition,
legacy checker/adapter, and Form-evaluator source implementations were not read
as proof logic.

## New files

Source and tests:

- `runtime_trace/caller_transition/checker.py`
- `runtime_trace/caller_transition/tests/test_caller_checker.py`
- `runtime_trace/caller_transition/tests/test_caller_mutations.py`
- `.superpowers/sdd/caller-plan/task-2-report.md`

Final evidence:

- `runtime_trace/caller_transition/artifacts/checker/final/audited-attempt-05/checker_report.json`
- `runtime_trace/caller_transition/artifacts/checker/final/fresh-closure-fresh-01/checker_report.json`
- `runtime_trace/caller_transition/artifacts/checker/final/mutations/manifest.json`
- `runtime_trace/caller_transition/artifacts/checker/final/mutations/cases/<case>/result.json`
  for all 18 cases listed below;
- saved `transition.json` beside each transition-level mutation result;
- `runtime_trace/caller_transition/artifacts/checker/final/verification/commands.md`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/execution_receipt.json`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/audited.stdout`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/fresh.stdout`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/mutation-generator.stdout`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/dedicated-pytest.log`
- `runtime_trace/caller_transition/artifacts/checker/final/verification/dedicated-pytest.xml`

The empty successful stderr streams are retained as zero-byte files. Their byte
counts and SHA-256 of empty bytes are also recorded in
`execution_receipt.json`.

No pre-existing tracked file was edited before staging these new files. The raw
acquisition and Task 1 evidence directories remain outside the Task 2 write
set. README, current/STATUS integration files, and attributes remain root-owned
and were not edited.

## Mutation evidence

The final mutation manifest contains 18/18 `REFUSED` results:

| Mutation | Rejection code |
|---|---|
| component bits changed | `CARRY_BINDING` |
| same bits, wrong dynamic ID | `CARRY_BINDING` |
| component swap | `CARRY_SET` |
| component omission | `CARRY_SET` |
| component duplication | `CARRY_SET` |
| stale previous endpoint | `CARRY_BINDING` |
| other acquisition boundary | `ANTECEDENT_IDENTITY` |
| caller record deletion with repaired chains/hashes | `TRACE_SEQUENCE` |
| caller record reordering with repaired chains/hashes | `TRACE_SEQUENCE` |
| Form-only change | `FORM_BINDING` |
| semantic write alteration with repaired chains/hashes | `WRITE_SET` |
| protected same-value store omission with repaired chains/hashes | `WRITE_SET` |
| incomplete zero coverage with repaired chains/hashes | `WRITE_SET` |
| wrong time provenance | `TIME_PROVENANCE` |
| wrong dt provenance | `DT_PROVENANCE` |
| pointer rebinding hidden behind a positive receipt | `POINTER_IDENTITY` |
| unknown antecedent | `UNSUPPORTED_ANTECEDENT` |
| unknown decoded memory effect | `UNKNOWN_INSTRUCTION_EFFECT` |

For raw-trace attacks, each `result.json` records the exact mutation payload,
base and mutated hashes, repaired chain/final-chain/capture/transition receipts,
and the semantic rejection. The preserved generator source gives the complete
reproduction procedure without storing multiple 2.25 MB transient trace copies.

## Hashes

| File | SHA-256 |
|---|---|
| checker source | `9e730db0e0798c578d082169ecf9e7c7c9e632007608f398941885a950b64ff0` |
| accepted-case test source | `067fe96d116289c7fd94449f62013793406c221ec8aa824da5d9e051b9a849d2` |
| mutation test source | `f56c2f6b3aeba082ea7dd97d76ae256c12e23d923221c8c313696cfc1a4ec35e` |
| final `attempt-05` checker report | `26c69e635e25000f13bd125f89c6bbb1d782a00303f7162d33b80d8ed0ca32d7` |
| final `closure-fresh-01` checker report | `31be0f88958f0fbfdb6c9dee8ba9de9c82e1b903531fb190afeb0ac94d0c1806` |
| final mutation manifest | `d7b9e42e38e852d7a8c5180f470666a031b9922e5eb4a13d9acaac00e82b62bd` |
| final pytest log | `afef2e4221ab6e490a87b1164186668bf759120645b27fedd54c0c42769c6c21` |
| final pytest JUnit XML | `b928ee9686a6663b5e33012184fb066d3f71428c484ec0ded933717e88b92247` |

Antecedent data hashes are independently rechecked by the checker:

- `attempt-05` numeric IR:
  `bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba`
- `attempt-05` correspondence:
  `3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3`
- `closure-fresh-01` numeric IR:
  `c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296`
- `closure-fresh-01` correspondence:
  `a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f`
- frozen module hashes shared by both acquisitions:
  `3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`,
  `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc`,
  `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`.

## Commands and tests

The exact final commands are saved in `final/verification/commands.md`. The
final dedicated result was:

```text
.....................                                                    [100%]
21 passed in 12.03s
```

This covers both accepted cases, their process/acquisition distinction,
unknown-antecedent and unknown-effect refusal, and the 16 semantic/integrity
mutation test functions (including the parameterized time and dt cases).
`py_compile` also exited 0. The root integrator explicitly owns the broader
related/full suites and final 805+27 preservation comparison, so this task did
not duplicate those integration runs.

## Preserved failed and intermediate runs outside the repository

Every Task 2 failed test/probe directory is retained under
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03`:

- `task2-probe-failure-01` — wrong WSL distribution probe;
- `task2-tdd-red-20261003-01` — pre-move/no-test RED command;
- `task2-tdd-red-20261003-02` — missing checker import RED;
- `task2-tdd-red-20261003-03` — 21-test `NotImplementedError` RED;
- `task2-green-repair-failure-20261003-01` — first GREEN repair failure;
- `task2-repair-probe-20261003-02` — thread receipt mismatch;
- `task2-repair-probe-20261003-03` — indirect jump classification failure;
- `task2-repair-probe-20261003-04` — harness-diff receipt mismatch;
- `task2-mutation-generator-20261003-01` — preserved generator plus its first
  missing-`PYTHONPATH` failed stdout/stderr;
- `task2-final-cli-failure-20261003-01` — PowerShell-expanded shell variable,
  exit 127, before the successful direct frozen-interpreter rerun.

Successful/intermediate evidence is also retained out of tree in
`task2-decode-probe-20261003-01`, `task2-dedicated-probe-20261003-01`,
`task2-repair-probe-20261003-05`, `task2-mutation-generator-run-20261003-02`,
`task2-mutation-generator-run-20261003-03`,
`task2-final-dedicated-20261003-02`, and
`task2-pre-final-evidence-20261003-01`. The directory
`task2-final-dedicated-20261003-01` is an empty reserved directory; no command
or result was written there.

## Self-review and limits

- Independence: no forbidden proof module is imported. `rg` finds only the
  module names in the checker documentation/source-hash receipt handling.
- Closed decoding: all 728 actual records decode and validate. The checker is
  deliberately corridor-specific; an unseen memory-destination instruction is
  refused instead of guessed. GNU `objdump` availability and its AT&T output
  are part of this checker environment.
- ELF scope: the parser intentionally supports the pinned little-endian ELF64
  `PT_LOAD` model needed by these three x86-64 binaries. It is not a general
  cross-architecture ELF verifier.
- Semantic scope: exact storage/value/ID/COPY/Form ancestry is checked against
  frozen bytes. The mathematical meaning of those Forms remains conditional on
  the stated external antecedent audit.
- Execution scope: no second body, trajectory, accumulated-error, physical
  accuracy, or general multi-step claim is made. The fresh acquisition gives
  process independence on the same machine only.
- Integration: no checker blocker remains. Broader suites, package/docs updates,
  and the final protected-file comparison are intentionally deferred to the
  root-owned integration step.
