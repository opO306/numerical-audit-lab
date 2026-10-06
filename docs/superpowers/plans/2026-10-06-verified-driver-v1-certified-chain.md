# Verified Driver V1 Certified-State Chaining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one original Gala process stop at every certified entry barrier, independently verify the just-finished numerical edge, atomically certify it, and only then allow the next numerical body to execute.

**Architecture:** Add a separate `runtime_trace/live_chain/` live-session path and `verified_driver/v1/` authority layer without changing historical V0 or batch Runtime Trace behavior. The live GDB inferior pauses before each next numerical body, seals an immutable trace-prefix checkpoint, waits while an incremental producer and independent checker verify the edge, then resumes only after the V1 store has atomically published the accepted continuation certificate. Crash recovery replays from genesis; replay may change process-local addresses/namespaces but live tokens remain strictly session/barrier/generation bound.

**Tech Stack:** Python 3.12, GDB Python API, Linux pipes/process groups, pathlib/dataclasses/hashlib/json/os, existing frozen V2 and audited checker primitives, pytest, WSL Ubuntu/Linux x86-64.

**Spec:** `docs/superpowers/specs/2026-10-06-verified-driver-v1-certified-chain-design.md`

## Global Constraints

- Baseline branch/HEAD: `codex/runtime-trace` at `eada258f77a1759a521821c1233ea523057b5c2f`.
- Do not modify or reinterpret V0 evidence; V0 four-lane states are not V1 full continuation certificates.
- Prefer new code under `verified_driver/v1/` and `runtime_trace/live_chain/`; existing `runtime_trace/regular_nstep/` behavior/artifacts remain byte-stable unless a separately justified compatibility fix is reviewed.
- Same pinned regular Henon-Heiles case, Gala/Linux x86-64/CPython environment and represented dt=1/64 only.
- Preserve q/full_v/latent, gradient reset evidence, t/dt, carried Forms, predecessor lineage and barrier identity.
- Replay namespace/address relaxation applies only to semantic comparison. Live checkpoint/resume-token binding is strict to session, barrier sequence, predecessor generation, candidate generation and checkpoint identity.
- Production fallback remains absent; failure means STOP at the store-proven last certified generation.
- No multi-core optimization, neural controller, evolution/resource-starvation experiment, A integration, Impulse work, GPU support or arbitrary state injection.
- Shared numerical ledger currently records 2936.687093598022 / 3600 seconds used, leaving 663.3129064019781 seconds. Re-read it before heavy execution; never reset or silently replace it. If real V1 validation needs more, stop and request a new ceiling.
- No paid resources.
- No commit/push unless the designer separately authorizes it. Per-task completion means tests/review only.

## Review Focus

- **Post-CURRENT/pre-resume crash:** recover the fully valid new generation, not the predecessor, while still forbidding forward execution before recovery.
- **Replay terminal semantics:** `FINAL_TERMINAL` recovery must never create a new numerical body or generation.
- **Live-vs-replay namespace confusion:** replay may ignore process-local namespace/address identity, but live tokens/checkpoints must never cross sessions/barriers.
- **Orphan execution:** controller loss during a paused barrier or active body must prevent entry into the next uncertified body.
- **Equal public q/v with wrong hidden continuation:** wrong latent/Form/t-dt/gradient state must refuse even when public output bits match.

---
### Task 1: V1 Continuation Certificate and Atomic Chain Store

**Files:**
- Create: `verified_driver/v1/__init__.py`
- Create: `verified_driver/v1/model.py`
- Create: `verified_driver/v1/store.py`
- Test: `tests/test_verified_driver_v1_model.py`
- Test: `tests/test_verified_driver_v1_store.py`

