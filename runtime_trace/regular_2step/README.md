# Regular init + complete two-step chain

This sibling package proves only the recorded regular two-step executions on
the pinned Gala 1.12.0 binary. External independent audit of this new chain is
pending. The old one-step and Caller external PASS remain limited to their
original immutable evidence. No N-step, trajectory, global accumulated error,
shadowing, observable, physical accuracy or cross-machine claim is made.

The acquisition contract is [CONTRACT.md](CONTRACT.md). Authoritative inputs
are `artifacts/known-03` and `artifacts/fresh-03`, two separately acquired
process executions; this is not evidence of ASLR diversity. Their eight-file
sets are unchanged. The public checker accepts only their literal paths,
acquisition IDs, seal hashes and structure-report hashes.

## Producer and independent checks

`producer.build(capture_dir, out, root)` uses the unchanged old translator's
`_Dataflow` on the actual second-body rows. Every new value ID is prefixed by
the acquired process identity hash and `/step2/`. The acquired global row
numbers are retained; the inherited numeric `step=1` field is not the dynamic
occurrence identifier. The only entry-tag seam assigns the new acquisition's
per-byte XMM origin suffixes. It does not alter raw trace rows or old sources.

All six protected entry lanes are new LOAD occurrences with explicit CARRIED
Form bindings. Each points to the old audited terminal COPY/source and Form
source, the proven-equivalent new step1 terminal occurrence, the same-process
caller corridor and pointer, and the new step2 entry state. The exact Form
coefficients, nonzero box and shared basis are preserved. Gradient has two
fresh exact-zero lanes; time is the newly loaded t[2] root; dt is the actual
caller argument load. Entry register roots are fresh.

The producer invokes unchanged `lab.v2_bound.Form/step_forms` for every actual
arithmetic operation and reuses `_Execution` for COPY/state serialization.
Its result includes every ordered operation/input identity, selected state,
entry boundary and all eight final component lanes. The frozen source hash,
K=4 and operator identity are serialized in `frozen_v2`.

`checker.check(capture_dir, derived_dir, root)` imports no acquisition,
producer, adapter or frozen propagation code. It reuses the unchanged
independent byte-storage `_Reconstruction`, raw effective-address/flow and
ELF-disassembly checks. Arithmetic results additionally undergo exact rational
IEEE-754 round-to-nearest/even comparison, including signed zero. Form
propagation uses the SHA-pinned received independent audit script's definitions
and separate Fraction/upward-rounded arithmetic. Its old top-level case loop
is never executed. The script and archive byte hashes are constants in
`form_oracle.py`; no evaluator is used as the new checker's proof oracle.

Before transferring old endpoint Forms, the checker runs the old IR and Caller
checkers and the received independent old V2 reconstruction. It compares the
new init+step1 complete graph, all ordered scalar bits and roots to the selected
old audited block. Module-relative instruction bytes and control are exact.
Every memory range is first resolved against all captured module PT_LOAD
segments. Module data/control reads retain SHA, module RVA, width and access;
ELF constants also retain their file offset. Ambiguous or cross-segment ranges
are refused. Only verified nonmodule nonnumeric heap routing memory is normalized by
first-observation byte ordinals: this is a bijection preserving every observed
alias and overlap. Component, stack and module roles remain exact. Actual
effective addresses are checked independently. For CONTROL memory operands,
the new closed checker accepts only observed `ff25 disp32` JMP (PC + 6 + signed
displacement), `ff14e8` CALL (pre RAX + 8 * pre RBP), and `c3` RET (pre RSP),
all 8-byte reads; unknown encodings refuse. Other flow/EA checks reuse the old
independent raw checker. Equal scalar bits do not stand
in for storage identity. The focused alias regression changes one overlapping
heap byte and detects the structural difference.

The init-return to step1-entry caller gap remains **untraced**, as in the
accepted old one-step component contract. No continuous caller evidence is
invented at that seam. Continuous acquired caller evidence is specifically
step1 RET through the caller to step2 entry. The old stopped process is never
described as resumed.

## Artifacts and publication

Each `artifacts/derived/{known,fresh}/` contains `numeric_ir.json`,
`v2_correspondence.json`, `endpoint.json`, full lower `components.json`,
`checker_report.json`, and `chain.json` (`REGULAR_2STEP_CHAIN_V1`). The chain
binds the ordered old correspondence/caller/new trace/IR/V2 identities, initial,
intermediate and final boundaries, ordered component hashes and completion
hash. Hash repair alone cannot satisfy semantic joins.

