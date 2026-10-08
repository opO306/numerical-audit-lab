# Compute Metabolism V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project override:** 이 프로젝트에서는 설계자 명시 승인 전 staging/commit/push를 하지 않는다. 아래 각 Task의 마지막 단계는 commit 대신 review checkpoint이다.

**Goal:** 승인된 Verified Driver V1은 읽기 전용으로 유지하면서, GCP system transient unit으로 2C / 1C / 0.5C CPU envelope를 강제하고 N=3 정확성 통과 실행의 CPU·wall·memory·throttle 비용을 반복 측정하는 Compute Metabolism V0 wrapper와 campaign runner를 만든다.

**Architecture:** 새 코드는 `compute_metabolism/v0/`에만 둔다. 외부 system guard가 CPU/memory/wall/writer envelope를 강제하고, 그 안에서 기존 production `ChainStore + VerifiedChainDriver + V1Gate`를 fresh store/session으로 실행한다. campaign layer는 상위 4200초/3GiB budget, 3→5→7 반복, STOP/REFUSED 분류를 맡고, analysis layer는 raw evidence를 바꾸지 않고 CV와 profile 비교만 만든다.

**Tech Stack:** Python 3.12.3, pytest, Linux cgroup v2, systemd 257 system transient units, GDB 15.1, Gala 1.12.0.

**Spec:** `docs/superpowers/specs/2026-10-06-compute-metabolism-v0-design.md`

## Global Constraints

- Baseline branch/HEAD at plan authoring: `codex/runtime-trace @ b986c4e7306101c01257d2dfab72e856d67e6ebe`.
- V1 approved source binding: `f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd`.
- V1 product source, Runtime Trace approved source, historical Task 8 evidence/ledger are read-only.
- GCP primary VM identity: instance `instance-20260925-221723`, ID `1987831758054968318`, zone `us-south1-b`.
- Prepared rootfs: `/home/zun24/compute-metabolism-v0-prepared-20261006/rootfs`.
- Inside-rootfs source root: `/workspace`; Python: `/home/otherside123/venvs/gate2c1-trace/bin/python`.
- 2C = guest logical CPUs `0,1`; 1C = `0`; 0.5C = `0` + `CPUQuota=50%`, `CPUQuotaPeriodSec=100ms`.
- All profiles: MemoryMax 4,294,967,296 bytes, MemorySwapMax 0, OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1.
- Per-run writer reservation = 671,088,640 bytes; post-run retained threshold = 100,663,296 bytes.
- Campaign retained ceiling = 3,221,225,472 bytes; campaign outer guarded wall ceiling = 4200 s.
- Per-run outer wall deadline = 180 s.
- Repetition = 3 → 5 → 7; stable ACCEPT requires wall CV ≤ 0.05 and CPU CV ≤ 0.05.
- No fitness score, no role parallelism, no neural/evolution work, no N=10/N=100 in V0.
- No outlier deletion, no result snapping/repair, no automatic budget reset/extension.
- A generic V1 STOP/exception/internal timeout is not automatically a resource refusal.
- Every execution attempt is fresh store + fresh genesis + fresh session + fresh output namespace.
- No staging/commit/push without explicit designer approval.

## Execution Model Recommendation

- Architecture/guard/ledger tasks: GPT-5.6 Sol High or equivalently strong reasoning model.
- Routine test implementation after interfaces are fixed: Claude Sonnet-class or GPT-5.6 Sol Medium is sufficient.
- Recommended execution method: **Subagent-driven**, because guard, ledger, V1 admission, campaign policy are separate failure domains and a wrong boundary can invalidate the whole experiment.

## Review Focus

1. **1C/2C unit cgroup에 local `cpu.max`가 없을 수 있음:** 가장 가까운 ancestor의 effective unlimited quota를 확인해야 하며, “파일 없음=실패”나 “파일 없음=무제한”으로 단정하지 않는다. Task 2에 ancestor-resolution test를 둔다.
2. **`--collect`로 unit/cgroup이 사라지기 전 final counters를 보존해야 함:** unit 안의 wrapper가 종료 직전 final snapshot을 쓰고, outer guard는 그 receipt가 없으면 성공 처리하지 않는다. Task 2/4에서 test한다.
3. **Writer quota failure를 문자열만 보고 분류하면 안 됨:** 구조화된 proof가 없으면 `UNRESOLVED_FAILURE`로 STOP한다. Task 5에 explicit test를 둔다.
4. **Crash 후 RUNNING marker가 남은 ledger:** 다음 attempt가 같은 allowance를 다시 쓰지 못해야 한다. Task 3에 recovery-blocking test를 둔다.
5. **V1은 ACCEPT했지만 retained evidence가 96 MiB 초과:** V1 ACCEPT 원본을 보존하면서 wrapper outcome은 `REFUSED_RESOURCE:EVIDENCE_GROWTH`이고 campaign은 STOP해야 한다. Task 5에 test한다.

