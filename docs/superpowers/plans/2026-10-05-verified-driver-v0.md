# Verified Driver V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a transactional authority gate so a Gala candidate cannot become certified state before fresh Runtime Trace evidence and the independent checker accept that exact candidate.

**Architecture:** Keep the existing Runtime Trace candidate unchanged. Run a supported Gala segment into an isolated pending transaction, bind its checked terminal output to the same candidate, then atomically publish an immutable certified generation only on ACCEPT. REFUSED, INVALID, checker/resource failure, or interrupted publication preserves the prior certified generation.

**Tech Stack:** Python 3.12, pathlib/dataclasses/hashlib/json/os, existing `runtime_trace.regular_nstep`, pytest, Linux/WSL for the real authority-path run.

**Spec:** `docs/superpowers/specs/2026-10-05-verified-driver-v0-design.md`

## Global Constraints
- Base worktree HEAD: `79a655f0848152aa765e1537b741518b2fa97acf`.
- Runtime Trace N-step candidate is uncommitted input work; do not rewrite or promote its historical evidence.
- Do not modify A, frozen V2, Independent Impulse, Gala wheel, or old Runtime Trace artifacts.
- V0 supports only the existing regular Gala case; no arbitrary initial states or universal program claim.
- Pinned harness SHA-256: `4928f88e4c6255cfbc3f68798648b543146fb5b13327490d331814f778a9fc26`.
- Genesis bits q0,q1,v0,v1: `0x0000000000000000`, `0x0000000000000000`, `0x3fd0000000000000`, `0x3fc0000000000000`.
- Candidate namespace must never alias certified state before ACCEPT.
- Production fallback defaults to STOP. TEST_ONLY fallback must still pass the same gate.
- Fresh numerical work uses the existing approved Runtime Trace ledger; never reset it.
- No paid resources. No commit/push without separate designer authorization.

## Review Focus
- Stale PASS from another transaction must refuse even if output bits match.
- Crash around CURRENT update must recover old or fully written new generation only.
- Genesis must refuse if pinned harness bytes changed.
- Candidate bytes must equal checked terminal q/full_v bits even after repaired hashes.
- Retrying the same completed transaction must not double-commit.

---
### Task 1: Canonical State Model and Regular Genesis

**Files:** Create `verified_driver/__init__.py`, `verified_driver/v0/__init__.py`, `verified_driver/v0/model.py`; test `tests/test_verified_driver_v0_model.py`.

**Interfaces:** Produce frozen `CertifiedState`, `CandidateState`, `GateDecision`, `DriverResult`; `regular_genesis(repo_root: Path) -> CertifiedState`; `canonical_bytes(value) -> bytes`; `content_id(value) -> str`.

- [ ] Write tests `test_regular_genesis_requires_pinned_harness_bytes`, `test_regular_genesis_has_exact_four_initial_bits`, `test_state_content_id_is_canonical_and_stable`, `test_noncanonical_bits_are_rejected`.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_model.py -q`; expected RED because module does not exist.
- [ ] Implement strict canonical JSON/SHA-256 and frozen dataclasses. `CertifiedState.state_bits` is exactly four canonical binary64 hex strings in q0,q1,v0,v1 order.
- [ ] Implement `regular_genesis()`: verify pinned harness SHA, return generation 0 with the four exact genesis bits; do not run Gala to invent genesis.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_model.py tests/test_regular_nstep_public.py -q`; expected PASS.
- [ ] Review only Task 1 diff; no commit.

### Task 2: Append-Only Certified Store and Atomic Recovery

**Files:** Create `verified_driver/v0/store.py`; test `tests/test_verified_driver_v0_store.py`.

**Interfaces:** `CertifiedStore(root: Path)` with `initialize(genesis) -> str`, `current() -> tuple[str, CertifiedState]`, `publish(expected_state_id, state, acceptance_bytes) -> str`, `recover() -> tuple[str, CertifiedState]`. Layout: `objects/<sha>.json`, `receipts/<sha>.json`, `CURRENT`.

