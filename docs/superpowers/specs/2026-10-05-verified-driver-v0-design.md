# Verified Driver V0 design

Date: 2026-10-05 (Asia/Seoul)

Status: DESIGN APPROVED IN CHAT / SPEC WRITTEN / NOT IMPLEMENTED / NOT AUDITED

## 1. Purpose

Build the first control layer that prevents an unverified external calculation from
becoming authoritative state.

The external Gala calculation is a proposer, not an authority. A candidate result
may become the Driver's certified state only after the already-delivered Runtime
Trace path and its independent checker accept the exact candidate execution.

This is the next step after the finite regular Runtime Trace integration. It does
not expand A, add new physics, or generalize the tracer to arbitrary programs.

## 2. Baseline and evidence boundary

The implementation target is the managed runtime-nstep worktree based on Git HEAD
`79a655f0848152aa765e1537b741518b2fa97acf`.

The Runtime Trace N-step candidate is currently uncommitted work under
`runtime_trace/regular_nstep/` plus its tests/evidence. Its delivered observed
scope is the inherited regular Henon-Heiles case, pinned Gala 1.12.0 native wheel,
Linux x86-64/CPython 3.12, represented dt=1/64, with fresh N=10 and N=100 runs.

Driver V0 may consume that candidate through explicit source/evidence pinning.
It must not silently promote the uncommitted Runtime Trace candidate into a new
historical baseline, nor rewrite its evidence.

Retained Runtime Trace limitations remain limitations of Driver V0:
- init-return -> step1-entry is UNTRACED;
- native terminal frontier -> Python wrapper tail is UNTRACED;
- initial allocation/root premises remain inherited;
- GDB/collector/OS execution truth is a trust premise;
- observed native symbolic coefficients are zero;
- physical trajectory correctness, universal program support, formal
  certification and external audit closure are not established.

## 3. Chosen V0 architecture: transactional segment gate

Driver V0 is not an in-process per-instruction controller.

It runs one external candidate segment in an isolated pending transaction:

```text
certified state S0
      |
      v
external Gala candidate execution
      |
      v
pending candidate artifact C1
      |
      +--> Runtime Trace acquisition
      +--> Numeric IR + frozen V2
      +--> independent checker
      |
      +--> ACCEPT  -> atomic commit -> new certified state S1
      |
      +--> REFUSE/INVALID/ERROR -> discard candidate -> S0 remains authoritative
```

V0 deliberately gates a complete supported candidate segment before publication.
It does not modify Gala internals or intercept and rewrite intermediate values.

The first implementation demonstrates the authority boundary on the existing
supported regular case. General restart from arbitrary future Gala states is not
claimed unless separately implemented and validated.

## 4. State model

Driver V0 has three semantically distinct state classes.

### certified_state

The only authoritative state. It is immutable once published. It includes:
- canonical state bytes;
- exact source/run binding;
- predecessor certified-state identity;
- acceptance receipt identity;
- content hash;
- monotonically increasing generation number.

### candidate_state

Untrusted pending output from one external run. It must live outside the
certified-state namespace and must not overwrite, alias, or mutate certified
state before acceptance.

### fallback_state

A result produced by a separately approved stronger correctness path after a
candidate refusal. It is still untrusted until it passes the same publication
gate. Driver V0 must not invent a fallback if no approved stronger path exists.

## 5. Authority and publication contract

Only the Driver commit operation may create a new certified state.

Acceptance requires all of the following from the same candidate transaction:
1. source/input binding matches the certified predecessor and approved case;
2. Runtime Trace acquisition is complete for the requested supported segment;
3. final fresh independent checker verdict is CHECKER_PASS;
4. requested_steps == checked_steps and requested_complete is true;
5. candidate output bytes match the checked terminal output;
6. source set/bytes did not change during the transaction;
7. all resource and evidence receipts required by the Runtime Trace contract are
   present and successful;
8. the acceptance receipt itself is written before the certified-state pointer
   changes.

No prefix PASS, stale report, copied receipt, hash-only match, resource EXECUTED
receipt, or producer-only PASS is authority to commit state.

Publication must be atomic from the Driver's point of view. On interruption,
the system must expose either the previous certified state or the fully published
new certified state, never a half-written authoritative generation.

## 6. Refusal, invalidity and failure

Driver V0 is fail-closed.

- Runtime Trace REFUSED -> do not commit candidate.
- independent checker failure or exception -> do not commit candidate.
- unsupported instruction/effect/path -> do not commit candidate.
- trust/source/input binding mismatch -> do not commit candidate.
- malformed/stale/missing evidence -> do not commit candidate.
- resource exhaustion -> do not commit candidate.
- candidate arithmetic/semantic invalidity -> do not commit candidate.
- process crash, timeout or interrupted publication -> preserve last certified
  generation.

