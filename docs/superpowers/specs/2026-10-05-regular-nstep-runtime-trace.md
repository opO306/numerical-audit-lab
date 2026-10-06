# Regular Runtime Trace N-step integration contract draft

Date: 2026-10-05 (Asia/Seoul)

Delivery note: the status below records the original preflight checkpoint, not
the current implementation. The user subsequently directed free desktop/laptop
execution and the proposed ceilings were retained. Actual final results and
limitations are in `current/RUNTIME_NSTEP_INTEGRATED_CANDIDATE_2026-10-05.md`.

Status: PREFLIGHT COMPLETE / IMPLEMENTATION NOT STARTED / EXECUTION BUDGET PENDING.
This document is a concrete implementation contract derived from the user's
Runtime Trace extension request. It is not an execution, checker, audit or
certification receipt.

## Deliverable and authority

Build one source path for N=10 and N=100:
unchanged external Gala execution -> actual instruction acquisition -> Numeric IR
-> unchanged frozen V2 -> independent reconstruction -> adjacent state/Form joins
-> requested-run completion or refusal. A handwritten replacement of Gala's
calculation is not an acquisition. A static template is not runtime evidence.

The user's 2026-10-05 request authorizes extension implementation and integration
verification, superseding the old design-only prohibition on implementation.
It explicitly requires an approved budget before heavy execution. No applicable
N-step execution budget was found in the reviewed repository materials.
No commit, push, paid resource, Impulse change, A-repository change, new physics,
universal program proof or Verified Driver is authorized by this contract.

## Baseline

