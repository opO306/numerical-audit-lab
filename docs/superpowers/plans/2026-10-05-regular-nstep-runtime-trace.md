# Regular N-step Runtime Trace Implementation Plan

Delivery note: this is the original planning checklist and preflight status.
Actual implementation consolidated contract helpers into acquire/schema and
the public runner into run.py; attacks and cost/inventory tools live in the
separate workflow evidence directory. The retained checkbox text describes the
plan, not an unimplemented delivery. Current supported scope, actual test results
and audit boundaries are in `current/RUNTIME_NSTEP_INTEGRATED_CANDIDATE_2026-10-05.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. User authorization overrides skill defaults: no commit/push, no numerical execution before the required budget decision, no deletion of failed evidence.

**Goal:** Deliver one actual Gala -> trace -> Numeric IR -> frozen V2 -> independent checker path, verified for 10 then 100 steps with preserved state/error lineage and honest completion/refusal.

**Architecture:** A new bounded collector records repeated actual body/caller occurrences and final output stores; old narrow entry points remain unchanged. Producer and independent checker construct occurrence-specific graphs separately and exchange a checked six-lane terminal frontier with one shared Form basis. A guarded runner measures and seals the connected pipeline and its failure receipts.

**Tech Stack:** Existing Python 3.12/WSL Linux x86-64, GDB, GNU objdump, unchanged Gala 1.12.0 wheel and frozen `lab.v2_bound`; cgroup v2 memory enforcement and explicit byte accounting.

**Spec:** `docs/superpowers/specs/2026-10-05-regular-nstep-runtime-trace.md`.

## Global Constraints

- Frozen wheel SHA `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
- Frozen V2 LF SHA `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`, K=4; computed-minus-reference Form and shared basis.
- Regular orbit only; represented dt=1/64; one orbit, two coordinates; N=10 then N=100, same source map.
- Preserve existing literal CASE_PINS, audited source/receipts and raw historical bytes.
- New-run semantics do not confer an external audit or universal/physical correctness.
- init-return -> step1-entry remains UNTRACED under accepted base assumptions.
- Budget approval pending: 3,600s cumulative, 600s per job, 4 GiB process tree, 8 GiB new evidence; limits are ceilings, not predictions.
- Worktree isolation; no Impulse/A/physics/Verified Driver work; no paid resources, commit or push.

## Review Focus

1. An identical bit string must never allow cross-process or cross-step state substitution.
2. Same-value writes must remain visible; a zero endpoint alone cannot prove reset/non-overlap.
3. Terminal output stores and requested N must be proved independently of a valid prefix.
4. Parser, subprocess and staging exceptions must not leave consumable success artifacts.
5. Resource guarding must cover the complete process tree and all evidence/log writes; a missing controller refuses execution.

## File and interface map

New `runtime_trace/regular_nstep/` files:

- `contract.py`: strict schema, namespace, limits and refusal/result types.
- `resources.py`: `run_guarded(command, limits, ledger, out) -> execution_receipt`; reservation-aware exclusive evidence writer.
- `harness.py`: same original Gala API and regular input with parameter N, accurate requested N metadata; no alternate calculation.
- `acquire.py` / `gdb_acquire.py`: actual repeated-body/caller/terminal acquisition, collector source proof and capture seal.
- `raw_check.py`: module/byte/order/control/EA/effect/ABI/terminal checks; imports no collector.
- `producer.py`: `build(capture_dir, out, root) -> candidate_report`; actual translator and frozen V2 calls.
- `checker.py`: `check(capture_dir, derived_dir, root) -> checker_report`; imports no producer/frozen evaluator.
- `runner.py`: `run(n, limits, out, root) -> run_report`; original baseline, acquisition, production, checker, last checked prefix and completion.
- `mutations.py`: exclusive attacks with repaired hashes and separately labelled integrity controls.
- `CONTRACT.md` / `README.md`: final supported contract and reproduction commands, not speculative PASS.

