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

---

# Task 2 fix round 1 addendum: read-proof control and ABI semantics

Date: 2026-10-03

Implementation base: `6ceaa3460e77dc855ddac03bd4ad78d65a16e21d`

Implementation/evidence commits:
`85716d5adffc04f712e5afbb80594a71d0286969` and
`38dcc6f52d30278e3af98a8f989d34d4577eeef7`

Task result: **DONE** for the scoped Task 2 fix. This addendum supersedes the
historical acceptance claims above for the old v1 acquisitions and old
`artifacts/checker/final` reports. Those bytes remain preserved history. The
accepted inputs and outputs for this fix are the two `*-readproof-01` raw
acquisitions, `producer-fix-round2`, and `artifacts/checker/fix-round1`.

This remains an author-side independent checker run. It does not perform or
claim a new external audit of the endpoint Forms, second-body execution,
trajectory closure, accumulated error, or physical accuracy.

## Review-finding disposition

| Finding | Disposition and evidence |
|---|---|
| C1 indirect/RET targets | Closed for every observed instruction. The checker derives all 16 indirect control targets from independently validated 8-byte pre-memory observations, all 23 RET targets from the pre-RET stack bytes, and every conditional branch from pre-EFLAGS plus the decoded direct target. Repaired source-byte attacks refuse as `TRACE_CONTROL_TARGET`. |
| C2 memory/register/final ABI def-use | Closed for this observed corridor. A byte shadow roots all 219 required observations, checks write preimages, and carries 111 writes. The checker executes every observed GPR/XMM/control-state instruction family, compares the complete post register state, and compares all architecturally defined flag bits. The final `rdi/rsi/rdx/xmm0/xmm1/rcx/r8/r9/[rsp]` argument values are therefore established from observed memory or prior register definitions through the final call. Repaired t/dt/q/full-v/latent/gradient/C-potential/n/half-dimension attacks reach and fail semantic checks. |
| I1 dense deletion/reorder | Closed. The saved attacks remove old sequence 106 or swap old 104/105, densely renumber rows, remap every schema-declared sequence receipt, repair row chains, trace/capture/seal/transition hashes, and repair claimed adjacency. Both pass structural integrity and refuse at `TRACE_CONTROL_TARGET`, not `TRACE_SEQUENCE`. |
| I2 immutable identities/execution receipt | Closed. Production uses literal case/path, transition, acquisition seal, exact sealed-file set, capture, execution, trace/final-chain, structured process identity, module/load-base, wheel, exact 11-source map, and antecedent IR/correspondence pins transcribed from the approved handoff. The handoff is not a runtime input. Public API/CLI expose no trust override; old v1 inputs refuse as `SUPERSEDED_EVIDENCE`. A coherent local repin through the public path refuses as `TRUST_PATH`. |

## Literal trust handoff

The fully read authoritative handoff was
`.superpowers/sdd/caller-plan/task-2-fix1-pin-handoff.json`, SHA-256
`39687ceef0d767869a3b958067ac2921e84e4c66f30eab2c484f345e63f1ad81`.
`verification/literal-pin-audit.json` independently compared the source
constants with that handoff and records `all_exact: true` for both cases, the
11-source map, the three module hashes, and the wheel hash.

The production interface is only:

```python
check_transition(capture_dir, transition_path, *, root=None, objdump="objdump")
```

It selects one of the two literal tables by exact resolved production paths.
The private `_check_bundle_with_pins` hook is used only by tests and the saved
mutation generator with in-memory `TrustedCasePins`. It is absent from the CLI
and public signature. Test injection changes only acquisition blob pins so a
repaired mutation can reach the semantic core; literal source/module/wheel/
antecedent identity pins remain fixed. Results label this mode
`TEST_ONLY_IN_MEMORY_ACQUISITION_PINS` and never represent it as production
verification.

The structured process identities are retained as JSON objects:

- audited read-proof: boot
  `ad2a0c22-e8d1-466b-8bbf-31c2cf4f54cd`, PID 394, start tick 12881;
- fresh read-proof: the same boot, PID 449, start tick 13968.