**Interfaces:**
- Produce `FormLane(center_bits: str, coefficients: tuple[str,str,str,str], box: str, source_state_id: str, component: str, byte_offset: int)`.
- Produce frozen `ChainState` with fields: `generation`, `step_index`, `requested_steps`, `barrier_kind`, `public_bits`, `q_bits`, `full_v_bits`, `latent_bits`, `gradient_bits`, `next_t_bits`, `dt_bits`, `forms`, `basis_contract`, `live_basis_namespace`, `source_binding`, `trace_prefix_sha256`, `trace_prefix_bytes`, `verified_frontier`, `predecessor_id`, `acceptance_id`, `live_session_id`, `process_identity_digest`, `barrier_seq`.
- `barrier_kind` is one of `GENESIS`, `NEXT_STEP_ENTRY`, `FINAL_TERMINAL`.
- Produce `ChainResult(verdict, run_id, state_id, generation, step_index, reason)`.
- Produce `chain_genesis(repo_root: Path, requested_steps: int) -> ChainState`.
- Produce `ChainStore(root: Path)` with `initialize(genesis)`, `current()`, `publish(expected_state_id, state, acceptance_bytes)`, `recover()`.

- [ ] Write RED tests that reject malformed lane counts, noncanonical binary64 bits, wrong Form coefficient count, NaN/Inf state, invalid barrier sequencing, generation/step mismatch, and a non-pinned genesis harness.
- [ ] Write RED store tests for append-only objects/receipts, predecessor mismatch, idempotent retry, CURRENT corruption, crash before CURRENT replace, valid CURRENT replace followed by crash, and uncertain replacement recovery.
- [ ] Run `python -m pytest tests/test_verified_driver_v1_model.py tests/test_verified_driver_v1_store.py -q`; expected RED.
- [ ] Implement strict model validation. Generation 0 is `GENESIS`; a `NEXT_STEP_ENTRY` generation must have two q/full_v/latent lanes, exact-zero gradient lanes, next t, dt and exactly six carried Form lanes. `FINAL_TERMINAL` has no next t requirement and cannot authorize a successor.
- [ ] Implement a new V1 store without modifying V0 store bytes. Reuse the V0 atomic pattern conceptually: fsynced content-addressed receipt/object, same-directory temporary CURRENT, `os.replace`, directory fsync.
- [ ] Make recovery obey the approved table: pre-replace keeps predecessor; a fully valid post-replace generation remains authoritative; ambiguous CURRENT is resolved only by validating complete object/receipt/lineage, never guessed.
- [ ] Run Task 1 tests plus `tests/test_verified_driver_v0_store.py`; expected PASS and no V0 regression.
- [ ] Review Task 1 diff only; no commit.

### Task 2: Barrier Protocol, Resume Tokens, and Immutable Checkpoints

**Files:**
- Create: `runtime_trace/live_chain/__init__.py`
- Create: `runtime_trace/live_chain/protocol.py`
- Create: `runtime_trace/live_chain/checkpoint.py`
- Test: `tests/test_live_chain_protocol.py`
- Test: `tests/test_live_chain_checkpoint.py`

**Interfaces:**
- Produce `BarrierEvent(session_id, barrier_seq, completed_step, barrier_kind, requested_steps, process_identity, trace_prefix_bytes, trace_prefix_sha256, trace_chain_hash, predecessor_id, checkpoint_state)`.
- Produce `ResumeToken(session_id, barrier_seq, predecessor_generation, candidate_generation, checkpoint_id, state_id, nonce)`.
- Produce `TokenLedger.issue(...) -> ResumeToken` and `TokenLedger.consume(token, expected_...) -> None`; consumption is single-use.
- Produce `CheckpointSealer(root: Path).seal(master_trace: Path, event: BarrierEvent, metadata: dict, out: Path) -> str`, returning checkpoint content ID.

- [ ] Write RED tests for stale/duplicate/future/foreign-session resume tokens, wrong generation, wrong checkpoint ID and token reuse.
- [ ] Write RED checkpoint tests proving only the declared trace prefix is copied, fsynced/sealed, later append does not change it, prefix mutation is detected, symlink/path escape is refused, and metadata binds predecessor/session/barrier/source snapshot.
- [ ] Run `python -m pytest tests/test_live_chain_protocol.py tests/test_live_chain_checkpoint.py -q`; expected RED.
- [ ] Implement canonical JSON-line protocol records and single-use token ledger. No polling file may itself authorize resume.
- [ ] Implement immutable checkpoint sealing with exact prefix byte length + SHA-256 + chain hash and exclusive destination creation.
- [ ] Run Task 2 tests; expected PASS.
- [ ] Review Task 2 diff only; no commit.