New tests: `tests/test_regular_nstep_resources.py`, `test_regular_nstep_acquisition.py`,
`test_regular_nstep_raw.py`, `test_regular_nstep_chain.py`,
`test_regular_nstep_mutations.py`, `test_regular_nstep_delivery.py`.
Final source-map, raw/derived, tests, measurements and audit package live in new
exclusive `runtime_trace/regular_nstep/artifacts/` attempt directories.

## Task 1: Isolation, strict contract and enforceable resources

**Interfaces:** approved `Limits` -> `run_guarded` and exclusive writer -> execution receipt consumed by capture and runner. `CheckReport` always exposes requested_complete and last checked prefix.

- [ ] Snapshot old source/evidence hashes and other-work uncommitted paths; create managed worktree at recorded HEAD without resetting the current checkout.
- [ ] Write failing tests for bool-as-int N/limits, duplicate JSON keys, reused output paths, missing controller, descendant memory growth, timeout, partial output and log/storage exhaustion.
- [ ] After budget decision, run these tests: expected initial RED on the missing new API; retain exit/log receipts.
- [ ] Implement strict schema and byte reservations, verified cgroup memory/swap/time configuration and whole-job accounting; no unenforced fallback.
- [ ] Run resource tests: expected GREEN, all limit attacks REFUSED_RESOURCE and no complete artifact.

## Task 2: One original harness and generic actual acquisition

**Interfaces:** `run_guarded` executes one parameterized harness/collector; output `capture.json` records regions, module/process identity, source pins, actual terminal frontier and completion events.

- [ ] Write failing tests for source transformation proof, arbitrary occurrence IDs, actual N entry/return counts, row limit, missing read/write, wrong thread and refused helper/terminal path.
- [ ] Run scoped tests: expected RED on the new acquisition interfaces.
- [ ] Implement a fresh harness whose original calculation/API/input differs only in N parameter plumbing and honest output metadata. Record a reviewed transformation, without modifying either old harness.
- [ ] Reuse reviewed definition-only collector primitives. The old 5,000-global-row/120s guard cannot remain the new N budget: introduce an explicit, source-bound new collector guard without removing the old guard from old entry points.
- [ ] Collect each actual body and corridor, same-value writes, PRE reads, t/dt lineage and final output stores. Preserve unsupported/failed captures exclusively.
- [ ] Run scoped tests: expected GREEN. Do not run native N=100 before a successful checked N=10.

## Task 3: Independent native semantics and adjacent/terminal joins

**Interfaces:** `validate_raw(capture_dir, root) -> checked_regions/frontiers`; producer and checker both consume a verified raw boundary, without using collector classifiers as the independent effect oracle.

- [ ] Write RED tests from existing observed raw rows for repaired missing/reordered/duplicate rows, wrong EA/control targets, same-value write omission, carry overlap, partial reset, t/dt swap and missing/wrong final save.
- [ ] Run tests and retain the actual RED results.
- [ ] Reuse independently decoded ELF/objdump rules and independent caller EA/register/flag/memory replay for supported observed forms. Require full byte/order coverage, process/thread consistency, live-pointer/alias preconditions and no protected writes.
- [ ] Define changed loop/save/termination semantics explicitly. Unsupported forms refuse; do not delete old signature fields to get equality.
- [ ] Check final output load/store lineage, save index/allocation, observed N entry/return count, absence of unexpected next step and normal inferior exit. State any untraced post-frontier boundary.
- [ ] Run raw/join tests: expected GREEN, all repaired semantic attacks refused with the actual failure stage.

## Task 4: Automatic IR, actual frozen V2 and independent Form frontier

**Interfaces:** verified raw regions -> producer IR/V2/endpoint files; checker independently reconstructs the same graph and terminal frontier; each endpoint is the exclusive input source for the next occurrence.

