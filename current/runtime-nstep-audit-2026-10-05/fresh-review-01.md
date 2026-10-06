# Runtime Trace N-step fresh reviewer report 01

Date: 2026-10-05. Reviewer: separately spawned fresh Codex reviewer `/root/audit_nstep`.

Status: **CHANGES REQUIRED; initial evolving-source review, no external audit closure.**

This review read all currently present new `runtime_trace/regular_nstep/*.py`,
the extension spec/plan, the native10-02 receipt and selected actual raw records,
and reused body/caller semantic checker primitives. The reviewer did not execute
numerical jobs or tests, and did not use the producer or frozen V2 as an independent
oracle. Observed derived10-01's checker receipt states 10 checked steps and 234
operations; that is an inspected implementation receipt, not a new reviewer-run
test. No 100-step evidence existed in the material inspected.

Baseline supplied to the review: working HEAD
`79a655f0848152aa765e1537b741518b2fa97acf`; old audited HEAD
`e69119e259b862a7d8462c8d61333782ee2747fd`. This report does not independently
rerun the historical external audit. Existing init-to-step1 and post-terminal
native frontier-to-Python-tail gaps remain UNTRACED and conditional.

## Findings sent promptly to implementer

1. **P1: body instruction contexts can claim unexplained general-register changes.**
   New raw checking calls `body_checker.graph`, which reuses
   `runtime_trace/correspondence.py:222-319`. At lines315-317 that primitive removes
   knowledge on an unexplained GPR change; it does not reject the change or derive
   every register result. Caller register semantics are stronger, but cannot prove
   a body-produced register value. A fabricated body post `r13` (or another
   callee-saved/ABI/control register), propagated through subsequent body contexts
   and into the caller, can preserve the same numerical graph while changing the
   actual schedule/control state. Requested probe: change one body scalar
   instruction's otherwise preserved `r13`, maintain all later register seams,
   and repair every hash. Required fix: independently validate complete body
   register/effect semantics, or an explicitly closed, complete rule set covering
   every body register that reaches ABI/control or pointer arithmetic.

2. **P1: body PRE read and possible-write sets are not independently complete.**
   `raw_check.py` initially called `structure._check_observations(body_rows)`
   (around line312 in the evolving source), which checks statuses and lengths.
   `body_checker.graph` derives numerical copies/stores from `operands` and
   `result_bits`; it does not compare body `possible_memory_writes` or
   `pre_memory_observations` with all independently decoded effects. Requested
   probes: omit a body store observation, omit a same-value PUSH/store, and omit
   one body PRE read while leaving numeric operands/contexts intact and repairing
   hashes. Required fix: derive and compare complete body read/write sets for the
   closed supported instruction family, including implicit stack effects.

3. **P1: each caller/terminal memory shadow starts empty.**
   `raw_check._memory` (`raw_check.py:98-99` in the evolving source) starts
   `shadow = {}` per segment. Consequently a read of a persistent stack or routing
   slot can become a new independent root although the preceding segment actually
   wrote that address. Concrete native10-02 terminal probe: at seq9817,
   `mov 0x108(%rsp),%rdx`, change the slot's PRE read pointer by -8; propagate -8
   through derived `rdx` contexts and all four output write addresses; change the
   seq9919 slot RMW before/after values by -8. Before the adjacent-output fix this
   retains stride, bits and final loop termination while writing the previous save
   index. Required fix: maintain memory def-use across traced bodies/callers and
   terminal; restrict newly admitted roots to actual first observations, under
   explicit live-allocation/thread assumptions. Adjacent output addresses alone
   address one symptom; inspect t/dt, full_v and gradient pointer routing too.

4. **P1: final save index/allocation was initially only a stride check.**
   Initial `_terminal` checked four ordered source lanes and destination spacing
   `8*(N+1)`, but did not bind save index N and the allocation to previous saves.
   The implementer has since added `_output_stores` for every internal caller and
   a +8 adjacent-column constraint. This is a relevant correction, still requiring
   the concrete repaired probe above and whole-memory/root checks. The initial
   all_w allocation creation and first-save offset occur in the inherited gap;
   any allocation-root premise at that gap must remain explicit, not described
   as newly traced allocation proof.

5. **P1: the initial aggregate storage reservation did not constrain writers.**
   `run_guarded` initially reserved `artifact_allowance` only in a caller-local
   `EvidenceBudget`; acquire/producer/GDB writers did not consume that allocation.
   RLIMIT_FSIZE was file-local, not an aggregate quota. Multiple files could exceed
   the stated 8GiB aggregate ceiling during a job. The implementer has since added
   file-backed locked `WriterQuota` and environment plumbing. Required validation:
   all raw/receipts/GDB logs/harness writes/derived files/mutations and failure
   receipts consume reserved bytes before writes; the guard's log/measurement and
   growing ledger reservations also fit; controller failure never refunds elapsed
   time or leaves a successful report. Public output paths must remain included
   in the global storage reconciliation.

6. **P2: raw JSONL parsing was less strict than capture/derived parsing.**
   `raw_check.validate` initially reused `structure._load_rows`, whose JSON parser
   accepts duplicate keys and non-finite constants. Capture/derived JSON uses a
   stricter parser. Requested probe/fix: duplicate a raw row key with a conflicting
   earlier value and repaired last-wins chain; reject ambiguity before semantics.

7. **P2: refusal/frontier and source-map evidence were not yet complete.**
   `checker.check` refusal currently lacks requested_steps, captured_steps and
   last_verified_trace_seq; raw failure returns checked_steps0 at ACQUISITION.
   The eventual runner must report the actual last independently checked interval
   (explicitly none when absent), captured range and requested completeness
   separately. Final identical-source evidence must include translator/checker,
   schema/raw checking and reused independent primitives, not only collector pins.

8. **P2: thread/all-stop metadata needs independent consistency checks.**
   Matching rewritten `pid`/`ptid` fields alone does not validate original
   `thread_ptid`, region owner, PID/PTID relation or scheduler-locking receipts.
   The collector enables scheduler locking, so this is a receipt-validation gap
   rather than evidence of actual concurrent execution. Requested attacks: change
   scheduler-locking receipt, original row thread_ptid or owner PID relationship;
   they must refuse under the no-concurrent-modification pure-carry contract.

## Evidence and dependency boundary

The source changed while findings were being communicated. At a subsequent
read, these byte SHA256 values were recorded, not asserted as final audited pins:

| Source | SHA256 |
| --- | --- |
| raw_check.py | b072113356312efccbb2747494ac9c1acdb8ad00020581df8b2e3f8b311ea0bc |
| resources.py | 7dc7598e8a0f03c55e157383c79bac6b946f9ab3b02a7f094c43a3b8b527874a |
| producer.py | 0d33d885c61ce070ef10c91bdd5830825b64f15b2d8532b113c88a475a03126f |
| checker.py | 7f7fc510af18ff2184e4094cef096b4cfaed37cdbab02dc627fca8d2267a54e5 |
| schema.py | 6a0a7c5ece4765ff1134a95f5b8769b9d1660cdaa0f8d0abb76c30793976ea3d |

Independent body reconstruction and exact IEEE/Form oracle reuse have a
different code path from production translation/frozen V2, which is useful.
They are historical author-ported checker reuse, not a fresh external numerical
audit. This fresh agent review is likewise not an external audit result. Final
review requires immutable final source pins, actual 10/100 evidence, repaired
attack receipts, resource receipts and affected revalidation after the fixes.