### Task 3: Persistent Gala/GDB Live Session with Entry Barriers

**Files:**
- Create: `runtime_trace/live_chain/gdb_live.py`
- Create: `runtime_trace/live_chain/session.py`
- Create: `runtime_trace/live_chain/harness.py`
- Test: `tests/test_live_chain_session.py`

**Interfaces:**
- `LiveGalaSession(repo_root: Path, run_root: Path, requested_steps: int, ledger: Path)`.
- Methods: `start() -> BarrierEvent`, `resume(token: ResumeToken) -> BarrierEvent`, `finish(token: ResumeToken | None) -> dict`, `terminate(reason: str) -> None`, `is_paused_at(event: BarrierEvent) -> bool`.
- Controller↔GDB communication uses controller-created anonymous pipes passed as FDs: event pipe child→controller, command pipe controller→child. The GDB side never derives resume authority from writable evidence files.

- [ ] Write RED session tests with a deterministic fake inferior: first event occurs before body2, resume token permits exactly one next body, stale/duplicate token refuses, and FINAL_TERMINAL does not accept a resume token for a new body.
- [ ] Add a GDB-script unit test that proves barrier sequence ordering and that the breakpoint is hit before the next body instructions are executed.
- [ ] Run `python -m pytest tests/test_live_chain_session.py -q`; expected RED.
- [ ] Implement a new live harness by parameterizing the original pinned harness without changing the old file or Gala calculation. Pin executed-source proof exactly as current Runtime Trace does.
- [ ] Implement `gdb_live.py` by reusing reviewed acquisition/semantic helpers while maintaining one inferior. After body(k)+caller(k,k+1), stop at step(k+1) entry and emit a barrier event before any body(k+1) instruction. Final step emits `FINAL_TERMINAL` after the checked native terminal corridor.
- [ ] Implement `LiveGalaSession` pipe framing, timeouts, state machine and fail-closed termination. It must refuse out-of-order commands and prove the inferior is still paused before accepting a token.
- [ ] Run Task 3 tests plus existing `tests/test_regular_nstep_acquisition.py`; expected PASS without historical behavior changes.
- [ ] Review Task 3 diff only; no commit.

### Task 4: Incremental Edge Producer and Independent Checker

**Files:**
- Create: `runtime_trace/live_chain/schema.py`
- Create: `runtime_trace/live_chain/producer.py`
- Create: `runtime_trace/live_chain/checker.py`
- Test: `tests/test_live_chain_incremental.py`

**Interfaces:**
- `build_edge(checkpoint_dir: Path, predecessor: ChainState, out: Path, repo_root: Path) -> dict`.
- `check_edge(checkpoint_dir: Path, derived_dir: Path, predecessor: ChainState, repo_root: Path, report: Path | None = None) -> dict`.
- Producer output includes exact new body IR, caller/terminal evidence, current endpoint, next-entry snapshot, carried Forms and an `EDGE_COMPLETION_V1` digest.
- Checker reconstructs the same edge from raw checkpoint evidence without importing the production producer, translator result or frozen V2 evaluator as its numerical oracle.