---

### Task 1: Package Skeleton and Exact Profile Contract

**Files:**
- Create: `compute_metabolism/__init__.py`
- Create: `compute_metabolism/v0/__init__.py`
- Create: `compute_metabolism/v0/profiles.py`
- Create: `tests/test_compute_metabolism_v0_profiles.py`

**Interfaces:**
- Produces: `ProfileSpec`, `CampaignLimits`, `get_profile(key)`, `parse_cpu_list(raw)`, `parse_cpu_max(raw)`.
- Later tasks consume these constants; no later task may hard-code a second copy of budget/profile numbers.

- [ ] **Step 1: Write failing profile/limit tests**

```python
def test_profiles_are_exact():
    assert get_profile("2c").cpus == (0, 1)
    assert get_profile("1c").cpus == (0,)
    assert get_profile("0p5c").cpus == (0,)
    assert get_profile("0p5c").quota_percent == 50
    assert get_profile("0p5c").quota_period_ms == 100

def test_limits_are_exact():
    limits = CampaignLimits()
    assert limits.per_run_wall_seconds == 180
    assert limits.total_wall_seconds == 4200
    assert limits.writer_bytes == 671088640
    assert limits.retained_run_bytes == 100663296
    assert limits.retained_total_bytes == 3221225472
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests/test_compute_metabolism_v0_profiles.py -q`

Expected: FAIL because package/interfaces do not exist.

- [ ] **Step 3: Implement profile and parser interfaces**

`ProfileSpec` must distinguish requested CPU set from quota. `parse_cpu_list("0-1,4")` returns canonical integer tuple; `parse_cpu_max("50000 100000")` and `parse_cpu_max("max 100000")` preserve quota/period semantics.

- [ ] **Step 4: Add invalid-input tests**

Assert duplicate/negative CPUs, malformed ranges, zero/negative periods, unknown profile keys are refused instead of normalized silently.

- [ ] **Step 5: Run Task 1 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_profiles.py -q`

Expected: all PASS.

- [ ] **Step 6: Review checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage/commit/push.

---

### Task 2: System Guard, Cgroup Snapshot, and Enforcement Validation

**Files:**
- Create: `compute_metabolism/v0/system_guard.py`
- Create: `tests/test_compute_metabolism_v0_guard.py`

**Interfaces:**
- Consumes: `ProfileSpec`, `CampaignLimits`.
- Produces:
  - `build_systemd_run_argv(...)->list[str]`
  - `current_cgroup_path()->Path`
  - `read_cgroup_snapshot(cgroup_path: Path)->dict`
  - `resolve_effective_cpu_max(cgroup_path: Path)->dict`
  - `validate_enforcement(profile: ProfileSpec, snapshot: dict, topology: dict)->None`
  - `run_system_guard(...)->dict` outer receipt.

- [ ] **Step 1: Write command-builder tests**

For 2C assert argv contains system transient unit, UID1000/GID1003, RootDirectory prepared rootfs, WorkingDirectory=/workspace, `AllowedCPUs=0,1`, MemoryMax=4294967296, MemorySwapMax=0, CPUAccounting/MemoryAccounting, RuntimeMaxSec=180s, KillMode=control-group, OOMPolicy=kill, and thread env vars.

For 0.5C additionally assert `CPUQuota=50%` and `CPUQuotaPeriodSec=100ms`.

For 2C/1C assert no quota property is injected.

- [ ] **Step 2: Add ancestor `cpu.max` test**

Build a fake cgroup tree where the unit directory has no `cpu.max`, parent has `max 100000`, and assert `resolve_effective_cpu_max` reports the parent source and unlimited semantics.

Also test that a parent `80000 100000` is rejected for 1C/2C because the profile would not be “unlimited”.

- [ ] **Step 3: Add strict cgroup validation tests**

Assert exact CPU set, memory=4294967296, swap=0, and 0.5C `50000 100000`. Verify CPU0/CPU1 have different guest core IDs for 2C. Preserve raw strings in the returned receipt.

- [ ] **Step 4: Add final-snapshot-required test**

Simulate a successful child exit with missing final cgroup receipt and assert outer guard cannot return success. It must classify environment/measurement authority as invalid, not substitute zeros.

- [ ] **Step 5: Implement the minimal guard**

Use the already successful GCP pattern:
`sudo -n systemd-run --quiet --wait --pipe --collect --uid=1000 --gid=1003`.

Keep source/user-space/reference read-only during execution. Make only the Compute Metabolism artifact namespace writable. If `ReadWritePaths` under the prepared RootDirectory does not work on GCP, STOP at Task 8 and debug; do not silently change architecture.

- [ ] **Step 6: Implement outer timeout/containment receipt**

Measure monotonic time outside `systemd-run`. On outer deadline, kill the owned system unit/control-group, wait for termination/reap, and record actual elapsed time including cleanup. A timeout is `OUTER_WALL_TIMEOUT` only when the guard itself proves it.

- [ ] **Step 7: Run Task 2 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_guard.py -q`