A refusal is not automatically a request for exact recomputation.

Fallback is allowed only when a separately registered correctness path explicitly
supports the refusal class and returns a result that can pass this same Driver
publication gate. Otherwise the Driver stops with the previous certified state.

## 7. First V0 scope

In scope:
- one Driver authority boundary over the currently supported regular Gala path;
- isolated pending candidate storage;
- acceptance/refusal state machine;
- immutable certified-state generations;
- atomic publication/recovery;
- binding Runtime Trace CHECKER_PASS to the exact candidate;
- restart from the latest fully committed certified generation;
- explicit STOP when no approved fallback exists;
- fault injection against the authority boundary;
- measured Driver overhead separate from Runtime Trace cost.

Out of scope:
- A repository integration;
- arbitrary programs, initial conditions, CPUs, GPUs or threads;
- changing frozen V2;
- fixing or expanding Independent Impulse;
- universal N-step correctness;
- in-process live steering of Gala;
- silent numerical correction or snapping;
- performance optimization before V0 authority semantics pass;
- new physics benchmark;
- Proof Cache reuse unless explicitly needed and separately designed;
- commit or push without designer authorization.

## 8. Initial implementation shape

Proposed new code lives under `verified_driver/v0/` or an equivalently isolated
new package. Existing Runtime Trace implementation and evidence stay unchanged.

Minimum logical components:
- `state.py`: canonical immutable certified/candidate records;
- `binding.py`: predecessor/input/source/run binding;
- `gate.py`: acceptance predicate using fresh Runtime Trace/checker evidence;
- `store.py`: append-only candidate/certified object store and atomic pointer;
- `driver.py`: transaction orchestration;
- `fallback.py`: registry that defaults to no available fallback;
- dedicated tests and evidence under new names.

The implementation may choose smaller files if it preserves these separations.
File names are not the contract; authority boundaries are.

## 9. Required attack matrix

V0 must include attacks that attempt to cross the authority boundary:
- mutate candidate output by 1 ulp;
- mutate candidate then repair content hashes;
- change candidate evidence while keeping old CHECKER_PASS;
- reuse a previous transaction's acceptance receipt;
- bind candidate A evidence to candidate B;
- skip the independent checker;
- treat REFUSED as ACCEPT;
- publish candidate before checker completion;
- publish fallback without revalidation;
- alter predecessor certified-state identity;
- corrupt or truncate atomic publication;
- crash between object write and certified-pointer update;
- crash immediately after pointer update and verify recovery;
- malformed checker report;
- checker exception/timeout;
- resource refusal;
- source bytes changed during transaction.

Every attack must either leave the prior certified state authoritative or recover
to a fully valid new generation. No attack may expose an unverified generation as
certified.

## 10. Required positive tests

At minimum:
- a normal supported candidate is accepted;
- candidate bytes and checked terminal bytes are identical;
- certified generation increments exactly once;
- restarting the Driver recovers the same certified state;
- re-running a completed transaction does not double-commit;
- Driver disabled/audit-only comparison does not change the candidate result;
- a refused transaction leaves certified bytes and generation unchanged;
- an approved fallback test double, if used only for contract testing, is clearly
  TEST_ONLY and still must pass the publication gate.

A production fallback implementation is not required for V0 unless an already
approved stronger path is found and explicitly bound.

## 11. Completion criterion

Verified Driver V0 is complete only when evidence demonstrates this statement:

> An external candidate result has no authority to change the Driver's certified
> state before fresh independent verification accepts that exact candidate. Any
> refusal, invalidity, checker failure, resource failure or interrupted
> publication preserves the last certified state. Any fallback result is also
> untrusted until independently revalidated.

Test counts alone do not satisfy this criterion.

The final report must separately state:
- what candidate path was actually exercised;
- which attacks were executed and rejected;
- whether any fallback path was production-capable or only TEST_ONLY;
- atomic-recovery evidence;
- measured Driver-only overhead versus existing Runtime Trace cost;
- retained Runtime Trace trust premises and untraced boundaries;
- whether an external independent audit was actually completed.

## 12. Execution discipline

Do not enlarge the Runtime Trace evidence campaign merely to implement V0.
Use the smallest fresh numerical runs that test the authority boundary, then reuse
immutable saved evidence only where the test question is about Driver storage or
transaction semantics rather than fresh numerical correctness.

Any fresh heavy numerical execution remains subject to an explicit resource
ceiling. Free desktop/laptop resources may be used, but their environments and
evidence roles remain separate.

No commit or push is authorized by this design document.