- [ ] Build test fixtures by splitting existing saved Runtime Trace evidence into immutable edge-shaped checkpoints; fixture construction is TEST_ONLY and may not become production evidence.
- [ ] Write RED positive tests for genesis→S1, S1→S2 and final S2→S3 edge reconstruction.
- [ ] Write RED negative tests for wrong latent with equal public q/v, one changed Form coefficient, box reset, t/dt swap, gradient reset omission, wrong predecessor certificate, cross-session checkpoint splice, trace-prefix mismatch, body(k+1) evidence present before acceptance, and FINAL_TERMINAL with successor data.
- [ ] Run `python -m pytest tests/test_live_chain_incremental.py -q`; expected RED.
- [ ] Implement per-edge producer using existing raw semantics/IR/V2 primitives only for the new segment. The predecessor Forms are explicit inputs; never reseed carried q/full_v/latent Forms.
- [ ] Implement independent checker reconstruction. Replay semantic comparison may ignore process-local addresses and acquisition-specific basis namespace, but live edge checks require exact current session/barrier/process evidence.
- [ ] Require `NEXT_STEP_ENTRY` to prove the next body has not executed; require `FINAL_TERMINAL` to prove the final native output-store corridor and forbid any successor.
- [ ] Run Task 4 tests plus existing `tests/test_regular_nstep_pipeline.py tests/test_regular_nstep_raw.py` under their required writer-quota environment; expected PASS.
- [ ] Review Task 4 diff only; no commit.

### Task 5: V1 Authority Controller and Resume-After-CURRENT Ordering

**Files:**
- Create: `verified_driver/v1/controller.py`
- Create: `verified_driver/v1/gate.py`
- Test: `tests/test_verified_driver_v1_controller.py`

**Interfaces:**
- `V1Gate.evaluate(checkpoint_id: str, checkpoint_dir: Path, predecessor: ChainState, derived_dir: Path, repo_root: Path) -> tuple[ChainState, bytes]`.
- `VerifiedChainDriver(repo_root: Path, store: ChainStore, run_root: Path, ledger: Path)`.
- Public method: `run(requested_steps: int, run_id: str) -> ChainResult`. Lost live sessions are not reattached here; Task 6 replay owns crash recovery.
- At every non-final barrier the only legal order is seal → producer/checker → acceptance → store.publish/CURRENT → token issue → session.resume.

- [ ] Write RED controller tests with a fake `LiveGalaSession`: successful S0→S1→S2→S3, checker refusal at edge3, checker exception, resource refusal, publish failure, stale event, and transaction retry.
- [ ] Add explicit RED crash hooks at `before_current_replace`, `after_current_replace_before_token`, `after_token_before_resume`. Assert the recovered authoritative generation follows the approved recovery table.
- [ ] Add RED tests that attempt token issue before CURRENT publication, resume after checker PASS but before CURRENT, and reuse S1 acceptance for S2; each must refuse without forward body execution.
- [ ] Run `python -m pytest tests/test_verified_driver_v1_controller.py -q`; expected RED.
- [ ] Implement `V1Gate` binding exact checkpoint, predecessor, edge report, source snapshot, barrier sequence and continuation state into one acceptance receipt.
- [ ] Implement Driver orchestration. After a valid CURRENT replacement, a later pre-resume crash must recover the new generation and keep the live/replayed process stopped until that generation is verified.
- [ ] FINAL_TERMINAL publication ends the requested run: no resume token and no successor generation.
- [ ] Run Tasks 1-5 tests plus all V0 tests; expected PASS.
- [ ] Review Task 5 diff only; no commit.

### Task 6: Replay Recovery and Orphan-Process Containment

**Files:**
- Create: `verified_driver/v1/replay.py`
- Create: `verified_driver/v1/containment.py`
- Create: `runtime_trace/live_chain/supervisor.py`
- Test: `tests/test_verified_driver_v1_replay.py`
- Test: `tests/test_verified_driver_v1_containment.py`

**Interfaces:**
- Produce non-authoritative `ReplayObservation` carrying logical continuation fields plus fresh process/session provenance; it has no generation authority, acceptance ID or publish method.
- `ReplayComparator.compare(stored: ChainState, observed: ReplayObservation) -> None`: ignores only live session/process-local address/acquisition namespace differences; requires equal logical lanes, Form coefficients/boxes+basis contract, t/dt, step and source binding, and checks the observation against the stored chain position rather than comparing replay content IDs.
- `ReplayEngine(driver_factory, store).recover(requested_steps: int, run_id: str) -> ChainResult`.
- `ContainedLiveProcess` owns controller-watchdog pipe + process group/cgroup receipt; loss of controller authority closes the watchdog and kills/stops the complete GDB/inferior group before another uncertified body can begin.