Expected: all PASS.

- [ ] **Step 8: Review checkpoint**

No numerical run. `git diff --check`; no staging/commit/push.

---

### Task 3: Top-Level Budget Ledger and Retained-Evidence Accounting

**Files:**
- Create: `compute_metabolism/v0/campaign.py`
- Create: `tests/test_compute_metabolism_v0_campaign.py`

**Interfaces:**
- Consumes: `CampaignLimits`.
- Produces:
  - `CampaignLedger.open(path: Path, limits: CampaignLimits)`
  - `begin_attempt(campaign_id, run_id, profile, role, round_index)`
  - `finish_attempt(run_id, outer_wall_seconds, cpu_seconds, writer_reserved_bytes, retained_bytes, outcome)`
  - `logical_tree_bytes(path: Path)->int`
  - `can_start_attempt()->tuple[bool, str|None]`.

- [ ] **Step 1: Write fresh-ledger tests**

Assert a new upper ledger starts at zero exactly once and stores fixed ceilings 4200s / 3GiB. Creating a second campaign ID must not create a new allowance.

- [ ] **Step 2: Write RUNNING-marker crash test**

```python
ledger.begin_attempt("gcp-a", "r1", "2c", "measured", 1)
with pytest.raises(UnresolvedPriorAttempt):
    ledger.begin_attempt("gcp-b", "r2", "1c", "measured", 1)
```

No automatic reset is allowed.

- [ ] **Step 3: Write allowance precheck tests**

Refuse to start a new numerical attempt if remaining guarded wall is less than 180s or remaining retained allowance is less than the 96MiB run threshold. This prevents knowingly partially funded attempts.

- [ ] **Step 4: Write actual-charge tests**

Charge actual outer wall, including values slightly above 180 due to containment cleanup. Preserve refusal/failure attempts in cumulative usage. Do not replace actual wall with V1 internal timing.

- [ ] **Step 5: Write retained-size tests**

`logical_tree_bytes` counts logical file lengths only, includes failed/warm-up/report files in the campaign tree, does not count prepared rootfs, and never deletes to fit the ceiling.

- [ ] **Step 6: Implement atomic ledger writes**

Use write-new/temporary + atomic replace. Preserve prior attempt records. Campaign-local `ledger.json` may mirror/reference the upper ledger but may not issue allowance.

- [ ] **Step 7: Run Task 3 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_campaign.py -q`

Expected: all PASS.

- [ ] **Step 8: Review checkpoint**

No systemd/Gala execution. No staging/commit/push.

---

### Task 4: Fresh Production V1 Runner and Correctness Admission

**Files:**
- Create: `compute_metabolism/v0/run_v1.py`
- Create: `tests/test_compute_metabolism_v0_v1.py`

**Interfaces:**
- Consumes: existing production `ChainStore`, `VerifiedChainDriver`, `V1Gate`; Task 2 cgroup helpers.
- Produces:
  - `AttemptConfig` for warm-up/measured runs.
  - `run_fresh_v1(config: AttemptConfig)->dict`.
  - `evaluate_v1_evidence(attempt_root: Path, requested_steps: int, reference: dict)->dict`.
  - CLI entry point used inside the system unit.

- [ ] **Step 1: Write fresh-attempt tests**

Use TEST_ONLY marker fixtures only for control-flow unit tests. Assert every invocation creates a new store/genesis/run directory and refuses an existing output directory. No prior CURRENT/checkpoint/token is reusable.

- [ ] **Step 2: Write N=3 admission tests**

Synthetic evidence must require:
- V1 result ACCEPT, generation3/step3.
- S0→S1→S2→S3 chain and S3 FINAL_TERMINAL.
- checker 1/2/3 = CHECKER_PASS + LIVE.
- body markers [1,2,3], no body4.
- same inferior PID/session for body1~3.
- each next body predecessor ID equals prior certified state ID.
- approved source binding and exact four final public bits.

Delete/change each item one at a time and assert admission fails closed.

- [ ] **Step 3: Write N=1 warm-up admission tests**

Require fresh S0→S1, generation1/step1, FINAL_TERMINAL, checker PASS, body1 only, body2 absent. Do not compare N=1 output to N=3 reference bits.

- [ ] **Step 4: Add cgroup-before/after contract tests**

Runner must write pre-environment and cgroup-before before invoking V1, and cgroup-after/final counters in a `finally` path while it is still inside the system unit. Missing final snapshot cannot become ACCEPT.

- [ ] **Step 5: Implement production runner**

Instantiate exactly production `ChainStore`, `VerifiedChainDriver`, `V1Gate`; do not import Task8 `ObservedSession`, negative/replay/death helpers, or substitute a gate/session in measured path.

Pass the new Compute Metabolism ledger path only to satisfy the existing V1 ledger contract. Keep V1 source binding logic unchanged.

- [ ] **Step 6: Preserve original and wrapper outcomes separately**

Write V1 result/metrics unchanged, plus wrapper admission report. The wrapper never rewrites a V1 STOP into ACCEPT.

- [ ] **Step 7: Run Task 4 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_v1.py -q`