- [ ] Write failing chain tests for equal-bit occurrence merge, old step1 Form reuse, box/coefficient/basis reset, forward COPY, swapped endpoint IDs, missing operation and modified output bits.
- [ ] Run scoped tests: expected RED before new producer/checker implementation.
- [ ] Reuse translator `_Dataflow` only in producer and independent `_Reconstruction` only in checker. Do not call narrow public APIs by bypassing their old literal trust restrictions.
- [ ] Use actual unchanged frozen V2 per observed arithmetic operation. Reuse independent exact/RNE and Form recomputation as checker prerequisites, clearly labelled author-ported reuse.
- [ ] Bind six next-entry Form states to immediately preceding last-write/COPY states and shared basis; gradient zero requires reset evidence, represented t/dt requires load provenance.
- [ ] Publish candidate components in staging; write requested completion only after independent checks. Return checked prefix and refusal on any later failure.
- [ ] Run chain tests and old scoped regressions: expected GREEN, old artifacts/source hash inventory identical.

## Task 5: Connected 10 then identical-source 100, attacks and cost

**Interfaces:** `runner.run` combines guarded stages and produces source-bound measurements plus a complete or refused run report. A successful 10-step result gates N=100.

- [ ] Record approved budget/enforcement receipts, installed source/module hashes and source-map SHA before the first numerical run.
- [ ] Measure original N=10 and traced N=10 separately; run automatic IR/V2/checker path. Expected CHECKER_PASS and requested_complete=true, or retain truthful REFUSED with prefix and resolve supported-path defects before N=100.
- [ ] Freeze source map and run original/traced/automatic N=100 with the same files. Expected identical source-map SHA; any changed source invalidates the earlier same-source claim until affected N=10 checks are rerun.
- [ ] Run the spec's attack matrix including raw, IR, Form, state, terminal and resource cases, repairing hashes for semantic cases. Expected semantic REFUSED for each; HASH/TRUST controls reported separately.
- [ ] Run connected regression under the remaining cumulative allowance; require zero failures/errors and disclose skips/xfails if any. Failure or exhausted budget is not completion.
- [ ] Seal measured stage times, peak tree memory, record sizes, source maps, commands/exit codes, failures and all manual interventions. Do not infer 100-step values from 10-step measurements.

## Task 6: Fresh audit, affected revalidation and delivery

**Interfaces:** immutable candidate source/raw/derived/test package -> fresh independent audit findings/result -> affected checks and final five-question report.

- [ ] Prepare a reviewable package containing the spec, final source map, old preservation map, actual captures, derived files, limits/cost, attacks, regression and reproduction commands.
- [ ] Obtain fresh review using the executing-plans/requesting-code-review workflow. For numerical audit, prohibit the production evaluator/collector from acting as its oracle and identify reused dependencies and authorship.
- [ ] Fix correctness, lineage and resource defects across all related paths. Reproduce defects, then rerun affected raw/chain/mutations and integrated checks within budget; preserve superseded evidence.
- [ ] External audit closure stays PENDING without an actual external report. Fresh agent review or author-ported audit reuse cannot be relabelled external closure.
- [ ] Compare all old protected bytes and other-work files; verify recovery/package hashes and source identity. Do not commit/push.
- [ ] Deliver the user's five-question report with actual 10/100 results, source identity, refusal evidence, measured costs, independent audit scope and unresolved blockers. Verified Driver remains the next separately reviewed stage.

## Preflight rulings

- The current user request approves extension work, so the old ADR's design-only restriction is historical. The explicit execution-budget gate still applies.
- New schema/module trust and dynamic caller/terminal rules are necessary additions described in the spec; old accepted contracts are immutable.
- Planning is not implementation completion. No numerical run, attack test, regression or fresh audit has yet been performed in this task.
- The user did not request a different chat or authorize messaging another chat; all work stays in this task.
- Skill commit/cleanup defaults are overridden by the explicit no-commit/push and evidence-preservation instructions.
