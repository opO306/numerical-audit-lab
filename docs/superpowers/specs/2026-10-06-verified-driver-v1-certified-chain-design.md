# Verified Driver V1 Certified-State Chaining Design

Date: 2026-10-06 (Asia/Seoul)

Status: DESIGN DRAFT FOR DESIGNER REVIEW / NOT IMPLEMENTED / NOT AUDITED

## 1. Purpose

Extend Verified Driver V0 from one accepted Gala candidate into a live certified
chain:

```text
S0 -> candidate step1 -> verify -> certify S1
   -> resume same Gala process
   -> candidate step2 -> verify -> certify S2
   -> resume
   -> candidate step3 -> verify -> certify S3
```

No unverified next numerical body may execute.

V1 remains the same regular Henon-Heiles product path. It does not add arbitrary
program support, A integration, Independent Impulse work, production fallback,
multi-core optimization, neural control, or compute-budget evolution.

## 2. Baseline

Implementation baseline is current branch `codex/runtime-trace` at
`eada258f77a1759a521821c1233ea523057b5c2f`.

That commit already contains the Runtime Trace finite-N candidate and Verified
Driver V0. V0 demonstrated one fresh N=1 authority transaction and atomic
certified-state publication.

V1 must preserve V0 evidence and historical Runtime Trace artifacts. Existing
V0/Runtime Trace claims remain conditional on their original contracts.

Retained limitations include:
- init-return -> step1-entry remains UNTRACED;
- native terminal frontier -> Python wrapper tail remains UNTRACED;
- initial allocation/root assumptions remain inherited;
- GDB/collector/OS execution truth remains a trust premise;
- physical trajectory correctness, universal inputs/programs, formal
  certification, and external audit closure remain unproven.

## 3. Why q/v-only restart is forbidden

V0's authoritative state contains four public output lanes: q0, q1, v0, v1.
That is enough for V0 publication but not enough to claim exact continuation of
the already-running Leapfrog native execution.

Existing Runtime Trace evidence shows step-to-step continuation also carries
`q`, `full_v`, and `latent` state plus the accumulated V2 Form state.
The caller corridor prepares the next entry, including gradient reset and
represented t/dt inputs.

Therefore V1 must not reconstruct a continuation by taking only q/v and calling
the public Gala API again. Such a restart is a different execution contract.

## 4. Chosen architecture: persistent inferior with certified entry barriers

Use one original Gala inferior process for the live chain. GDB/controller pauses
that process at each next-step native entry before the next body executes.

The barrier after completed step k is the entry boundary of step k+1:

```text
body(k)
  -> actual caller corridor k -> k+1
  -> BREAK BEFORE body(k+1)
  -> flush/snapshot evidence
  -> independent verification
  -> atomic certified commit Sk
  -> only then RESUME body(k+1)
```

This barrier includes the actual q/full_v/latent handoff, gradient reset,
represented t/dt entry values, and accumulated Form transfer.

For the final requested step, the terminal native corridor is checked before
publishing the final certified state. The existing Python wrapper tail remains
untraced and is not silently promoted into the certified boundary.

The existing batch `runtime_trace.regular_nstep` path remains unchanged.
V1 gets a separate live-session path rather than mutating historical batch
evidence or weakening its completion contract.
## 5. Certified continuation state

V1 introduces a continuation certificate distinct from V0's four-lane public
state. A certified generation must bind all information needed to prove the next
entry belongs to the just-verified chain.

At minimum it records:

- generation and certified step index;
- public q0/q1/v0/v1 output bits;
- q/full_v/latent entry/exit lane bits required by the next native entry;
- gradient entry status, which for the supported path must be the observed exact
  zero reset;
- represented t and dt bits for the next entry when a next entry exists;
- all carried q/full_v/latent V2 Forms, including center, four coefficients, box,
  a process-independent basis contract (K=4, computed-minus-true, no reseed),
  the live basis namespace as provenance, and source state identities;
- predecessor certified-state ID;
- acquisition/session identity;
- process identity for the live receipt;
- trace prefix identity and verified frontier;
- source pinset identity;
- checker acceptance receipt identity;
- barrier kind: `NEXT_STEP_ENTRY` or `FINAL_TERMINAL`.

Raw process-local addresses and the acquisition-specific basis namespace may be
included in the live evidence receipt, but they are not cross-process semantic
identity. Replay on a new process compares logical roles, bits, Form
coefficients/boxes, the basis contract, t/dt and certified lineage; it must not
require the same virtual addresses or acquisition namespace. The currently
observed native coefficients are zero, so V1 does not claim cross-process native
nonzero-coefficient basis equivalence.

A V1 generation is authoritative only when both the V0-style public output state
and the continuation certificate are atomically published.

## 6. Live acquisition and pause/resume handshake

The live inferior must not continue because a file happened to appear or because
a writable directory changed. Resume authority belongs only to the trusted
Driver controller.

The live acquisition path must:

1. launch the pinned original Gala program under one controlled GDB/inferior
   session;
2. collect the init and numerical body/caller rows as today;
3. stop before body(k+1) executes;
4. flush the append-only trace and emit a bounded checkpoint descriptor;
5. remain stopped while verification runs in separate checker processes;
6. accept a single-use controller resume token bound to the exact accepted
   generation;