Expected: all PASS.

- [ ] **Step 8: Review checkpoint**

Verify the approved 40-file V1 source binding is still unchanged. No staging/commit/push.

---

### Task 5: Outcome Classification, Round Scheduling, and CV Policy

**Files:**
- Modify: `compute_metabolism/v0/campaign.py`
- Modify: `tests/test_compute_metabolism_v0_campaign.py`

**Interfaces:**
- Produces:
  - `classify_attempt(v1_report, guard_receipt, retained_bytes)->dict`
  - `sample_cv(values: list[float])->float`
  - `profile_decision(profile: str, attempts: list[dict])->dict`
  - `next_attempt(history: list[dict])->dict|None`
  - CLI: `init`, `status`, `run-next`.

- [ ] **Step 1: Write exact schedule tests**

Round order must be:
1: 2C,1C,0.5C
2: 1C,0.5C,2C
3: 0.5C,2C,1C
4: 2C,0.5C,1C
5: 0.5C,1C,2C
6: 1C,2C,0.5C
7: 2C,1C,0.5C.

After round3, already-stable profiles are skipped in later rounds.

- [ ] **Step 2: Write CV tests**

Use sample SD denominator `n-1`. Both wall and CPU CV must be ≤0.05. 3 ACCEPT unstable → 5; 5 unstable → 7; 7 unstable → `UNRESOLVED_VARIABILITY`.

- [ ] **Step 3: Write mixed-outcome tests**

3 attempts with ACCEPT/refusal mix must expand to 5 regardless of ACCEPT-subset CV; same at 5→7; mixed at 7 = `UNRESOLVED_VARIABILITY`.

- [ ] **Step 4: Write 0.5C stable-refusal tests**

Exactly first three 0.5C measured attempts, all same structurally proven resource reason, valid profile/source/environment, no verification/unresolved failure → `STABLE_RESOURCE_REFUSAL`.

2C/1C never get this completion shortcut.

- [ ] **Step 5: Write refusal-taxonomy tests**

Only structured guard/cgroup/quota/ledger proofs can issue `REFUSED_RESOURCE`.
A V1 STOP string such as “resource refusal” without structured proof must yield `UNRESOLVED_FAILURE` + campaign STOP.
An internal 60/120s timeout without outer resource proof must also be unresolved.

- [ ] **Step 6: Write V1-ACCEPT + evidence-growth test**

Preserve `v1_outcome="ACCEPT"`; wrapper outcome becomes `REFUSED_RESOURCE` reason `EVIDENCE_GROWTH`; no next attempt.

- [ ] **Step 7: Implement one-at-a-time orchestration**

`run-next` launches at most one warm-up/measured attempt. After each attempt, ledger/outcome is durable before another is eligible. This intentionally favors auditability over unattended bulk execution.