Root's separately supplied
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/readproof-root-verification.json`
records PASS for 39 raw/Git files and independently derived counts. It is
treated as the immutable handoff review, not as checker semantic proof.

## Independent algorithm and actual coverage

The checker still imports only standard-library modules and invokes external
GNU `objdump`; it does not import producer, acquisition, read/write effect,
module-resolver, old checker/adapter, or Form-evaluator proof logic.

1. It verifies the literal trust table and exact acquisition file set before
   parsing semantic claims. It authenticates `execution.json` by literal SHA,
   the acquisition seal, capture/transition receipts, exact source/module
   sets, and structured process identity.
2. Its ELF64 parser and GNU objdump path independently check every module,
   load base, address, offset, instruction byte, and decoded assembly for all
   728 rows.
3. It derives the exact observation grammar. The 219 observations decompose
   into 123 explicit reads, 30 implicit POPs, 23 implicit RETs, 16 indirect
   controls, 16 read-modify-write reads, 10 implicit LEAVEs, and one final ABI
   stack observation. Missing, extra, wrong-width, failed, or wrong-address
   observations refuse.
4. Effective addresses use pre-GPR/RIP plus the per-row FS/GS bases. This
   independently includes the previously omitted FS-relative writes at
   sequences 369, 374, and 457. The derived total is 111 writes, of which 21
   are same-value stores.
5. A byte shadow checks every redundant observation and known write preimage,
   then applies each validated write. It refuses disagreement rather than
   choosing one source.
6. The corridor-specific interpreter covers the actual `mov/movl/movq`,
   `movzbl`, `lea`, call/push/pop/leave/ret, add/sub/and/or/xor/shl/shr,
   cmp/test/setne, locked cmpxchg, xchg, `movsd`, `vmovd`, `vmovdqu`,
   `vpbroadcastb`, endbr/nop, and actual branch forms. It compares all GPRs,
   all XMM registers, MXCSR, FS/GS bases, and defined flag results after each
   row. Architectural undefined AF for logical/shift instructions and OF for
   multi-bit shifts are deliberately excluded; every defined flag bit is
   checked.
7. Final ABI provenance is established through sequence 718 time memory load,
   719 q copy from r15, 720 latent copy from r14, 721 observed-memory gradient
   push and validated stack write, 722 C-potential load, 723 dt load, 724
   half-dimension load, 725 n load, 726 full-v load, and the direct call at
   727 including its return-address stack write and entry gradient observation.
8. Existing IR/COPY/Form, carry no-overwrite, pointer identity, exact-zero
   gradient coverage, fresh-root, basis-namespace, and no-second-body checks
   remain in force against the literal-pinned antecedents.

Unsupported decode/read/write/register forms refuse. This is an exact
corridor-specific x86-64 interpreter, not a general x86 emulator.

## Normal results and hashes

Both public CLI runs returned `CHECKER_PASS`:

| Case | PID | capture SHA-256 | trace SHA-256 | transition SHA-256 | rows / reads / writes / same | indirect / RET | shadow bytes | body |
|---|---:|---|---|---|---|---|---:|---:|
| `audited-attempt-05-readproof-01` | 394 | `9ae29bee14c2d42265dbf353a1e55caa78012c16210fa7c5b6bf8e84cd8c9157` | `64f5f8caaf00cbd691ad24bdb8fa59fd6f50bbf4036d8671895fd27ac7766877` | `526132b3ec1d1efcb06c05dd4ac803cd818074b63b47bec1a381ac38b4aa0f59` | 728 / 219 / 111 / 21 | 16 / 23 | 726 | 0 |
| `fresh-closure-fresh-01-readproof-01` | 449 | `ebb9a05557a28a58afa8835d74e4f473048b2bcc554fc5e8f18c1fdb715ab185` | `0f195ce50ae247394bd95bda00a5de304e180752df69284405c80c112b4ad9b5` | `01ca255ece2fef51fe4737deb42a005d6ea5ba39a2ed79c9f8eab66f9eac61f7` | 728 / 219 / 111 / 21 | 16 / 23 | 726 | 0 |

Key output hashes:

- checker source: `fbdea1a42f8422e4393f28ffc9c0b6f0c7ccdf608ce369128b5737a941cc276c`;
- accepted-case tests: `9a3c4ed34d46d960339a747ab121c488bdf8303acb9586fec50b4883ad75d6c6`;
- prior mutation tests: `5ed0b03bce30dba430dccfdfe2c83338cf8562f5288435d85f967f8ab4bd2818`;
- fix mutation tests: `509a0d7cb13c6ca037a251ac908d42e1e9a18e4c37f1a5150ba59017cb004ba7`;
- audited checker report: `35a8f4662c676a15582dec5ba36bd5c6e5a9ee87af12cc85ce955dae9cda514f`;
- fresh checker report: `6cec65c3c3e6a730a9628875ff5fd638e3844cc0c11209f758ac6f2daa161f82`;
- mutation manifest: `b5c0805e31b21274ddc28ead02e77ef52f60bc97c904e443bdf579188a71a14b`;
- dedicated pytest log: `7b7632d73f03707c1bb9a6edc3c9e6a53c93291200d622ac37a76a3cd372e108`;
- dedicated JUnit: `845ceb57cb92b265d515fe5d271a1065a48fe7556d4553204012c43f59bc3e61`.

## Mutation evidence

`artifacts/checker/fix-round1/mutations/manifest.json` records 35/35
`REFUSED`. It includes all prior semantic classes plus:

- indirect target and RET stack-source byte changes;
- time, dt, C-potential, half-dimension, n, full-v and gradient source bytes;
- q/latent register def-use propagation attacks;
- TLS destination rebinding and required-read omission;
- dense repaired deletion/reorder with every wrapper/receipt rebuilt;
- exact source, module, structured process identity, and antecedent pin attacks;
- a coherent public repin that fails rigid production trust.

Each raw semantic case saves a mutation receipt with repaired trace,
final-chain, capture, execution, seal, and transition hashes. Each transition
case saves its mutated transition. Results save the trust mode, completed
stages, exact refusal code, and reason. The external generator source is
preserved at
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-fix1-mutation-generator.py`.