- [ ] Write tests for same-genesis idempotence, predecessor mismatch refusal, append-only objects, retry without double-generation, crash-before-pointer, crash-after-pointer, and truncated/unknown CURRENT refusal.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_store.py -q`; expected RED.
- [ ] Implement exclusive content-addressed object/receipt writes. Existing same-address bytes must match exactly or refuse.
- [ ] Implement atomic CURRENT publication: flush object/receipt, write same-directory temp pointer, flush, `os.replace()`, then Linux directory fsync. Inject named crash hooks only for tests.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_model.py tests/test_verified_driver_v0_store.py -q`; expected PASS.
- [ ] Review only Task 2 diff; no commit.

### Task 3: Fresh Runtime Trace Evidence Gate

**Files:** Create `verified_driver/v0/gate.py`; test `tests/test_verified_driver_v0_gate.py`.

**Interfaces:** `candidate_from_evidence(transaction_id: str, predecessor_id: str, evidence_dir: Path) -> CandidateState`; `evaluate_candidate(candidate: CandidateState, predecessor: CertifiedState, repo_root: Path) -> GateDecision`. Parse with stdlib JSON/hashlib/pathlib; do not import the Runtime Trace producer or frozen V2 evaluator as an oracle.

- [ ] Build a passing-control fixture from the delivered 10-step evidence: `run_result.json`, `integration_source_pinset.json`, `fresh_checker_report.json`, `capture/harness_output.json`, `derived/completion.json`, and three stage `execution.json` receipts.
- [ ] Pin the passing output bits: `0x3fa3eaff7788ac22`, `0x3f93eacc1b020e3a`, `0x3fcf9999a5c32ae6`, `0x3fbf984cad4b103f`.
- [ ] Add RED tests for stale checker reuse, 1-ulp output mutation with repaired hashes, wrong predecessor, wrong harness binding, prefix/false completion, failed resource receipt, completion digest mismatch, duplicate JSON keys/nonfinite JSON.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_gate.py -q`; expected RED.
- [ ] Implement strict gate checks: both reports CHECKER_PASS; exact integer requested==checked; requested_complete true; completion digest recomputes; harness output has four canonical bits; completion q offsets 0/8 then full_v offsets 0/8 equal those bits; source-pinset SHA matches run result and pinned harness SHA; stage receipt hashes match and each verdict is EXECUTED without resource failure.
- [ ] Bind acceptance to transaction ID, predecessor ID, candidate ID, completion SHA, source-pinset SHA, requested steps, and output bits. First V0 accepts only the regular genesis predecessor contract.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_gate.py tests/test_regular_nstep_public.py tests/test_regular_nstep_pipeline.py -q`; expected PASS.
- [ ] Review only Task 3 diff; no commit.

### Task 4: Transaction Orchestrator and STOP-Default Fallback

**Files:** Create `verified_driver/v0/fallback.py`, `verified_driver/v0/driver.py`; test `tests/test_verified_driver_v0_driver.py`.

**Interfaces:** `FallbackRegistry.resolve(reason: str, context: dict) -> CandidateState | None` defaults to `None`. `VerifiedDriver(repo_root, store, pending_root, ledger, fallback=None)` provides `transact(steps: int, transaction_id: str | None = None) -> DriverResult` and `audit_only(steps: int, out: Path) -> CandidateState`.

- [ ] Write RED tests with a fake Runtime Trace runner for: candidate not authoritative before gate; ACCEPT commits once; REFUSED/checker exception/resource refusal preserve bytes+generation; same transaction retry idempotent; audit_only never moves CURRENT; no fallback => STOP.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_driver.py -q`; expected RED.
- [ ] Implement transaction isolation under `pending/<transaction_id>/`, recording predecessor and source binding before Runtime Trace starts.
- [ ] Implement runner -> candidate extraction -> gate -> acceptance receipt -> store.publish. Never publish on non-ACCEPT.
- [ ] Keep production fallback registry empty. A TEST_ONLY fallback double may be used in tests but must return a candidate that goes through the same gate before publish.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_model.py tests/test_verified_driver_v0_store.py tests/test_verified_driver_v0_gate.py tests/test_verified_driver_v0_driver.py -q`; expected PASS.
- [ ] Review only Task 4 diff; no commit.

### Task 5: Authority-Boundary Mutation and Crash Matrix

**Files:** Create `tests/test_verified_driver_v0_attacks.py`; create `verified_driver/v0/attack_support.py` only if helpers cannot stay in tests. If an attack exposes a real defect, invoke `superpowers:systematic-debugging` before fixing production code.

**Interfaces:** Exercise the full Driver API and assert both verdict and authoritative CURRENT identity/generation.