The producer exclusively creates the output directory, writes into `.pending`,
runs the independent checker there, then publishes `chain.json` last. Failures
retain `.pending` and `failure.json` without a published completion. Existing
evidence is never overwritten. The checker report is an output receipt, not a
trusted input that can bypass checking.

```bash
PY=/home/otherside123/venvs/gate2c1-trace/bin/python
$PY -m runtime_trace.regular_2step.producer --root . \
  --capture runtime_trace/regular_2step/artifacts/known-03 --out /new/exclusive/known
$PY -m runtime_trace.regular_2step.checker --root . \
  --capture runtime_trace/regular_2step/artifacts/known-03 --derived /new/exclusive/known
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $PY -m pytest -q \
  runtime_trace/regular_2step/tests/test_step2_chain.py \
  runtime_trace/regular_2step/tests/test_step2_mutations.py
```

## Negative evidence and limits

`mutations.generate(root, out)` saves full copied numerical inputs, before/after
hashes, repair receipts and checker results for all 15 requested semantic
classes, plus separate hash and trust controls. The private
`_TEST_ONLY_REPIN_check` exists only for copied local fixtures after enclosing
hash repairs. No public CLI flag changes trust. Original absolute execution
paths in repair receipts are historical provenance; relocation requires fresh
test-only path binding or regeneration in an exclusive directory. The
generator is reproducible from the immutable raw cases and derived baselines.

The concrete chains carry zero symbolic coefficients with nonzero boxes.
Separate arithmetic unit tests compare explicit nonzero symbolic coefficient
Forms for ADD/SUB/MUL; this does not establish native nonzero-coefficient
caller coverage. This is an internal implementation/checker result, never a
new external audit closure. General step templates and induction require a
separate design decision after this narrow two-step result.

## Validation and final audit delivery

Task 3 validation receipts are under `artifacts/validation/`. The authoritative
final runs are `final-new-63`, `final-caller-101`, and `final-regular-479`; older
Task 3 logs preserve wrapper/exit-receipt failures and are not the final PASS
receipts. `mutation_replay.json` enumerates the only allowed replay differences:
the 17 private TEST_ONLY capture-directory paths. `source_test_map.json` and
`protected_baseline.json` record source identity, physical LOC and baseline
byte/blob preservation.

After Task 3 and whole-branch review, build the final package once from the
reviewed clean HEAD into a new exclusive destination:

```bash
PY=/home/otherside123/venvs/gate2c1-trace/bin/python
$PY -m runtime_trace.regular_2step.delivery \
  --history /mnt/d/numerical-audit-lab-regular-2step-delivery-2026-10-03 \
  --out /mnt/d/numerical-audit-lab-regular-2step-delivery-2026-10-03/final-delivery
$PY -m runtime_trace.regular_2step.delivery \
  --verify /mnt/d/numerical-audit-lab-regular-2step-delivery-2026-10-03/final-delivery
```

The build refuses an existing destination, dirty tree or wrong branch. It
contains no push operation. The controller records the authorized push and
remote-ref verification only after the package has been sealed and verified.

The helper also refuses until the final commit archive matches every
production/test Python path and SHA-256 in
`artifacts/validation/source_test_map.json`. Documentation entries in that map
are byte-pinned as well. After the scoped Task-3 fix review and fresh
whole-branch review both approve that exact commit, the controller creates
`.superpowers/sdd/2026-10-03-regular-2step/final-reviewed-tested-head.json` with
this schema:

```json
{
  "schema": "regular-2step-final-reviewed-tested-head-v1",
  "git_head": "<40-hex reviewed and tested HEAD>",
  "source_test_map": {
    "path": "runtime_trace/regular_2step/artifacts/validation/source_test_map.json",
    "sha256": "<hash of the committed map>"
  },
  "reviews": [
    {"path": "task-3-review.md", "sha256": "<hash>", "disposition": "HISTORICAL_NEEDS_FIXES"},
    {"path": "task-3-fix1-review.md", "sha256": "<hash>", "disposition": "APPROVED"},
    {"path": "whole-branch-review.md", "sha256": "<hash>", "disposition": "APPROVED"}
  ],
  "review_gate": "APPROVED"
}
```

The initial `task-3-review.md` remains required historical evidence but cannot
satisfy either approval. The helper requires exact hashes for that report, the
approved `task-3-fix1-review.md`, and approved `whole-branch-review.md`, plus
the exact current HEAD and committed source-map hash, before it creates a stage
directory or ZIP. The controller generates this ignored workflow receipt only
after both approvals; no placeholder receipt is accepted.
