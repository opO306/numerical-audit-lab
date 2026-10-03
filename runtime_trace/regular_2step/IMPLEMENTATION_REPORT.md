# Regular init + complete two-step implementation report

## Result and limits

The narrow result is **IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING**.
It covers the two recorded regular executions on the pinned Gala 1.12.0 bytes.
It does not close an external audit of the new chain and does not establish
3-step, general N-step, trajectory, accumulated-error, shadowing, observable,
physical-accuracy, cross-machine or ASLR-diversity claims. Concrete native carry
Forms have zero symbolic coefficients and nonzero boxes; an independent unit
test with nonzero coefficients is narrower than actual native carry coverage.

The prior Runtime Trace → Numeric IR, Numeric IR → frozen V2 and Caller Gate
external PASS scopes remain attached only to their immutable evidence. The
received Caller report and ZIP identities are recorded in
`current/REGULAR_2STEP_RECEIVED_AUDIT_IDENTITY.json`; no root/worker review in
this work is described as a new external audit.

## Implemented chain

Task 1 acquired `known-03` and `fresh-03` through the production n_steps=2
harness. Each has 1,428 actual instruction rows, two observed native step calls,
normal process completion and a machine-checked step1/step2 structural reuse
report. The inherited harness output field still says `n_steps=1`; it is preserved
as stale metadata. Two-step execution is established by exact source token proof,
two native entries/returns and normal completion rather than rewriting that field.

The process-local join carries measured q/full_v/latent bits and pointers from
step1 endpoint through the actual caller corridor into measured step2 entry.
Gradient is reset by observed writes to exact zero, t is the actual t[2] load and
dt is the actual second-call argument. The old stopped caller process is never
treated as resumed. The new caller instantiation is internally checked against
the old template and is not newly externally audited.

Task 2 builds the actual second-body Numeric IR, frozen V2 correspondence,
endpoint and `REGULAR_2STEP_CHAIN_V1`. Dynamic IDs are acquisition/step2 scoped.
The independent checker reconstructs raw graph/storage identity, exact IEEE-754
and Forms without using the producer or frozen evaluator as its proof oracle.
It retains full PT_LOAD module operand identity and independently recomputes the
three observed CONTROL memory EAs: `ff25 disp32`, `ff14e8` and `c3`.

Authoritative completion hashes are:

- known: `f44d2edfca32d6b7fc14429a818a16995da9f6e5e869cfdf22e5da2872e91401`
- fresh: `bcf9b24f5e62394a74508b97f2881d9b4d172e7f9a23e700cefc0cd2bb78429b`

## Final regression and mutation replay

All final commands used `/home/otherside123/venvs/gate2c1-trace/bin/python`,
Ubuntu-24.04, `PYTHONPATH=.` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

- `runtime_trace/regular_2step/tests`: 63 passed in 165.06s, exit 0.
- `runtime_trace/caller_transition/tests`: 101 passed in 60.61s, exit 0.
- `tests runtime_trace/tests runtime_trace/numeric_ir/tests runtime_trace/numeric_ir/v2/tests`:
  479 passed in 203.81s, exit 0.
- Each final JUnit has failure 0, error 0, skip 0. Final distinct total is 643.

The first new-suite wrapper completed 63 tests in 167.54s, then failed while
trying to execute an invalid numeric `exit`; it is preserved as a wrapper
failure. A second new run and first Caller/regular runs produced complete PASS
logs/JUnit but empty exit files due the same quoting defect. They are retained,
counted as actual pytest time, and are not the final exit receipts. A preserved
shell script then produced the three final numeric exit-0 receipts. Renaming the
first log set was a move, not another execution, and is not double-counted.

An explicit mutation replay generated a new 273-file tree in an exclusive OUT
directory and exited 0 in 111.15s. Against the authoritative 274-file tree,
`copy_receipt.json` exists only in the original as historical copy provenance.
Of 273 common files, 256 are byte-identical. Each of the 17 `repair.json` files
differs at exactly `/test_pins/capture_directory`, with before/after paths fully
enumerated in `artifacts/validation/mutation_replay.json`. All results, manifest,
substantive payload, repair hashes, arithmetic, IDs, bits and stages are equal:
15 SEMANTIC refusals plus HASH and TRUST controls.

## Protection, size and scaling

The baseline verification re-read the original 1,488-entry preflight map. The
baseline commit's raw SHA/Git blobs match every entry; at current worktree bytes,
1,487 remain unchanged and `.gitattributes` is the sole authorized metadata
delta. The wheel, leapfrog `.so` and `lab/v2_bound.py` pins match. Old 01/02 raw
captures, Task 1/2 failed and superseded attempts, historical reports and original
external audit bytes remain preserved.

New package production code is 2,813 physical lines: Task 1 1,537, Task 2 801,
Task 3 delivery 475. Tests are 736 physical lines. The exact source/test hashes,
line counts and function counts are in `artifacts/validation/source_test_map.json`.
Bounded reuse counts 891 exact Task-1 selected/direct definition lines, 1,621
Task-2 named definition lines and a separate 238-line received audit definition
prefix. These counts do not claim every line of a reused module executed.

There were 15 actual native acquisitions, 5 failures and 10 successes; Task 2
and Task 3 added none. Total actual observed pytest time is 1,930.85s, including
all failed/superseded runs and the seven Task-3 executions, without counting a
renamed log twice. Detailed origins and each run are in `COST_REPORT.json`.

The 2,813 production lines trigger the user's thousands-of-lines scaling rule.
This does not prove the method mathematically unscalable, but it requires a
separate regular transition template/induction design review before any 3-step
or N-step extension. No such extension is implemented here.

## Delivery lifecycle

`delivery.py` requires a clean committed `regular-2step-chain` HEAD and an
exclusive output directory. It re-verifies protected bytes, builds an exact HEAD
tar and `git bundle --all`, performs a bare clone, strict fsck and baseline
ancestry check, and reconstructs a relocated checkout. Fresh subprocess file-open
auditing denies the original checkout and every captured absolute module path;
it requires actual reads of relocated source/capture/derived/module resolver
paths and checks every `objdump` target. It then runs the normal known/fresh
semantic checker from that relocated checkout. Python runtime/stdlib dependencies
are allowed and distinguished from target evidence/module paths.

The helper also packages the complete tracked snapshot, attempt history,
workflow briefs/reports/reviews/ledger/probes and final manifest, then verifies
unique ZIP members, CRC, SHA-256 and sizes. It performs no GDB/native acquisition
and no network operation. It has deliberately **not** been executed yet: Task 3
review and fresh whole-branch review must finish first. Push is authorized but
has not been executed at this report seal; the controller will run the helper at
the reviewed clean HEAD, verify the ZIP/bundle/recovery, then push and save the
actual remote-ref receipt outside the pre-push ZIP.

## Reading boundary

Fully read for Task 3: Task 3 brief/context, complete user request, execution
spec and Task-3 plan block, accepted Task-2 fix report/review, Task-1 final metrics
report and the relevant Task-1/Task-2 source metrics/run summaries. Fully read
or implemented: delivery helper, current regular README/contract, generated
validation summaries and mutation comparison. Machine-parsed/hashed rather than
line-by-line prose: 1,488 baseline files, 273 replay files, complete raw traces,
JUnit XML, all source maps and attempt inventories. The final package, bare
recovery and relocated path audit remain unexecuted until review; no result for
those is claimed here.