- [ ] Add attacks: 1-ulp candidate mutation; repaired hashes; stale PASS; candidate-A evidence on candidate-B; checker skipped; REFUSED forced to ACCEPT; publish-before-check; fallback without revalidation; predecessor swap; truncated pointer; crash before pointer replace; crash just after replace; malformed checker report; checker timeout/exception; resource refusal; source change during transaction.
- [ ] For every attack assert either prior certified state remains authoritative or recovery yields a fully valid new generation. No partial/unverified generation may be CURRENT.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_attacks.py -q`; expected all controls PASS and all mutants detected/refused.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_*.py tests/test_regular_nstep_public.py tests/test_regular_nstep_pipeline.py tests/test_regular_nstep_resources.py -q`; expected PASS.
- [ ] Preserve attack evidence under a new Driver-only validation path; do not rewrite Runtime Trace artifacts.
- [ ] Review only Task 5 diff; no commit.

### Task 6: Fresh Linux Authority Run, Cost Receipt, Review, Final Report

**Files:** Create `current/VERIFIED_DRIVER_V0_2026-10-05.md`; create new evidence only under `verified_driver/v0/artifacts/<run-id>/`.

**Interfaces:** Consume final V0 implementation; produce one fresh real accepted transaction, one controlled refusal that preserves CURRENT, source/preservation receipts, Driver-only cost data, and final review report.

- [ ] Record pre-run Git HEAD/status plus hashes of spec, plan, all Driver sources, selected Runtime Trace sources, frozen V2, pinned Gala wheel, protected inventory and unrelated uncommitted files. Do not clean the worktree.
- [ ] Check the existing cumulative resource ledger. If remaining allowance is insufficient, stop with `REFUSED_RESOURCE`; never reset/replace the ledger.
- [ ] In Linux/WSL run the smallest real full authority transaction, initially `steps=1`. Expected: candidate stays pending until CHECKER_PASS; Driver commits generation 0->1 exactly once; certified output bits equal the checked harness terminal bits.
- [ ] Run one controlled non-heavy refusal and verify generation/state bytes do not change.
- [ ] Measure Driver bookkeeping/gate/store overhead separately from Runtime Trace cost where possible. Mark inseparable cost as inseparable, never subtract guessed values.
- [ ] Run `python -m pytest tests/test_verified_driver_v0_*.py tests/test_regular_nstep_public.py tests/test_regular_nstep_pipeline.py tests/test_regular_nstep_raw.py tests/test_regular_nstep_resources.py -q`; expected PASS.
- [ ] Recompute preservation inventories; old Runtime Trace artifacts, frozen V2, Gala wheel, Impulse source and unrelated uncommitted files must be unchanged.
- [ ] Invoke `superpowers:requesting-code-review`. Reviewer focus: authority boundary, stale-evidence binding, atomic publication/recovery, fallback revalidation. Do not label this external independent audit unless an actual external audit occurred.
- [ ] Write `current/VERIFIED_DRIVER_V0_2026-10-05.md` answering: did any unverified candidate become authoritative; exact real path exercised; attacks rejected; REFUSED/checker/resource/crash behavior; fallback status; recovery evidence; Driver-only cost; retained UNTRACED/trust boundaries; external audit status; commit/push status.
- [ ] Present final report, tests, reviewer findings, Git diff/status, and limitations. Stop before commit/push.

## Self-Review Notes

- Spec coverage: Tasks 1-6 cover immutable state, pending isolation, fresh evidence binding, atomic publication, fail-closed behavior, STOP-default fallback, attack matrix, real authority-path evidence, cost reporting and retained Runtime Trace limits.
- Type consistency: Task 1 defines all state/result records; Task 2 consumes CertifiedState; Task 3 produces CandidateState/GateDecision; Task 4 is the sole publication orchestrator; Tasks 5-6 only use those public interfaces.
- Review-focus coverage: stale PASS and output mismatch are Task 3; crash recovery is Task 2/5; genesis mismatch is Task 1; idempotent retry is Task 4.
- Scope control: no arbitrary-state continuation, no A integration, no tracer generalization, no production fallback requirement, no performance optimization before authority semantics pass.
- Commit rule: this plan intentionally replaces the generic frequent-commit convention with explicit no-commit/no-push until designer authorization.