- [ ] Write RED replay tests: reproduce S1/S2 from genesis without new generations; equal q/v but wrong latent refuses; wrong Form refuses; namespace/address change is allowed only in replay comparison; altered stored certificate refuses.
- [ ] Write RED terminal replay test: recovering a `FINAL_TERMINAL` state performs completion/exit handling only and cannot switch to LIVE or create S4.
- [ ] Write RED containment tests with real subprocesses for controller death while paused and while a simulated numerical body is active. Prove the child group cannot enter the next body marker.
- [ ] Run `python -m pytest tests/test_verified_driver_v1_replay.py tests/test_verified_driver_v1_containment.py -q`; expected RED.
- [ ] Implement replay from pinned genesis using fresh live-session evidence at each stored barrier. Replay validates but never calls `store.publish`.
- [ ] Implement transition to LIVE only for a reproduced `NEXT_STEP_ENTRY` whose next body remains inside the original requested scope.
- [ ] Implement watchdog/process-group containment with an execution receipt proving process IDs, exit reason and whether the next-body marker was reached. Python object cleanup alone is not evidence.
- [ ] Run Task 6 tests and Tasks 1-5 regression; expected PASS.
- [ ] Review Task 6 diff only; no commit.

### Task 7: Full V1 Authority Attack Matrix and Compatibility Regression

**Files:**
- Create: `tests/test_verified_driver_v1_attacks.py`
- Create: `verified_driver/v1/attack_support.py` only if helpers cannot remain test-only.
- No production change after a discovered failure without first using `superpowers:systematic-debugging`.

**Interfaces:** Exercise the public V1 model/store/session/checker/controller/replay APIs and assert both `CURRENT` and the forward-execution marker.

- [ ] Add attacks for q/full_v/latent mutation, Form coefficient/box mutation, Form reset, S1 receipt reused for S2, cross-session checkpoint splice, skipped/duplicate/stale barrier token, resume-before-check, resume-before-CURRENT, certified-prefix mutation, next-body execution before certification, t/dt swap, gradient reset omission, checker crash, resource refusal, source change and transaction retry.
- [ ] Add crash attacks before CURRENT, immediately after valid CURRENT but before token, and after token construction but before resume. Validate the exact authoritative generation rather than assuming predecessor rollback.
- [ ] Add replay attacks: equal q/v with wrong hidden continuation, altered stored certificate, cross-process namespace substitution outside replay mode, and attempt to create a generation during replay.
- [ ] Run `python -m pytest tests/test_verified_driver_v1_attacks.py -q`; expected all controls PASS and every mutant detected/refused.
- [ ] Run all V1 tests, all V0 tests, and selected existing Runtime Trace acquisition/pipeline/raw/resource/public tests with required quota environment; expected PASS.
- [ ] Byte/hash compare protected V0 and batch Runtime Trace source/artifact sets against the pre-V1 inventory; unexpected changes are blockers.
- [ ] Review Task 7 diff only; no commit.

### Task 8: Fresh N=3/N=4 Live Evidence, Replay, Cost, Review, and Delivery

**Files:**
- Create: `current/VERIFIED_DRIVER_V1_2026-10-06.md`
- Create fresh evidence only under `verified_driver/v1/artifacts/<run-id>/`.
- Do not overwrite V0 or Runtime Trace historical evidence.

**Interfaces:** Produce one real positive N=3 chain, one real negative N=4 barrier failure, one replay recovery receipt, controller-death containment receipts, final source/protection inventories and final review report.