- Working HEAD: `79a655f0848152aa765e1537b741518b2fa97acf`.
- Current branch: `codex/c1b1-fclaim1-output-limit`; another feature's branch.
- Independently audited 2-step source: `e69119e259b862a7d8462c8d61333782ee2747fd`.
- Frozen Gala 1.12.0 cp312 manylinux x86-64 wheel SHA-256:
  `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
- Frozen V2 LF SHA-256:
  `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`, K=4.
- Source comparison from audited HEAD to working HEAD found no changes under
  `runtime_trace`, `lab/v2_bound.py`, or `audit/gate2c1`.
- The existing 2-step audit report and receipt byte hashes were freshly checked;
  the audit itself was not rerun during preflight.

Implement in a separate managed worktree based on the recorded working HEAD.
Keep every existing source, literal CASE_PINS, accepted input restriction,
historical raw artifact and audit receipt unchanged. New production sources live
under `runtime_trace/regular_nstep/`; new tests and evidence have their own names.
Record a preservation inventory before execution and compare it after delivery.

## Supported contract

The first candidate supports this frozen Linux x86-64/CPython 3.12/Gala environment,
the existing regular orbit, one orbit/two coordinates, dt represented as 1/64,
and observed finite N=10 and N=100 executions. One entry point accepts N; N does
not select a different implementation or a literal trace fixture.

Numerical reference: the actually supplied represented schedule bits and the
observed ordered ADD/SUB/MUL operation sequence, with the existing accepted base
case. This is a rounding-layer claim conditional on the observed path. Schedule
generation accuracy, exact-reference branch equivalence, continuous trajectory,
physical accuracy and all future executions remain outside the claim.

The inherited init-return -> step1-entry gap remains UNTRACED and explicitly
conditional on the accepted base contract. Native zero symbolic coefficients
and separate nonzero-coefficient algebra tests must be reported separately.
Distinct processes alone do not establish ASLR diversity.

## Contract changes versus implementation choices

The following new contracts are necessary and are explicit additions; the old
contracts are not relaxed:

1. New-run trust: accept a fresh capture through reviewed collector/source/module
   identities, actual process/thread identity and full semantic checks. Keep the
   old literal input pins private to old paths. No public TEST_ONLY_REPIN mode.
   Capture hashes bind bytes; GDB/OS execution truth remains a stated trust premise.
2. Caller admissibility: derive actual instruction effects and control flow for
   each observed corridor, instead of asserting that all future corridors equal
   the old 727-row case. Unknown instructions/effects/helper paths refuse.
   Register, flag, EA and memory semantics must justify changed loop values;
   deleting signature fields is not that justification.
3. Completion: acquire and check the final native output-store corridor separately
   from internal handoffs. Bind all four final q/full_v output lanes to their
   actual source loads and destination writes, correct save index and output
   allocation. Require N actual entry/return pairs, no unexpected next step,
   source-bound harness result and observed zero-code normal inferior exit.
   Report the verified terminal frontier and any subsequent untraced harness
   boundary. If this path cannot be supported, completion is refused.

These additions implement the requested scope; they do not claim universal
induction or newly close historical gaps. Any change to the supported domain,
reference meaning, refusal criteria or untraced boundaries beyond this contract
must be reported together before dependent implementation.

## Dynamic identity and joins

Namespace: `(acquisition_id, region_kind, k, global_trace_seq, local_value_id,
byte_offset)`. Encode deterministically; never key identity by bits or static PC.
Regions are `init`, `body(k)`, `caller(k,k+1)` and `terminal(N)`.
Global rows and local occurrences are unique, ordered and contiguous inside the
declared traced frontier. A gap is a declared boundary, never a fabricated row.

Each adjacent handoff verifies acquisition/process/thread, native RET and entry
seams, all six q/full_v/latent lane pointers/bits and actual last-write lineage.
The complete possible-write set must prove zero overlap, including same-value
writes. Allocation/free, pointer/alias changes or concurrent modification refuse
the pure-carry contract. ABI provenance and EA are recomputed independently.

Each next input receives precisely the preceding terminal Form/state ID,
serialized coefficient/box and shared basis. No old step1 Form reuse, box reset,
bit-equality substitution or cross-acquisition edge. Gradient becomes exact zero
only after actual complete 16-byte reset with no later overwrite. t/dt require
their own actual PRE load/address/bytes -> XMM -> entry-argument lineage.

Frozen Form convention remains computed-minus-reference, four shared basis
variables and the existing outward box arithmetic. No QR/rebase or new bound.
Independent center/RNE checking and independent Form recomputation remain
separate from actual frozen V2 calls.

## Failure and publication

Return a machine-readable report containing requested_steps, captured_steps,
checked_prefix_steps, last_verified_trace_seq, failure_stage and requested_complete.
A successfully checked prefix is not a completed requested execution.
Missing/duplicate/reordered rows or segments, unsupported effects, bad state/Form
joins, checker exceptions, resource exhaustion and false completion must refuse.
Publish completion last only after all lower checks and joins pass. Preserve
failed attempts in exclusive directories; never overwrite or relabel them PASS.

## Resource proposal pending user decision

Proposed local limits are ceilings, not estimates of needed time or scalability:

- One active numerical job, no paid resource.
- Numerical acquisition/checking/tests/audit subprocess wall time: cumulative
  3,600 seconds, counted without double-counting nested subprocesses.
- Any single guarded numerical invocation: at most 600 seconds and no more than
  the remaining cumulative allowance.
- Process-tree memory ceiling: 4 GiB; cgroup memory controller must be available
  and its applied limit checked before a numerical job starts. No automatic
  downgrade to per-process RSS or an unenforced limit.
- New evidence storage: total at most 8 GiB. All writers, logs and mutation
  materialization must reserve/count bytes before publication. Existing evidence
  reads do not consume this new-storage allowance.

Failure to enforce a proposed limit stops numerical execution. Exceeding a limit
records REFUSED_RESOURCE and the last checked prefix. Extensions or additional
paid resources require a new user decision. Implementation and document review
time are not numerical-execution wall time; report them separately.

Measure original execution, traced execution, translation/frozen V2, independent
checker and audit separately, retaining time, peak tree memory, output sizes,
commands, exit codes and source maps. Harness integration-call timing is included
in the traced process and must not be added to it as a separate elapsed cost.
Original-run overhead includes startup; disclose both process and API-call
measurements. No performance claim precedes measurements.

## Required evidence

Verify 10 steps first, then 100 with the identical collector/translator/checker
source SHA map. If relevant code changes after 10 steps, rerun affected 10-step
verification before claiming source-identical 10/100 evidence.

Attack matrix must include repaired hashes as well as HASH/TRUST controls:
arithmetic result tampering; missing/duplicate/reordered raw rows; missing body or
caller; cross-process/cross-k splice; equal-bit ID merge; wrong EA; omitted
same-value write; partial gradient reset; time/dt source swap; wrong terminal
state ID; old Form reuse; box reset; coefficient/basis swap; reordered components;
missing final save; wrong final save index; missing next-step refusal; false N;
premature completion; checker failure; time/memory/storage exhaustion.

Run relevant tests during development and integrated regression on the connected
candidate. Obtain a fresh independent review/audit of the final source and raw
evidence without using the production evaluator as the numerical oracle.
Author-ported old audit code is checker reuse, not a fresh external audit.
Name the new audit's authorship and dependency boundary. External independent
audit closure requires an actual external result; keep it PENDING otherwise.
After audit fixes, revalidate affected paths and source-map correspondence.

Final reporting starts with the user's five questions: automatic external path,
same-source 10/100 results, refusal behavior, measured cost/limits and completed
scope/audit/blockers. Verified Driver follows only after designer review.