## Commands and verification

Exact CLI, mutation-generator, py_compile, and pytest commands are saved in
`artifacts/checker/fix-round1/verification/commands.md`. The final authorized
dedicated command used frozen Python and produced:

```text
........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 25.82s
```

JUnit records 91 tests, 0 failures, 0 errors, and 0 skips in 25.803 seconds.
`py_compile` exited 0. Both public CLI stderr files and mutation-generator
stderr are empty. The execution receipt records hashes for checker/tests,
reports, manifest, test log/JUnit, pin audit, baseline audit, and commands.

The 93-file protected baseline was independently rehashed after outputs and
records `all_unchanged: true` in
`verification/protected-baseline-verification.json`. This is the scoped
Task2 preservation check; root still owns the final combined suite and package
preservation audit.

## Changed and read files

Changed source/tests:

- `runtime_trace/caller_transition/checker.py`;
- `runtime_trace/caller_transition/tests/test_caller_checker.py`;
- `runtime_trace/caller_transition/tests/test_caller_mutations.py`;
- `runtime_trace/caller_transition/tests/test_caller_fix1_mutations.py`.

New evidence is exclusively below
`runtime_trace/caller_transition/artifacts/checker/fix-round1/`: two reports,
35 mutation case/result directories plus manifest, and verification receipts.
This addendum is the only plan/report edit. README, current/STATUS,
`.gitattributes`, all raw/producer/acquisition sources, historical
`artifacts/checker/final`, and Task1 evidence were not edited.

Fully read for the fix:

- `task-2-fix1-brief.md`, original `task-2-brief.md`, full
  `task-2-review.md`, `task-2-fix1-evidence-requirements.md`, and
  `task-2-fix1-design.md`;
- `task-2-fix1-pin-handoff.json`;
- Task1 `task-1-readproof-report.md` and `task-1-readproof-review.md`;
- root `readproof-root-verification.json` and the 93-file preservation
  baseline;
- both v2 raw capture/execution/seal/module/source/trace inputs, both accepted
  producer-fix-round2 transitions, and the frozen IR/correspondence data;
- the existing checker and all three Task2 checker/mutation test modules.

Producer/acquisition helper source names were read only as fixed hash receipts;
their proof algorithms were not imported or reused.

## Failed and intermediate outputs outside the repository