7. resume only after the certified store atomically publishes that generation.

The resume channel should be a controller-owned pipe or equivalently exclusive
local IPC, not an unauthenticated polling file.

Every barrier receives a unique monotonic sequence number. Replayed, stale,
duplicated, skipped, or future resume tokens refuse.

## 7. Immutable checkpoint snapshot

The live master trace may continue growing after a barrier, so a checker must not
read an unstable moving file.

At each pause:

- flush and fsync the current trace;
- record the exact prefix byte length and chain hash;
- copy or materialize that exact prefix into a new immutable checkpoint
  directory;
- bind capture metadata, process/session identity, source snapshot, step index,
  current barrier state and previous certified-state ID;
- seal the checkpoint before running producer/checker work.

Later live writes may append to the master trace but may not change any verified
prefix bytes. A prefix mutation after certification is a fatal session error.

## 8. Incremental verification contract

V1 must not fake per-step approval by running the whole N-step job to completion
and revealing old results one at a time.

A new incremental verifier consumes:

```text
previous certified continuation certificate
+
new live trace segment
+
current next-step-entry or final-terminal snapshot
```

and independently verifies only the new authority edge while checking the
predecessor certificate chain.

For a non-final barrier k -> k+1 it verifies:

- actual body(k) machine/IR/V2 correspondence;
- actual caller(k,k+1) control and memory effects;
- q/full_v/latent exact dynamic carry;
- gradient reset evidence;
- t/dt provenance;
- V2 Form propagation from the previous certified Forms;
- unique process/session and monotonic trace sequence;
- that body(k+1) has not executed before acceptance.

For the first edge, the existing conditional accepted init->step1 premise is
retained. It is not relabeled as newly traced.

For the final edge it verifies body(N) plus the terminal native output-store
corridor and binds public q/v output to the certified final generation.

The new checker must remain independent of the production incremental producer
in the same sense as the current checker: no production evaluator may serve as
the numerical oracle.

## 9. Authority ordering

The required order at every barrier is:

```text
PAUSE
-> seal checkpoint
-> verify
-> write acceptance receipt
-> write certified object
-> atomically move CURRENT
-> issue resume token
-> RESUME
```

The following orders are forbidden:

- resume before checker PASS;
- resume after PASS but before CURRENT publication;
- publish a state after observing the next body already execute;
- reuse a prior generation's receipt to resume;
- change candidate bytes or Forms between verification and publication.

A failure before resume leaves the current inferior stopped and the previous
certified generation authoritative.

## 10. Failure behavior

V1 is fail-closed.

On any of these conditions, do not resume the numerical body:

- incremental checker REFUSED;
- malformed/missing/stale evidence;
- source binding change;
- candidate/Form/latent mismatch;
- wrong predecessor generation;
- unsupported instruction/effect;
- resource refusal;
- checker exception or timeout;
- checkpoint sealing failure;
- resume-token mismatch;
- store publication failure;
- controller uncertainty about whether publication completed.

Production fallback remains absent. The result is STOP at the last certified
generation.

If the current inferior cannot be proven to still be paused at the accepted
barrier, terminate that live session rather than guessing its state.
## 11. Controller death and process containment

The live Gala inferior must never continue as an orphaned uncontrolled train.

The controller, GDB, inferior, and live trace writer must run inside an execution
containment that proves the following property in tests:

> if the Driver/controller authority process dies or loses control of the live
> session, the numerical inferior cannot continue executing new bodies.

The implementation may use the existing systemd/cgroup model plus an explicit
supervisor, parent-death signal, or equivalent mechanism. The exact mechanism is
an implementation choice, but the property is part of the V1 contract and must
be tested with real process termination.

A test that merely checks Python object cleanup is insufficient.

## 12. Crash recovery: replay, not state injection

V1 does not claim arbitrary internal Gala-state injection after a process crash.

If a live session is lost after certified generation Sk:

1. read and verify the complete certified chain through Sk;
2. start a fresh pinned Gala process from the original regular genesis;
3. drive it through the same barrier sequence in REPLAY mode;
4. at each stored generation compare the fresh logical continuation boundary to
   the stored certified state: q/full_v/latent bits, Form coefficients/boxes and
   basis contract, gradient rule, t/dt, source binding, and step index; do not
   require the same process-local addresses or acquisition-specific namespace;
5. do not create duplicate certified generations while replaying;
6. if every boundary through Sk matches, stop at the Sk continuation barrier;
7. switch that newly reproduced process into LIVE mode and allow the next new
   candidate segment.

Any replay mismatch causes STOP. V1 does not patch memory to force the new
process to match the old certificate.

Replay may use new process-local addresses and acquisition identity. Those are
new evidence, not a failure by themselves.

## 13. V1 first supported experiment

The first real V1 experiment is deliberately small:

- same regular Henon-Heiles case;
- same pinned Gala/Linux x86-64/CPython environment;
- represented dt = 1/64;
- one original live Gala process;
- requested N=3;
- three certified generations after genesis.

Expected live authority sequence:

```text
genesis S0
-> run body1/caller1-2
-> pause before body2
-> verify -> commit S1
-> resume body2/caller2-3
-> pause before body3
-> verify -> commit S2
-> resume body3/terminal
-> verify -> commit S3
-> finish
```

The final S3 public q/v bits must equal the original unmodified Gala N=3 output
for the same pinned case. This equality is a control, not a substitute for
trace/checker evidence.

After the positive N=3 chain, run a separate fault-injection live session with
requested N=4. Accept S1 and S2, run body3/caller3-4, pause before body4, then
corrupt or invalidate the third candidate edge before certification. Prove:

```text
CURRENT == S2
body4 did not execute
session stopped
```

This negative N=4 run exists only to prove the live barrier blocks forward
execution. No 10/100-step V1 campaign is required for initial V1 completion.

## 14. Required attacks

V1 must include at least these authority attacks:

- alter one q/full_v/latent lane after checkpoint sealing;
- alter one carried Form coefficient or box;
- reset a carried Form to zero;
- attach S1's acceptance receipt to S2;
- splice a checkpoint from another process/session;
- skip one barrier sequence number;
- duplicate a resume token;
- send a stale resume token;
- attempt resume before checker completion;
- attempt resume after checker PASS but before CURRENT publication;
- mutate the live master trace inside an already-certified prefix;
- execute body(k+1) before generation k is published;
- change t or dt provenance;
- omit/alter gradient reset evidence;
- crash the checker;
- kill the Driver/controller while the inferior is paused;
- kill the Driver/controller immediately after CURRENT replacement;
- replay from genesis with one stored continuation certificate altered;
- replay with equal q/v but wrong latent/Form;
- try to create a new generation during replay;
- retry an already committed barrier transaction.

Every negative case must preserve the last valid certified generation and prevent
unverified forward numerical execution.

## 15. Positive tests and completion criterion

V1 is complete only when fresh evidence demonstrates all of the following:

1. one original Gala process produced at least three sequential certified
   generations S1, S2, S3;
2. body(k+1) did not execute before generation k was atomically certified;
3. q/full_v/latent and carried Forms were preserved across each accepted edge;
4. S1/S2/S3 form one immutable predecessor chain;
5. a third-edge failure leaves CURRENT at S2 and prevents forward execution;
6. controller death cannot leave the numerical inferior running uncontrolled;
7. restart/replay from genesis reproduces the last certified continuation
   boundary and does not create duplicate generations;
8. the final N=3 public output matches the ordinary original Gala N=3 control;
9. retained Runtime Trace trust and UNTRACED boundaries remain explicitly
   reported;
10. tests, evidence, and review distinguish internal/fresh review from any
    external independent audit.

A loop counter, successful pause command, or three JSON files alone are not V1
completion evidence.

## 16. Resource and performance discipline

Correct authority ordering is the V1 goal. Performance optimization is not.

The current shared numerical ledger must be checked before fresh heavy work. Do
not reset or silently enlarge it. If the remaining historical allowance is too
small for implementation validation, the implementer must report the required
additional ceiling before heavy execution rather than quietly consuming a new
budget.

Measure separately where practical:

- live body/caller acquisition time;
- checkpoint sealing time;
- incremental producer time;
- independent checker time;
- certified store publication time;
- paused wall time per barrier;
- replay recovery time.

Do not claim that V1 is faster than V0 or batch Runtime Trace without repeated
measurements.

## 17. Explicitly deferred work

The following is not part of V1:

- multi-core role allocation;
- parallel independent checkers;
- adaptive CPU/memory/time budgets;
- neural controllers;
- evolutionary search over numerical strategies;
- compute-resource starvation experiments;
- performance tuning of GDB/trace serialization;
- production exact/rigorous fallback;
- arbitrary program or initial-condition support;
- arbitrary certified-state memory injection;
- GPU/SIMD support;
- A-world integration;
- Independent Impulse changes.

The multi-core and compute-budget/evolution idea is retained as a separate
post-V1 research direction. V1 should expose per-barrier timing/resource
measurements so that later work has an observable metabolism to optimize.

## 18. Implementation isolation

Prefer a new package such as `verified_driver/v1/` and a separate live-trace
namespace. Reuse V0 store/model primitives only where their semantics remain
valid; do not mutate V0 evidence or reinterpret V0 four-lane states as full V1
continuation certificates.

Existing `runtime_trace/regular_nstep/` batch behavior and its historical
artifacts must remain byte-stable unless a separately justified compatibility
fix is required and reviewed.

No commit or push is authorized by this design document.

## 19. Final reporting

The final V1 report must answer, in plain language:

- Did one original Gala process actually stop and resume between verified steps?
- How many certified generations were produced?
- Did any next numerical body execute before its predecessor was certified?
- Were q/full_v/latent and Forms carried and independently checked?
- What happened when the third edge was deliberately invalid?
- What happened when the controller was killed?
- Did replay from genesis reproduce the last certified boundary?
- What were the per-barrier and total costs?
- Which UNTRACED/trust assumptions remain?
- Was any external independent audit actually completed?
- Were commit/push performed, and under whose explicit authorization?
