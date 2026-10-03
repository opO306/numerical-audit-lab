# Regular 2-Step Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the narrow regular init + 2-step semantic chain while preserving all previously audited assets, package it for external audit, and push the completed feature branch.

**Architecture:** Add sibling acquisition and step2 proof/composition modules. Reuse frozen step1/schema rules only after actual machine-checkable structural comparison. Keep new semantic checker independent of producer/frozen evaluator and keep historical assets immutable.

**Tech Stack:** WSL Ubuntu-24.04, Python 3.12.3, GDB 15.1, frozen Gala 1.12.0 wheel, GNU objdump 2.42, unchanged frozen V2, pytest, Git.

**Spec:** `docs/superpowers/specs/2026-10-03-regular-2step-design.md` plus its byte-preserved full user-request reference.

## Global Constraints

- New status: Regular 2-Step Chain / IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING.
- Production `H.integrate_orbit` path, exact `runtime_trace/harness_nsteps2.py`, save_all retained; no direct-kernel harness.
- Frozen Gala 1.12.0 wheel SHA cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0.
- Preserve all baseline 1,488 tracked assets and old raw evidence; never overwrite artifact directories.
- Reuse existing modules read-only; do not import production proof logic into new independent checker.
- Distinct acquisition/step2 dynamic identity even for equal bits; q/full_v/latent Forms carry, gradient fresh zero, t new root, dt actual source, temporary registers fresh roots.
- No general N-step, 3/10/100-step, trajectory/global-error/shadowing/physical/observable claims.
- User's latest push authorization overrides pasted no-push; push feature branch after validation, no fetch/merge.
- Preserve failed/interrupted runs and report actual tests, costs and Git state.

## Review Focus

1. Same-bit state from the wrong acquisition must be REFUSED after hashes are repaired.
2. Instruction bytes/order/helper control difference must block template reuse.
3. Raw endpoint equality must not silently reset carried nonzero box Forms.
4. Equal-bit dynamic ID substitution or operand-order swap must be semantically refused.
5. Malformed/truncated raw evidence and stale caller input must not produce a completion certificate.

---

### Task 1: Actual second body acquisition and structural reuse proof

**Files:**
- Create: `runtime_trace/regular_2step/__init__.py`, `acquire.py`, `gdb_acquire.py`, `structure.py`, `CONTRACT.md`.
- Test: `runtime_trace/regular_2step/tests/test_acquisition_structure.py`.
- Evidence: `runtime_trace/regular_2step/artifacts/known-01/` and `fresh-01/`; failed attempts in exclusive numbered directories.

**Interfaces:**
- Consumes: unchanged regular n_steps=2 harness, frozen acquisition helpers, old audited trace and caller capture/transition artifacts.
- Produces: each capture directory has `trace.jsonl`, `capture.json`, `execution.json`, `source_pinset.json`, `acquisition_seal.json`, `harness_output.json`, `gdb.log`, `structure_report.json`.
- `structure.compare(capture_dir: Path, root: Path) -> dict` validates raw integrity, frozen ELF/objdump correspondence, actual step1/step2 sequence, branch/helper path and arithmetic/storage topology; reports proven reuse or explicit difference.
- Document all exact capture/row/region schemas and paths in CONTRACT, preserving semantic operands/origins compatible with audited `_Dataflow` where possible. Add process-local first endpoint/second entry/second return binding, actual PRE memory observations and writes plus implicit controls. Keep original code untouched.

- [ ] Write RED tests for malformed harness/receipt, altered instruction/order/control/role, and equal-bit wrong acquisition entry binding; capture failure output.
- [ ] Implement minimal sibling wrappers/subclasses over existing acquisition machinery without importing its top-level execution accidentally. Pin reused source bytes and new launcher/GDB sources before acquisition. Never synthesize an old-process continuation.
- [ ] Generate known/audited-lineage then fresh separate native processes through normal two-step harness completion. Record attempts/failures/PID/startticks/boot/source/module/time costs. Preserve failed runs.
- [ ] Compare actual step1 and step2 bodies by module-relative addresses and bytes, branch/control/helper sequence, operation kind/order, memory role and boundary topology before selecting template reuse. Independently re-decode ELF instructions. Report gradient/t/dt differences and final endpoint bits.
- [ ] Run focused GREEN tests; validate both case receipts and replay structural report; commit sources, raw captures and structure proof. Self-review and write report with complete reading/testing boundaries.

### Task 2: Step2 Numeric IR, frozen V2 and semantic chain checker

**Files:**
- Create: `runtime_trace/regular_2step/producer.py`, `checker.py`, `mutations.py`, `schema.py`, `README.md`.
- Optional focused split: `form_oracle.py` for independent IEEE-754/Form arithmetic; keep files cohesive, no duplicated framework.
- Test: `runtime_trace/regular_2step/tests/test_step2_chain.py`, `test_step2_mutations.py`.
- Evidence: each known/fresh case under `artifacts/derived/<case>/`; mutation inputs/results under `artifacts/mutations/`.