All fix-round1 failed runs are preserved under
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03`:

- `task2-fix1-red-01`: first v2/public-path RED, including one test-fixture
  path error;
- `task2-fix1-red-02`: corrected RED showing v2 schema refusal and v1 being
  incorrectly accepted;
- `task2-fix1-red-03`: semantic RED showing indirect/RET/ABI mutations were
  initially accepted;
- `task2-fix1-red-04`: a missing per-row FS base originally raised `KeyError`;
  the checker now refuses it as `SEGMENT_BASE`;
- `task2-fix1-exitcode-command-error-01`: the accidental file produced by an
  incorrect PowerShell `Set-Content` argument order; moved out of tree intact.

The successful intermediate dedicated suite is preserved in
`task2-fix1-suite-attempt-01` (`89 passed in 36.92s`). The reports and logs
immediately before the segment-base regression were preserved in
`task2-fix1-pre-segment-base-final-01`; final public-CLI regeneration receipts
were preserved in `task2-fix1-final-cli-regeneration-01`. Earlier Task2
failure and probe directories are enumerated in the historical report section
above and remain unchanged.

## Self-review and remaining limits

- The literal pin audit is exact and production has no file/env/argument trust
  override. Private pin injection remains an underscore-prefixed test hook.
- The two accepted processes are independent only within the same boot/machine.
- GNU objdump AT&T syntax is an external decoding boundary; bytes, operands,
  and actual post-state are independently checked, and unseen forms refuse.
- Undefined x86 flags are not asserted. Defined flags and all recorded GPR/XMM,
  MXCSR, and segment bases are checked.
- Memory shadow roots are the authenticated live observations and captured
  write preimages. No post-hoc old read was invented.
- Form semantics remain conditional on the literal-pinned external antecedent;
  this checker does not create a new external audit.
- The scoped implementation has no known blocker. Fresh independent re-review,
  the broader combined suite, integration docs, and final package audit remain
  root-owned.

# Task 2 fix round 2 addendum: complete ABI origins and repaired receipts

Date: 2026-10-03

Implementation base: `5dac56db67b0311b342e92a722916b1fa1c201e4`

Implementation/evidence commit:
`bc2de9b2816d014a659d1892b37fdfb941f83184`

Task result: **DONE** for the scoped fix-round-2 implementation. This addendum
supersedes the fix-round-1 C2/I1 and saved-input claims. It does not supersede
the literal acquisition pins, raw read-proof evidence, antecedent hashes, or
the C1/I2 controls. It does not claim a new external audit or closure beyond
the prospective second-step entry.

## Review finding disposition

- **C2 MOVSD and missing origin graph — addressed.** Legacy memory-form
  `movsd m64,xmm` now replaces the low 64 bits and clears bits 127:64. The
  reviewer's repaired 728-row attack, with upper value
  `0x1122334455667788` carried through actual rows 615, 636, 657, and 678,
  now refuses at `REGISTER_SEMANTICS` on row 615. Register-source legacy MOVSD
  retains the destination upper lane as required.
- **C2 final ABI provenance — addressed.** The checker propagates explicit
  value origins independently of producer claims and serializes nine final ABI
  chains in each normal report. Correct numeric bits with a `dt` root claimed
  as `time` refuse at `ABI_PROVENANCE`.
- **I1 deletion/reorder — addressed.** Sequence/count receipt validation runs
  before control, memory, register, and provenance semantics. Superseded sparse
  remaps refuse at `SEQUENCE_RECEIPT`. Fully repaired deletion and reorder
  bundles use maps computed from the retained order, update every declared
  sequence and count receipt, pass the receipt preflight, and then refuse at
  `TRACE_CONTROL_TARGET`.
- **Important saved-input gap — addressed.** Five full mutated raw bundles,
  their transition inputs, receipts, results, and the checked-in generator are
  committed. The unit origin attack includes its complete structured fixture.
- **C1/I2 — retained.** Actual indirect/RET control checking, literal source,
  module, acquisition, process, and antecedent pins, and the absence of a
  public/CLI trust override remain in force. Production input pin values did
  not change.

## Value and origin algorithm

The pre-existing numeric interpreter remains the authority for recorded GPR,
XMM, flags, MXCSR, segment-base, memory-write, and control-state equality. The
origin interpreter is a second track over those already authenticated values.
It seeds `AuthenticatedContext` nodes at the first-return boundary and
`AuthenticatedMemoryRoot` nodes from exact live pre-memory observations. A
stack root receives an ABI role only when its exact derived address, width, and
bytes equal the authenticated role value.

The origin engine handles every instruction family present in the 728-row
corridor. It emits `Load`, `Store`, `Copy`, `Arithmetic`, and
`InstructionResult` nodes for explicit/implicit loads and stores, register
copies, partial-register writes, arithmetic and flags, stack operations,
XMM/VEX operations, and every control transfer. It retains per-lane XMM
origins, including explicit zero origins for memory-form MOVSD upper 64 bits
and VMOVD upper bits. Unknown origin, source, destination, or write forms fail
closed as `ABI_PROVENANCE`.

At pre-call row 727, the independently derived normal chains are:

- `rcx/q`: `Copy(719) <- Load(539) <- Store(522) <- Load(360) <- Store(54)
  <- AuthenticatedContext(first-return,r15,q)`;
- `r8/full_v`: `Copy(726) <- Load(726) <- AuthenticatedMemoryRoot(full_v)`;
- `r9/latent`: `Copy(720) <- Load(582) <- Store(450) <- Load(359) <-
  Store(55) <- AuthenticatedContext(first-return,r14,latent)`;
- `[rsp]/gradient`: `Store(721) <- Load(721) <-
  AuthenticatedMemoryRoot(gradient)`;
- `xmm0.low64/time`: `Load(718) <- AuthenticatedMemoryRoot(time)`;
- `xmm1.low64/dt`: `Load(723) <- AuthenticatedMemoryRoot(dt)`;
- `rdi/cpotential`, `rsi/n`, and `rdx/half_ndim`: `Copy(722/725/724) <-
  Load(722/725/724) <-` their exact authenticated memory roots.

These origin chains supplement rather than replace the existing terminal COPY,
dynamic value/state identity, Form-ancestor/shared-basis, component-memory,
fresh-gradient, time-schedule, and dt entry-root checks.

## Receipt preflight and mutation construction

`_validate_sequence_receipts` checks capture and transition record counts,
all nine independently counted row/read/write/control totals, every scalar
`sequence`/`*_sequence`, every `*_sequences` list, final ABI observation
references, gradient write references, and save-all candidate references.
Each reference must select a retained dense row. This phase executes after
pinned ELF decode and before semantic execution.

The fix-round-2 generator builds `old_sequence -> new_sequence` only after
deletion or reordering. It recursively remaps the schema-declared sequence
fields, independently recomputes row/read/write/control counts, rebuilds every
row chain, trace/final chain, capture, file hash, acquisition seal, transition
authentication receipt, and in-memory test pins. The two repaired attacks
record `receipt_preflight: PASSED`; the two intentionally stale controls record
`receipt_preflight: REFUSED`.

## Changed and read files

The implementation commit changes exactly 90 files: 85 new files entirely
under `runtime_trace/caller_transition/artifacts/checker/fix-round2/`, plus:

- `runtime_trace/caller_transition/checker.py`;
- `runtime_trace/caller_transition/generate_checker_fix2_mutations.py`;
- `runtime_trace/caller_transition/tests/test_caller_mutations.py`;
- `runtime_trace/caller_transition/tests/test_caller_fix1_mutations.py`;
- `runtime_trace/caller_transition/tests/test_caller_fix2_mutations.py`.

The 85 evidence files comprise two normal reports; five complete 9-file raw
mutation copies plus their transition/receipt/result files; one structured
origin fixture plus receipt/result; one mutation manifest; and 19 verification
files (commands, CLI/generator/test/pycompile stdout/stderr and exit codes,
JUnit, execution receipt, and the protected baseline audit). No read-proof raw,
producer, old checker artifact, acquisition source, README, current/STATUS, or
attribute file was edited.

Inputs fully read or structurally parsed for this round were
`task-2-fix2-brief.md`, the full `task-2-fix1-review.md`, the C2/I1/origin and
mutation sections of `task-2-fix1-design.md`, the existing checker and all
Task-2 checker tests, both read-proof captures/traces and accepted transitions,
the prior Task-2 report, and the root-supplied 177-file preservation baseline.
Producer/acquisition helper algorithms were not imported into the checker.

## Evidence paths and hashes

Normal reports:

- audited: `artifacts/checker/fix-round2/audited-attempt-05-readproof-01/checker_report.json`,
  SHA-256 `a3964850e39643fe2dd503883773a35952f1412b3e3e8f267487d0be6bc03f36`;
- fresh: `artifacts/checker/fix-round2/fresh-closure-fresh-01-readproof-01/checker_report.json`,
  SHA-256 `50ae61b76b2b9efc38edb3d554b8cc7df30a1383345ee271b9c8fa223cb1c923`.

Both say `CHECKER_PASS`, schema
`gala-caller-transition-independent-checker-v3`, 728 decoded rows, 219 reads,
111 writes, 21 same-value writes, 16 indirect controls, 23 returns, zero
second-body instructions, and nine authenticated ABI origin chains.

Key source/evidence SHA-256 values:

- checker: `8c1915ed19e9fb1cefd757d8a2ff8c475193ed581fa272784dabcd89e5e125a4`;
- generator: `c435f52d976d22b93c3060b8537a45fe670d8eea662a4d77266128c9be972d5d`;
- fix2 tests: `b54d98ef166fadae9ccee60c440daf2d7683c14a196f2ca407b476ea7d4e1541`;
- mutation manifest: `579a7bf163a51efd0778f8b60cbc6e6abce767d0299f2b14bfa99e9fe1e89f45`;
- dedicated log: `8d3919a9d4fb9b307e145f799f40aff0d2c9d4a018183f8cd176fc7f947c2370`;
- JUnit: `38dce38e2abb6564f65f8f379c0b7968c2424018ead4a7d94a40acdc0f487029`;
- protected-177 audit: `46002c5bf9ad214aa0a43d387e7e03b56ed04d0f43abdf9381e753754db88e28`.

The mutation manifest contains six committed cases, all `REFUSED`:

- `movsd-memory-upper64` -> `REGISTER_SEMANTICS`;
- `dense-deletion-stale-receipts` -> `SEQUENCE_RECEIPT`;
- `dense-deletion-fully-repaired` -> `TRACE_CONTROL_TARGET`;
- `dense-reorder-stale-receipts` -> `SEQUENCE_RECEIPT`;
- `dense-reorder-fully-repaired` -> `TRACE_CONTROL_TARGET`;
- `same-bits-wrong-origin-role` -> `ABI_PROVENANCE`.

Every result contains the SHA-256 map of its actual committed input files. A
fresh exclusive replay under `task2-fix2-generator-final-replay-01` produced a
byte-identical manifest.

## Commands and verification

Exact commands are saved in
`artifacts/checker/fix-round2/verification/commands.md`. Frozen Python produced:

```text
........................................................................ [ 72%]
...........................                                              [100%]
99 passed in 33.69s
```

JUnit records 99 tests, 0 failures, 0 errors, 0 skips, and 33.673 seconds.
`py_compile`, both public CLI runs, mutation generation, and the suite all
exited 0. Their stderr files are empty. The execution receipt hashes checker,
generator, tests, accepted raw/seal/capture/execution/transition inputs,
normal reports, mutation manifest, commands, logs, and preservation audit.

The root-provided baseline
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/checker-fix1-completed-evidence-baseline.json`
has SHA-256 `4dcc2713e6720c4467f4cc7d64de00f163ce5f8cac285b9ffbf414612e8d1ad7`.
All 177 listed files rehashed unchanged after generation and testing.