- [ ] **Step 8: Run Task 5 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_campaign.py -q`

Expected: all PASS.

- [ ] **Step 9: Review checkpoint**

No warm-up/benchmark yet. No staging/commit/push.

---

### Task 6: Analysis and Final Report Without Data Rewriting

**Files:**
- Create: `compute_metabolism/v0/analyze.py`
- Create: `tests/test_compute_metabolism_v0_analysis.py`

**Interfaces:**
- Consumes: upper ledger + per-attempt raw receipts.
- Produces: `analyze_campaign(campaign_root: Path)->dict` and CLI writing `analysis/summary.json`, `analysis/report.md`.

- [ ] **Step 1: Write raw-preservation tests**

Analysis must not modify attempt files. Hash raw input tree before/after and assert equality.

- [ ] **Step 2: Write summary-stat tests**

For eligible ACCEPT attempts, report n, arithmetic mean, sample SD, CV separately for outer wall and CPU seconds. Keep memory/throttle/barrier metrics separate.

- [ ] **Step 3: Write ratio tests**

Derived ratios use profile ACCEPT mean divided by 2C ACCEPT mean and are labeled derived, not raw measurement. Do not create a combined fitness score.

- [ ] **Step 4: Write paused-timing test**

Assert report never calculates total cost as `paused + seal + produce + check + publication`. Authoritative totals are outer wall and cgroup CPU usage only.

- [ ] **Step 5: Write incomplete/STOP report tests**

`UNRESOLVED_VARIABILITY`, `UNRESOLVED_FAILURE`, budget exhaustion, or incomplete profile must prevent a COMPLETE conclusion while preserving all attempt counts/reasons.

- [ ] **Step 6: Implement analysis/report writer**

Use write-once output or new analysis version path; never overwrite raw attempts.

- [ ] **Step 7: Run Task 6 tests GREEN**

Run: `python -m pytest tests/test_compute_metabolism_v0_analysis.py -q`

Expected: all PASS.

- [ ] **Step 8: Review checkpoint**

No staging/commit/push.

---

### Task 7: Local Regression and Source-Boundary Verification

**Files:**
- Modify only if tests expose a defect in new `compute_metabolism/v0/` code.
- Do not modify approved V1/Runtime Trace source to make new tests pass.

**Interfaces:**
- Produces: local implementation-test evidence only; not campaign benchmark evidence.

- [ ] **Step 1: Run all new unit tests**

Run:
`python -m pytest tests/test_compute_metabolism_v0_profiles.py tests/test_compute_metabolism_v0_guard.py tests/test_compute_metabolism_v0_campaign.py tests/test_compute_metabolism_v0_v1.py tests/test_compute_metabolism_v0_analysis.py -q`

Expected: all PASS.

- [ ] **Step 2: Run focused existing V1/Runtime Trace regression**

Run:
`python -m pytest tests/test_regular_nstep_resources.py tests/test_verified_driver_v1_controller.py tests/test_verified_driver_v1_model.py tests/test_verified_driver_v1_store.py tests/test_live_chain_checkpoint.py tests/test_live_chain_protocol.py tests/test_live_chain_session.py -q`

Expected: all PASS.

- [ ] **Step 3: Recompute V1 binding**

Assert the 40-file live source snapshot still binds to:
`f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd`.

- [ ] **Step 4: Verify Git hygiene**

Run `git diff --check`, inspect `git status --short`, and confirm no historical Task8 ledger/evidence changed.

- [ ] **Step 5: Reviewer gate**

Fresh reviewer checks only the implementation against the approved spec/plan. Blocking finding stops before GCP deployment.

No staging/commit/push.

---

### Task 8: GCP Deployment and Non-Numerical Guard Preflight

**Files/remote paths:**
- Deploy new wrapper source to prepared rootfs `/workspace/compute_metabolism/`.
- Writable evidence namespace: `/workspace/compute_metabolism/v0/artifacts/`.
- Do not replace prepared Python/GDB/Gala/user-space binaries.

**Interfaces:**
- Consumes: Task 7 reviewed source.
- Produces: implementation/preflight evidence, not benchmark data and not GCP V1 completion.

- [ ] **Step 1: Record deployment identities**

Before copying wrapper files, record current VM instance ID, boot_id, topology, prepared binary hashes, V1 40-file binding, and destination wrapper manifest.

- [ ] **Step 2: Deploy only new wrapper package**

Copy `compute_metabolism/` without altering approved V1/Runtime Trace files. Recompute V1 binding after deployment and require exact equality.

- [ ] **Step 3: Run 2C/1C/0.5C trivial system-unit probes**

Use the new `system_guard` around a non-numerical Python child. Verify exact effective cpuset, effective quota semantics, 4GiB memory, swap0, thread env, writable artifact exception, final cgroup receipt, and process-tree containment.

- [ ] **Step 4: Test timeout containment with a trivial sleeper**

Trigger outer timeout on a non-numerical process tree and prove all owned descendants are terminated and actual cleanup wall is recorded.

- [ ] **Step 5: Test ledger crash blocking without Gala**

Leave a synthetic RUNNING marker and confirm `run-next` refuses another attempt until reconciled. Do not reset allowance.

- [ ] **Step 6: Verify no hidden user-unit fallback**

Receipt must identify a system.slice transient unit. If strict cpuset/writable-path/final-cgroup behavior differs from the prepared preflight, STOP and use systematic debugging before any V1 run.

- [ ] **Step 7: Review checkpoint**

Submit guard-preflight report. No warm-up/benchmark yet. No staging/commit/push.

---

### Task 9: Start One GCP Campaign and Run the Non-Scored N=1 Warm-up

**Files/evidence:**
- Create during execution: `compute_metabolism/v0/artifacts/budget.json`
- Create: one `gcp-<campaign-id>/` namespace and warm-up evidence.

**Interfaces:**
- This is the first numerical use of the new campaign budget.

- [ ] **Step 1: Initialize the single upper ledger**

Record ceiling 4200s, 3GiB, approved spec/plan hashes, instance ID, boot_id, topology, V1 binding, wrapper binding. Campaign ID creation must not create an extra allowance.

- [ ] **Step 2: Run exactly one 2C N=1 warm-up**

Use per-run outer deadline180s, writer640MiB, retained post-run threshold96MiB, memory4GiB/swap0.

- [ ] **Step 3: Validate warm-up correctness**

Require fresh S0→S1, generation1/step1, FINAL_TERMINAL, independent checker PASS, body1 only, body2 absent, source/environment/profile integrity.

- [ ] **Step 4: Validate accounting**

Charge actual outer wall and retained bytes. Record actual writer counter. If 640MiB is insufficient, do not increase it; classify only from structured evidence, otherwise `UNRESOLVED_FAILURE`.

- [ ] **Step 5: Warm-up gate**

PASS permits Task 10. Any warm-up failure/refusal/invalid environment stops before measured runs and preserves evidence.

---

### Task 10: Primary N=3 Campaign, Conditional Expansion, and Completion Review

**Files/evidence:**
- Append only to the same upper ledger and campaign namespace.
- Create round-01..round-07 as needed.
- Create `analysis/summary.json` and `analysis/report.md`.

- [ ] **Step 1: Execute Rounds 1–3 one attempt at a time**

After every `run-next`, verify durable ledger/outcome before the next. Do not batch-launch profiles.

- [ ] **Step 2: Apply correctness admission before performance analysis**

Only eligible V1 ACCEPT attempts enter CV/ratio calculations. Verification/environment/unresolved failures stop the whole campaign immediately.

- [ ] **Step 3: Evaluate profile outcomes after three attempts**

Stable ACCEPT profiles stop. 0.5C may finish as `STABLE_RESOURCE_REFUSAL` only under the exact spec conditions. Mixed/unstable profiles proceed.

- [ ] **Step 4: Execute conditional Rounds 4–5 only for unresolved profiles**

Re-evaluate after attempt5. Stable profiles leave the schedule.

- [ ] **Step 5: Execute conditional Rounds 6–7 only if still unresolved**

At attempt7, mixed or CV-unstable result becomes `UNRESOLVED_VARIABILITY`. Do not extend to attempt8.

- [ ] **Step 6: Enforce upper ceilings before every attempt**

Do not start if remaining wall <180s or retained allowance <96MiB. Actual overrun during containment is still charged and then STOPs.

- [ ] **Step 7: Generate analysis**

Run `analyze.py`. Preserve raw evidence hashes. Report raw CPU/wall/memory/throttle/barrier data separately from derived CV/ratios.

- [ ] **Step 8: Final source/environment/accounting review**

Recheck V1 source binding, instance ID, boot_id, topology, upper ledger continuity, all attempts/outcomes, no hidden deletions, no Task8 ledger changes.

- [ ] **Step 9: Completion verdict**

Claim `Compute Metabolism V0 COMPLETE` only if:
- warm-up PASS;
- 2C stable eligible ACCEPT;
- 1C stable eligible ACCEPT;
- 0.5C stable eligible ACCEPT or exact STABLE_RESOURCE_REFUSAL;
- budget/ledger/source/environment integrity remains valid.

Otherwise report the exact STOP/incomplete state without upgrading evidence strength.

- [ ] **Step 10: Independent final review**

Use a fresh reviewer and the verification-before-completion procedure. No formal-certification/external-audit claim.

No staging/commit/push.

---

## Explicitly Deferred

- Local Ryzen 5600 cross-environment run: after GCP primary completion only, with separate local CPU-control preflight and separate execution allowance.
- Role parallelism and multi-core work distribution.
- Neural controller / evolutionary search / fitness optimization.
- N=10/N=100 Compute Metabolism campaign.
- Any V1 source/verification-contract change.
- Joule/power-efficiency claims.

## Self-Review

### 1. Spec coverage
Sections 1–20 map to Tasks 1–10. No approved numerical/profile/budget/repetition/STOP requirement is intentionally omitted. Local Ryzen execution remains deferred because the spec explicitly does not grant automatic execution allowance for it.

### 2. Step scan
Each implementation task separates RED test, minimal implementation, GREEN verification, and review checkpoint. GCP execution tasks are also one-at-a-time and gate the next numerical action on durable evidence.

### 3. Type/interface consistency
`profiles.py` owns exact constants; `system_guard.py` owns enforcement/receipts; `run_v1.py` owns fresh production V1 invocation/admission; `campaign.py` owns upper budget/outcome/schedule; `analyze.py` owns read-only summaries. No V1 file is a write target.

### 4. Review Focus
All five Review Focus risks have explicit tests in Tasks 2, 3, and 5.

### 5. Proportion
The plan specifies interfaces, tests, and execution gates rather than implementation bodies. It does not duplicate V1 numerical code.

## Execution Handoff

This plan must be reviewed and approved by the designer before Task 1 implementation starts.

Recommended approach: **Subagent-driven**. Tasks 1–6 are separable implementation/review units, while Tasks 8–10 are high-consequence VM execution gates. A fresh reviewer between tasks costs more context but is justified because a guard/ledger bug can make otherwise-correct benchmark numbers unusable.

If the designer chooses Native execution instead, use `superpowers:executing-plans` and keep the same per-task review checkpoints.

## 2026-10-07 Operational namespace amendment (승인된 변경 기록)

Task 9 최초 초기화의 실제 STOP 원인: 기존 Task 8 TEST_ONLY evidence가 있는 `artifacts/`를 missing 운영 ledger의 root로 사용하여 reset 방지 규칙이 초기화를 거부했다. 기존 Task 8 evidence를 이동·삭제·수정하지 않기 위해 승인된 운영 root를 `compute_metabolism/v0/artifacts/operational/`로 분리한다. 위 Task 9의 `artifacts/budget.json` 생성 경로와 실제 campaign 배치 지시는 이 amendment로 대체하며, 원래 지시는 변경 이력으로 보존한다. Task 8 preflight namespace는 그대로 둔다.

1. RED: Task 8 TEST_ONLY siblings가 있어도 operational/budget.json 최초 생성이 가능해야 함을 검증한다. operational 자체가 nonempty이고 budget이 없거나 실제 운영 evidence를 남긴 채 budget만 삭제한 경우에는 기존 reset 거부가 유지되어야 한다. sibling evidence 및 그 증가분은 operational retained accounting에서 제외한다.
2. 최소 변경: campaign 고정 ledger 경로와 연결된 config/test fixture를 operational/budget.json으로 변경한다. `CampaignLedger.open()`, V1 source/numerical contract 및 system guard CPU 제한 구현은 변경하지 않는다.
3. GREEN: 관련 campaign/analysis/V1-wrapper 회귀, git diff --check 및 승인 V1 40-file source binding 검사를 수행하고 fresh read-only review를 받는다.
4. Review 통과 후 campaign source 및 amendment가 포함된 spec/plan의 필요한 bytes만 GCP에 배포한다. 기존 wrapper/준비된 binary와 Task 8 evidence는 보존한다. 운영 root는 operational/, campaign은 operational/<campaign-id>/로 고정한다.
5. 운영 ledger 초기화를 정확히 1회 시도한다. 누적 wall 4200초, operational retained ceiling 3,221,225,472 bytes, run deadline 180초, writer 671,088,640 bytes, post-run threshold 100,663,296 bytes, memory 4,294,967,296 bytes, swap 0을 유지한다. Task 8 TEST_ONLY 사용량은 소급 산입하지 않는다.
6. 초기화 결과와 namespace, source/spec/plan hashes, instance ID 및 boot ID를 보존하고 STOP한다. 이번 승인은 Gala warm-up, Task 8 probe 반복, Task 10 또는 staging/commit/push를 포함하지 않는다.


## 2026-10-07 Environment identity + campaign restart amendment (승인된 변경 기록)

Task 9의 첫 warm-up은 준비 당시 platform 문자열과 현재 live platform의 차이를 영구 runtime identity 불일치로 판정하여 ENVIRONMENT_INVALID로 STOP했다. prepared execution-environment.json은 당시 provenance로 원본 bytes/hash를 보존한다. 아래 변경은 이전 승인 설명을 지우거나 실패 이력을 덮어쓰지 않고, prepared identity와 campaign 동안 유지할 live identity를 분리한다.

- Prepared exact identity: Python version/executable, installed package set/version, pinned runtime file hashes, V1 source count/binding/source match. 준비 당시 platform은 provenance이며 exact-match 기준에서 제외한다.
- 새 formal campaign 초기화 직전 live observation으로 얻은 platform을 campaign-environment.json에 저장하고 config/input SHA-256으로 bind한다. 특정 kernel/platform 문자열을 source에 하드코딩하지 않는다. 모든 attempt에서 live platform과 campaign platform, before/after platform, instance ID, boot ID, topology가 일치해야 한다.
- 기존 operational/budget.json 하나를 계속 사용한다. 새 campaign은 명시적 restart_from_campaign_id 및 restart_from_finalization_sha256을 config에 bind하고, 현재 campaign의 durable STOP finalization 및 proof hashes를 검증한 경우에만 생성한다. RUNNING은 null, 모든 기존 attempts는 FINISHED여야 하며, 새 ID는 달라야 하고 새 namespace는 없어야 한다. finalization/proof의 campaign/config, attempts, wall 및 STOP 정책 근거도 검증한다.
- 기존 binding을 formal_campaign_history에 보존하고 predecessor STOP identity와 successor binding을 campaign_restarts에 추가한다. 기존 attempt/finalization/evidence는 변경하지 않는다. 역사 campaign은 읽기 전용으로 조회할 수 있지만 run-next 실행 권한은 없다.
- 기존 guarded wall 1.0627413820002403초와 retained accounting/history를 이어간다. 새 campaign은 추가 allowance나 reset을 발급하지 않으며 총 4200초/3 GiB, 180초 deadline, 640 MiB writer reservation, 96 MiB retained threshold, 4 GiB memory/swap 0은 유지한다. CampaignLedger.open()의 reset 거부 계약, V1 source/numerical contract 및 system_guard CPU 계약은 변경하지 않는다.
- 이번 승인 실행은 RED → 최소 구현 → 관련 회귀 GREEN → fresh read-only review 후 필요한 wrapper/spec/plan 배포, live environment 재확인, successor formal campaign 정확히 1개 초기화 및 accounting/history 연속성 확인까지다. 이후 STOP한다. 두 번째 N=1 Gala warm-up, Task 10, Task 8 probe 반복, staging/commit/push는 포함하지 않는다.

## 2026-10-07 Adaptive execution and validation amendment

설계자의 후속 승인으로 적응형 registry/detector/selector, campaign profile pinning, 비인증 observation/candidate/independent promotion, prepared helper 및 실패 CPU accounting을 함께 구현한다. 상세 순서와 조건부 GCP 실행은 `2026-10-07-compute-metabolism-adaptive.md`에 기록한다. 이전 amendment와 STOP 기록은 삭제하거나 소급 변경하지 않는다. CLEAN 후 GCP 관찰까지 진행하며, 독립 검증된 GCP profile이 존재할 때만 새 successor와 fresh 2C N=1 한 번을 허용한다. N=3/Task10과 budget reset/increase, Git mutation은 계속 금지다.

## 2026-10-08 execution ownership amendment (append-only)

The actual Gala observation `observation-gala-evex-01` stopped before child creation:
its root-owned 0755 attempt directory could not be written by UID 1000 / GID 1003.
This is an orchestration failure, not a verdict about the new CPU path. Preserve
that attempt, its STOP finalizations, unavailable measurements and all old evidence.

One immutable system-unit execution identity must supply both systemd credentials
and artifact ownership. Exclusively create the run directory and writer quota,
restrict them to 0700 and 0600, apply the execution owner's UID/GID, then read actual
ownership/type/mode back. Recheck both filesystem ownership and systemd argv identity
before launch. Preparation failure or mismatch refuses before starting any unit.
No 0777, user-unit fallback, CPU contract change or EVEX semantic change is authorized.

`system_guard.py` is outside the 49-file V1 numerical source snapshot but inside the
complete gate source authority. Keep the physical V1 binding 104578c1... and its old
receipts unchanged; issue a fresh guard-inclusive gate binding, source-epoch hash,
review and regression receipts. A different V1 digest must not be invented for
unchanged V1 bytes. The new campaign binds the complete new gate manifest.

Only GCP executes permission tests, related regression and numerical work. After
CLEAN review, first perform a small system-unit file-write check without Gala or a
Task 8 CPU/timeout rerun. Then initialize one explicitly last-STOP-linked successor
on the existing upper ledger (16.948194404001697 seconds, four attempts, 9210281 bytes
at authorization). No new allowance or reset. Observe one original Gala call in
uncertified mode. Independent promotion must close all original call/library/input,
13 instruction, complete state/effect and negative-test obligations. Failure STOPs.
Only VERIFIED permits one fresh 2C N=1 warm-up; if an observation STOP requires it,
one additional same-upper STOP-linked successor is authorized. Stop after that N=1
regardless of result. N=3, Task 10, staging, commit and push remain unauthorized.
### STOP-linked observation-only successor clarification

The original APIs require a STOP owned by the current formal campaign and a
VERIFIED execution profile for numerical campaigns. A fresh unknown-route successor
has neither. The authorized connection therefore declares OBSERVATION_ONLY in its
frozen config and binds exactly one run ID, profile 2C, no certified state progress,
fingerprint, source epoch, registry and GDB hashes. It supplies no execution profile.
Initialization still verifies the explicit predecessor STOP with the existing full
history/hash/allowance checks. The first observation rechecks its unique recorded
restart link using a read-only predecessor view; it never writes that view to the
ledger. Zero own attempts, no own closing receipt, all prior attempts FINISHED and
RUNNING null are required. A second observation cannot consume this authority.
Numerical run_next is refused before launch. The observation policy has no numerical
next item and records a genuine single-authorization STOP without changing the raw
observation outcome. A subsequent numerical successor must bind an independently
VERIFIED profile and that observation STOP; ordinary campaign policy is unchanged.