**Interfaces:**
- Consumes: Task1 capture/structure schemas and accepted immutable caller paths, audited 1-step IR/V2 endpoint graph/Forms, unchanged frozen `Form/step_forms`.
- Produces: `numeric_ir.json`, `v2_correspondence.json`, `chain.json` (REGULAR_2STEP_CHAIN_V1), `checker_report.json`, endpoint and component receipts.
- `producer.build(capture_dir: Path, out: Path, root: Path) -> dict` writes exclusive derived artifacts and publishes completion last.
- `checker.check(capture_dir: Path, derived_dir: Path, root: Path) -> dict` refuses malformed/untrusted/semantic mismatch and returns CHECKER_PASS only after all lower checks and semantic composition joins.
- `mutations.generate(root: Path, out: Path) -> dict` preserves exact mutation inputs/results/repairs and a reproducible manifest; no public trust override.

- [ ] Write RED tests for real known/fresh case composition, carried Form preservation, fresh gradient/time, distinct dynamic namespace, malformed evidence and repaired semantic attacks.
- [ ] Build IR from actual new trace using structurally proven template/dataflow/schema rules read-only. Bind actual opcode/ELF/bytes/order/input/output/state evidence; no copy-and-rename of prior result. Distinct step2/acquisition IDs. If Task1 finds differences, contract only those differences.
- [ ] Bind six carried state lanes to old audited terminal dynamic COPY/source and exact Forms/basis; gradient/time/dt roots follow caller contract. Drive actual unchanged frozen V2 arithmetic and serialize each operation/state/value/boundary with counts and ordered IDs.
- [ ] Implement independent raw arithmetic/IR/Form checking using exact rational IEEE-754 interpretation and separate upward-rounded Form operations. No producer/acquisition/adapter/frozen V2 evaluator proof imports. Validate unchanged components with audited APIs as prerequisites, independently verify new graph and semantic joins.
- [ ] Compose ordered identities/component hashes and initial/intermediate/final boundaries; completion hash covers them, but repaired hash alone never proves semantic join. Bind case/process/lineage, fresh process-local endpoint/entry and old audit-reference role/bits/Form identity.
- [ ] Generate all 15 requested semantic mutation classes with saved actual inputs and fully repaired completion/component hashes where relevant. Separate deliberate hash/trust controls; require semantic refusals for wrong bits/IDs/acquisition, deletions/duplication/reorder, ADD/SUB swaps, equal-bit other ID, state swap, handoff, mixed case, repaired completion, stale caller.
- [ ] Run focused GREEN tests and both CLI normal cases. Save outputs/commands/exit codes/timing. Commit; self-review and full report including added/reused LOC/modules and checker functions.

### Task 3: Regression validation, audit delivery and cost report

**Files:**
- Create: `runtime_trace/regular_2step/delivery.py`, `current/REGULAR_2STEP_STATUS.md`, received audit identity record.
- Update only new `runtime_trace/regular_2step/README.md`/CONTRACT as needed and append evidence raw-byte attributes.
- Evidence: `runtime_trace/regular_2step/artifacts/validation/`; delivery output `D:/numerical-audit-lab-regular-2step-delivery-2026-10-03/`.

**Interfaces:**
- Consumes: both accepted derived case outputs, mutation manifest, prior component artifacts, baseline preflight map, task/review/ledger records and tracked source hashes.
- Produces: implementation report, cost report, related pytest logs/JUnit, protected verification, manifest, exact HEAD snapshot, Git bundle, bare recovery/fsck/ancestry and ZIP verification. Final push is controller-owned after final branch review.

- [ ] Run every new test plus unchanged Caller101 and regular479 suites with frozen Python/PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Distinct test names, complete exit0 results, JUnit0fail/error/skip. If any frozen/core file changed, run full LOCAL FULL pytest -n6 and describe broken audit premise first.
- [ ] Reproduce mutation inputs/results once and verify byte identity. Pin all tested Python source bytes through final changes; rerun only covering suites for later source fixes.
- [ ] Verify baseline tracked bytes/Git blob identity (authorized added attribute metadata separately), frozen wheel/module/core hashes and unchanged historical evidence.
- [ ] Write accurate current closure/new-chain statuses and cost report: measured elapsed total and defined timing origin, new/reused LOC/modules, all acquisition attempts/failures, new checker functions, total actual pytest time. Preserve failure history and identify any scaling concern.
- [ ] Implement audited packaging helper (exclusive destination), include complete components/cases/mutation inputs/checker sources/failure history/reviews/tests/cost/spec/plan/request, exact snapshot, bundle and manifest. Commit all implementation/evidence/status changes; do not push yet.
- [ ] Report READY_FOR_FINAL_REVIEW with exact sources/tests/HEAD. Controller performs fresh whole-branch review and at most one final fix wave; run delivery helper at final reviewed HEAD, verify ZIP/hash/size/bare recovery, then controller pushes and verifies remote ref. Do not claim final delivery or push until actually run.
