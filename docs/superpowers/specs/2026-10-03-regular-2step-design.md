# Regular 2-Step Chain execution spec

Authority: the user's complete pasted request, preserved byte-for-byte in
`D:/numerical-audit-lab-regular-2step-delivery-2026-10-03/USER_REQUEST.md`.
The live instruction "이번에는 끝나면 푸시까지 ㄱㄱ" overrides the pasted no-push
and completion-condition no-push items. Push the completed feature branch;
do not fetch or merge. All other requirements remain binding.

## Goal and existing premises

Build regular init + complete 2-step, connecting audited init/step1 V2
endpoint through the externally audited caller transition to newly acquired
step2 execution, Numeric IR and unchanged frozen V2 Forms.
The received Caller external audit is PASS on HEAD
`43f1e9b21a014520facb5a545846d648eb67b288`; its original ZIP and report are in
`current/caller-external-audit-2026-10-03/`. Earlier init/1-step Trace/IR/V2
and the Caller Gate remain CLOSED / PASS only within their existing scopes.
The new chain remains IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING
after successful implementation and internal checks.

## Architecture

Add a sibling `runtime_trace/regular_2step/` package. Reuse existing acquisition
and graph/schema machinery without changing its files, plus frozen
`lab/v2_bound.py:Form/step_forms`. Before reusing the step1 template, independently
compare actual step1 and step2 instruction/control/helper sequence and operation,
storage-role and boundary topology against packaged frozen ELF bytes.
Same centers are never proof of the same dynamic occurrence.

A new regular production n_steps=2 acquisition may execute/capture the earlier
regions to establish process-local binding, but the new proof claim is the
second body. The new acquisition must reach step2 return and normal harness
completion; preserve all raw reads/writes, control, modules and source receipts.
Use the existing exact n_steps=2 sibling harness, including save_all.
No direct kernel harness and no source-only or reconstructed execution evidence.

Maintain known/audited-lineage and separately acquired fresh cases. Each has a
unique acquisition identity. Binding to the old audited caller entry compares
logical roles, bits and provenance; do not claim old and new process addresses
are identical. Require fresh process-local step1 endpoint to step2 entry links
and reject cross-acquisition swaps even when component bits happen to match.

The production IR producer may reuse audited graph internals/template rules;
the semantic checker must not import acquisition, producer, adapter or frozen
V2 propagation as a proof oracle. It independently checks actual raw arithmetic,
graph identities and exact-rational IEEE-754/Form propagation. Existing audited
checkers may validate their unchanged components; their results are not a
substitute for checking new semantic handoffs.

## Boundaries and composition

Carry each q/full_v/latent lane's exact audited terminal dynamic source, center,
serialized Form and shared basis through the accepted caller contract.
grad_v starts as a fresh exact-zero state; t is the newly loaded time root;
dt binds to the actual argument; incidental GPR/XMM are fresh entry roots.
Give all new dynamic values acquisition + step2 namespaces, including copies
and equal-bit occurrences. Preserve arithmetic operand order.

The upper REGULAR_2STEP_CHAIN_V1 artifact contains identities, ordered component
hashes, initial/intermediate/final boundaries and a completion hash. Its checker
checks semantic joins, not just hashes; it does not replace sub-checkers.
All lower checks must succeed before publishing the completion artifact.

## Failure, mutation and preservation

Unknown forms, missing observations, malformed receipts and unsupported structure
are REFUSED. If structure differs, describe the difference and contract only that
new path; do not force the prior topology onto it. Preserve failed captures and
all superseded evidence without rewriting existing pinned outputs.
Save actual mutation inputs/results, receipt repairs and declared trust modes.
Cover all 15 requested mutation classes. Distinguish hash/trust refusal from
semantic refusal after fully repairing completion and component hashes.

Protect all 1,488 baseline tracked files, especially trace/IR/V2/caller evidence,
frozen binaries and core/checker source. Only adding evidence attributes and new
status documents is authorized initially. If an existing asset must change,
first report why, which premise it affects and the additional audit scope.

## Verification and delivery

Complete new tests and unchanged Caller 101 + regular 479 suites. With unchanged
frozen/core no -n6 LOCAL FULL expansion is needed. Interrupted runs are failures,
not PASS. Pin tested Python sources through final documentation/package changes.
Record elapsed implementation time, new/reused LOC/modules, acquisition attempts
and failures, added checker functions and pytest elapsed time.
Create a manifest/SHA/size-verified ZIP, exact HEAD snapshot, Git bundle and
independent bare recovery/fsck/ancestry record, retaining failure history.
Commit and push feature branch only after these checks; verify advertised remote
HEAD without fetch/merge. Report branch, final HEAD, clean state, changed files,
ZIP size/SHA and actual push result. External audit remains PENDING.

## Bounds

No 3/10/100-step, general N-step correctness, trajectory correctness, global
accumulated error, shadowing, observable or physical accuracy claim. The prior
caller audit exercised zero symbolic coefficients with nonzero box; preserve
that coverage limit. Do not claim cross-system or ASLR diversity merely from
two different processes. If this needs thousands of new framework lines or
5-6 hours again, raise general step template/induction as a design issue after
this two-step result and do not expand to the next step.