## Preserved failed and intermediate outputs

All round-2 diagnostic directories are exclusive and retained under
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03`:

- `task2-fix2-red-01`: initial RED, 4 failed and 1 passed;
- `task2-fix2-intermediate-01`: MOVSD/receipt fixes green, origin reports still
  absent, 2 failed and 3 passed;
- `task2-fix2-origin-green-attempt-01`: first origin run exposed the expected
  full-v top-node shape mismatch, 2 failed and 3 passed;
- `task2-fix2-focused-green-01`: broader intermediate run exposed 10 old tests
  whose unrepaired receipts now correctly failed preflight, 10 failed and 33
  passed;
- `task2-fix2-generator-attempt-01`: successful first six-case generator run;
- `task2-fix2-generator-final-replay-01`: successful byte-identical final
  generator replay.

The small diagnostic source `inspect-fix2-reorder.py` is also retained there;
it identified the superseded sparse reorder helper's empty time sequence list.
No failed or intermediate output was overwritten or committed as a normal
result.

## Self-review and remaining limits

- Origin nodes explain byte/register derivation over authenticated observations
  and independently validated execution. They do not create native Form objects
  or replace the frozen external Form audit.
- The two accepted acquisitions remain separate processes from one machine and
  boot. No cross-machine claim is made.
- GNU objdump AT&T output remains the external decode boundary. Every observed
  family is closed; unseen origin/value/control forms refuse.
- Undefined flag bits remain excluded according to the existing opcode masks.
  This change adds no new floating-point arithmetic semantics.
- The second native body, second V2 block, trajectories, accumulated error,
  physical accuracy, and external-audit closure remain outside scope.
- The scoped implementation has no known evidence or opcode blocker. The root
  owner retains the combined suite, integration documentation/package checks,
  and the original reviewer's scoped re-review.