- [ ] Record pre-run HEAD/status, spec/plan hashes, V1 source hashes, protected V0/Runtime Trace inventory, Gala wheel/frozen V2 hashes, current shared ledger and storage usage.
- [ ] Before any real live Gala validation, compute the guarded execution allowance required for the planned N=3 positive, N=4 negative, replay and controller-death runs. Current historical remainder is 663.3129064019781 seconds only. If the planned allowance cannot fit, STOP and ask the designer for a new ceiling; do not reset or replace the ledger.
- [ ] Run an ordinary unmodified Gala N=3 control once within the approved budget and record only its public q/v output and environment/source identities.
- [ ] Run fresh live V1 N=3. Required evidence: one inferior/session, S1/S2/S3 predecessor chain, pause before body2 and body3, no body(k+1) before Sk publication, exact q/full_v/latent/Form carry, S3 FINAL_TERMINAL, and final public q/v equal the ordinary Gala N=3 control.
- [ ] Run fresh live N=4 negative experiment: certify S1 and S2, reach the barrier before body4 after body3/caller3-4, invalidate the third candidate edge before certification, and prove `CURRENT == S2`, body4 marker absent, session STOP.
- [ ] Run real controller-death experiments under containment: one while paused, one while a numerical body is active. Prove no next uncertified body starts.
- [ ] Run recovery after a valid post-CURRENT/pre-resume interruption. Prove the new published generation remains authoritative and execution stays stopped until recovery verifies it.
- [ ] Run replay from genesis to the last nonterminal certified boundary and prove semantic continuation equality without duplicate generations. Separately replay S3/FINAL_TERMINAL and prove it cannot enter a new live body.
- [ ] Measure per barrier: live acquisition, checkpoint seal, incremental producer, independent checker, store publication, paused wall time; separately measure replay recovery. Do not manufacture speed ratios from mixed intervals.
- [ ] Run the complete final regression suite again on the exact final source bytes. Preserve JUnit/stdout/command/environment receipts.
- [ ] Invoke `superpowers:requesting-code-review`. Reviewer must focus on pause-before-next-body evidence, hidden continuation state, post-CURRENT recovery, replay namespace rules, terminal replay and controller-death containment. Do not label internal review an external audit.
- [ ] Re-run affected tests after any review fix and repeat any real evidence whose source bytes changed.
- [ ] Recompute protected inventories and verify V0/batch Runtime Trace history is unchanged except explicitly approved mutable ledgers/receipts.
- [ ] Write `current/VERIFIED_DRIVER_V1_2026-10-06.md` answering the spec's final-report questions, including actual run IDs, certified generation IDs, failure position, body markers, replay result, costs, remaining assumptions, external-audit status and actual commit/push state.
- [ ] Present final report, review, regression output, source inventory and Git status. Stop before any further feature, optimization, commit or push unless separately authorized.

## Self-Review Notes

- **Spec coverage:** Tasks 1-8 cover continuation certificates, durable CURRENT semantics, persistent pause/resume, immutable checkpoints, per-edge independent verification, resume-after-publication ordering, fail-closed behavior, replay, FINAL_TERMINAL recovery, controller death, N=3 positive, N=4 negative, costs and final review.
- **Type consistency:** Task 1 owns `ChainState`; Task 2 owns barrier/token/checkpoint records; Task 3 produces `BarrierEvent`; Task 4 consumes `ChainState + checkpoint`; Task 5 is the only live publication/resume authority; Task 6 replays without publication.
- **Review-focus coverage:** post-CURRENT crash is Tasks 1/5/7/8; FINAL_TERMINAL replay is Tasks 6/8; namespace separation is Tasks 4/6/7; orphan execution is Tasks 6/8; hidden continuation mismatch is Tasks 4/7.
- **Scope control:** no multi-core/evolution work, production fallback, arbitrary restart injection, 10/100 V1 campaign, A/Impulse change or generalized program support.
- **Resource discipline:** unit/fixture work precedes heavy execution; the existing ledger is authoritative and cannot be reset. Insufficient real-run allowance is a designer decision, not an implementation workaround.
- **Commit rule:** no task contains a commit step because the designer has not authorized V1 commit/push.

