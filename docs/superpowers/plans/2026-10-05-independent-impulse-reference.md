# Independent Impulse V1 Reference Implementation Plan

> Execution: implement in this session, test first. The user's explicit implementation request supersedes the skill's extra plan approval, commit, and worktree steps. No commit or push. No delegated implementation or independent audit is claimed.

**Goal:** Independently enclose the approved point impulse and resolve its whole signed96 nearest-even vector in author reference checks.

**Architecture:** Frozen data loader → bounded exact rational primitives → analytic potential/derivative → point impulse → cell decision → private compact certificate. The runtime entry stops at POLICY_UNBOUND; author reference evaluation has an explicit, separate internal parameter object, without registering a production budget or publishing a point proof.

**Tech Stack:** Python standard library integers/Fraction/isqrt/hashlib/JSON; pytest. mpmath only in test diagnostics, never a proof primitive.

**Spec:** specs/c1b1-independent-impulse-v1/semantic-bundle.json and its seven pinned dependencies; human B1–B8 norms; audit target 8e5865964770b3752326d361276cbccd125c547a.

## Global Constraints

- Ar40; position FX(96,48); momentum/impulse FX(96,80); full_dt=40; kick_fraction=1/2.
- Admission before nonlinear/zero work; exact segment plus stored final point contract remains frozen.
- No executor, Arithmetic, V2, A-EV, Candidate B primitive imports or copied implementation.
- No spec bytes changes; preserve protected Arithmetic eight files and all historical evidence.
- RESOLVED is private; no PUBLISHED/ACCEPTED/J_VERIFIED. Runtime activation remains false.
- No numeric production instance, allocator byte majorant, OS enforcement, V2 call or full KDK integration in this stage.

## Review Focus

Malformed wire before integer conversion; coarse radius lower zero; mixed-sign interval extrema; asymmetric overflow and opposite raw; budget exhaustion/partial vector publication. Pin each in the corresponding tests below.

### Task 1: Primitive enclosures and resource structure

Create interval.py, resource.py, sqrt_enclosure.py, exp_enclosure.py, rounding.py and tests/test_impulse_reference_primitives.py. Interfaces: Interval(lo,hi), checked exact operations, sqrt_enclosure(R2,N,ctx), exp_enclosure(x,P,order_max,ctx), decide_scaled(interval). No implicit interval repair.

- [ ] Write and run RED tests for sign corners, reciprocals/powers, perfect/non-square radius, coarse zero, exp zero/small/large/tail, even/odd ties, signed overflow, pre-operation bit/work/order limits.
- [ ] Implement only the approved formulas; rerun GREEN and preserve logs.

### Task 2: Physical binding and independent formula

Create spec.py, contracts.py, domain.py, identity.py, potential.py, derivative.py, policy.py. Interfaces: load_spec(), validate_input(bytes), admit(q), evaluate_terms(R,N/P controls), deterministic attempts, independent identities. Test: tests/test_impulse_reference_model.py.

- [ ] RED tests for domain before zero, state/grid/spec/phase validation, no external J, identity separation, exact BO i=-1/g-prime/REL branch/TT identities and diagnostic derivative comparison.
- [ ] Implement using only pinned nominal constants and the approved mathematical expressions; rerun GREEN.

### Task 3: Whole-vector producer and compact private proof

Create producer.py, certificate.py, wire.py and tests/test_impulse_reference_producer.py. Interfaces: evaluate_reference(input_bytes, ReferencePolicy) for author use; produce(input_bytes) returns bounded runtime refusal while activation is absent. PrivateResult contains all three raw lanes or none, common opposite vector, compact certificate bytes, author-only intervals/counters.

- [ ] RED tests for all-resolved physical state, exhausted policy, one-lane ambiguity/overflow, unchanged input/state, Failure enum/null and digit/byte boundaries, compact certificate/binding, runtime unbound refusal.
- [ ] Implement complete-vector resolution, deterministic refinement anomaly checks, bounded errors and private construction; rerun GREEN.

### Task 4: Evidence and actual mutations

Create audit/c1b1-impulse-reference-2026-10-05/run_mutants.py plus explicit source edit catalog. Run semantic mutants against independent primitive expectations and nondegenerate physical diagnostic fixtures. Do not count source hash mismatch as semantic detection. Mark deferred rechecker/composition mutants honestly.

- [ ] Capture baseline PASS and actual isolated source mutant results.
- [ ] Run reference tests and repository suite; preserve every failing run.
- [ ] Record source/dependency hashes, certificate examples, known UNPROVED and runtime gates.
- [ ] Verify pinned spec/Arithmetic/history bytes and no commit/push; author self-review only.

## Progress and decisions

Ruling: ReferencePolicy is an internal author-test control, not a normative Budget instance or activation decision. It exercises implementation methods under the user's requested author checks; the external wire producer always remains POLICY_UNBOUND. No allocator bytes-per-bit rule is invented. Allocator/worker verification and independent nonlinear recheck remain activation gates.
