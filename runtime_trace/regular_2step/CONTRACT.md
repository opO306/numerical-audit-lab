# Regular two-step acquisition contract

## Scope and refusal boundary

This package captures one unchanged regular `integrate_orbit(..., n_steps=2)`
execution in a new native process.  It records `c_init_velocity`, the first
`c_leapfrog_step`, the second `c_leapfrog_step`, both returns, and normal Python
harness completion.  It does not resume the stopped process from an older
caller audit.  The old/new link is only a comparison of logical roles, exact
bits, and recorded argument provenance.

Unknown instruction effects, missing PRE reads, unreadable memory, unregistered
ELF bytes, malformed receipts, a non-normal exit, a missing body, and a
cross-acquisition handoff are `REFUSED`.  The proof is limited to the pinned
gala 1.12.0 manylinux x86-64 wheel, packaged frozen ELF files, this regular
input, and these two process-local dynamic calls.  It is not an N-step,
trajectory, physical-accuracy, cross-machine, or independent-audit result.

The protected `runtime_trace/harness_nsteps2.py` differs from `harness.py` by
exactly the first source token `n_steps=1 -> n_steps=2`.  Its human docstring and
emitted `harness_output.json.n_steps == 1` remain inherited stale metadata.  A
capture proves two steps only through that exact source-byte proof plus two
observed native step entries and returns; it never treats the stale field as the
execution count.

## Definition-only reuse

`gdb_acquire.py` parses the pinned `runtime_trace/gdb_capture.py` and compiles
only its leading imports, constants, functions, and `Capture` class definition.
It stops before the first executable top-level GDB command, so the original
one-step capture is not launched.  `Regular2StepCapture` subclasses that class
and reuses its instruction decoding, raw register/memory capture, byte-flow
tracking, arithmetic checks, ELF correspondence, and restricted opcode set.
The subclass adds the second dynamic body, occurrence labels, segment bases,
all classifier-required PRE memory reads, possible write pre/post bytes, process
identity, and normal-completion evidence.  After the actual step1 RET, it also
loads only the definition prefix of the pinned caller `gdb_acquire_reads.py`
and reuses `Acquisition.one("caller")` on the same inferior/thread until the
actual CALL lands at step2 entry.  It does not re-execute the RET.  The original
sources are unchanged.

`read_effects.required_reads` and
`write_effects_reads.possible_writes` are reused only as acquisition-time effect
classifiers.  `structure.py` does not import acquisition code.  It checks the
raw rows, frozen files, hashes, roles, and a new `objdump` result independently.

## Paths and exact final file set

The authoritative captures are
`runtime_trace/regular_2step/artifacts/{known-03,fresh-03}/`.  The complete
`known-01`/`fresh-01` and `known-02`/`fresh-02` directories are immutable
historical Task-1 evidence; they remain byte-for-byte preserved under their
original source pins, but are superseded by later checker/source contracts.
Each authoritative directory contains exactly:

- `trace.jsonl`
- `capture.json`
- `execution.json`
- `source_pinset.json`
- `acquisition_seal.json`
- `harness_output.json`
- `gdb.log`
- `structure_report.json`

Failed and exploratory runs use new exclusive numbered directories under
`D:/numerical-audit-lab-regular-2step-delivery-2026-10-03/`; they are retained
and never converted into successful evidence.

## `trace.jsonl` row schema

Every line is one actual retired instruction.  Body rows have the original
capture fields: `seq`, `pid`, `ptid`, `phase`, `step`, `symbol`, `module_path`,
`module_sha256`, `module_load_base`, `runtime_pc`, `elf_address`,
`elf_file_offset`, `mapping`, `bytes`, `instruction`, `opcode`, `kind`,
`operands`, `pre`, `post`, `post_pc`, optional `changed_gpr_results`, optional
`result_bits`, and `chain`.  `phase` and added `occurrence` are exactly one of
`init`, `step1`, `step2`.  The inherited numeric `step` field remains `0` for
init and `1` for either step body; consumers use `occurrence` plus sealed region
ranges for dynamic identity.

Rows between step1 RET and step2 entry preserve the audited
`gala-caller-transition-instruction-v2` fields (`sequence`, `pc`, `next_pc`,
module/ELF fields, assembly/bytes, pre/post, PRE reads, possible writes,
thread, and its local chain) and add acquisition-global `seq`, `pid`, `ptid`,
`occurrence=caller12`, and `chain`.  One sealed stream therefore binds the body
RET, every actual caller instruction, and step2 entry without a second
execution or reconstructed row.

Each operand records `kind`, width, access, raw bits, origins, and for memory an
actual address.  `pre` and `post` include GPR/XMM values, MXCSR, EFLAGS, and
FS/GS bases.  Added `pre_memory_observations` lists every required read as
`address`, `size`, classifier `kind`, assembly `operand`,
`timing=PRE_INSTRUCTION`, `bytes_hex`, `status=OK`.  Added
`possible_memory_writes` lists every possible write as `address`, `size`,
classifier `kind`, `before_hex`, and `after_hex`.  The reused classifiers cover
implicit RET/POP/LEAVE reads, indirect control reads, and CALL/PUSH stack
writes.  Unsupported effects refuse acquisition.

`chain` is SHA-256 of the previous 32-byte chain value concatenated with the
canonical JSON bytes of the current complete row excluding `chain`; the initial
chain is 64 zero hex characters.

## `capture.json` schema

Schema is `gala-regular-2step-runtime-trace-v1`, verdict `CAPTURED`.  It records
`case`, unique `acquisition_id`, counts, opcode histogram, modules, trace hash,
chain endpoint, GDB/wheel/source receipts, `process_identity`, normal completion,
definition-only reuse, harness binding, antecedent binding, and the
process-local handoff.

`process_identity` is exactly `linux_boot_id`, inferior `pid`, and
`proc_stat_start_time_ticks`.  Each region has `occurrence`, runtime entry and
return PCs, half-open `[start_seq,end_seq)` row range, component pointers,
`start_state`, `end_state`, `t_bits`, `dt_bits`, MXCSR, owner PTID, scheduler
state, and entry stack observations.  Component state maps each of `q`,
`full_v`, `latent`, and `gradient` to two ordered binary64 bit strings.

`process_local_handoff` binds step1 return to step2 entry inside one
`acquisition_id`.  It records `q/full_v/latent` from/to bits and pointers.
It also binds the unchanged process-local gradient pointer to the actual
function-entry stack observation, requires the caller corridor's observed
write transition from the step1 gradient bits to exact zero, and requires both
step2 gradient lanes to be exact zero.  Equal bits with a different acquisition
ID are rejected.

For each protected role, replay requires one equality chain from the measured
step1 `end_state` and pointer through handoff-from, Caller start state and
protected pointer, Caller end state and entry-ABI pointer, handoff-to, and the
measured step2 `start_state` and pointer.  The Caller receipt carries the same
source acquisition ID and exact protected role set.  Only after this join does
the checker apply actual Caller-row no-write observations to those ranges.

`caller_corridor` records its half-open global row range, the step1-RET post PC,
step2 entry PC/ABI, start/end component bits, actual `t`/`dt` load provenance,
local caller chain/counts, module maps, all writes including same-value writes,
and the definition-only source receipt.  The checker requires its first PRE PC
to equal the actual body RET post PC, its last `next_pc` to equal the actual
step2 entry, zero writes overlapping q/full_v/latent, unchanged component bits,
and instruction/read/write-effect equivalence to the selected immutable old
caller trace (excluding the old trace's separately executed RET row).  This is
a same-process internal instantiation check; it does not expand the external
Caller audit beyond its two old acquisitions.

`antecedent_binding` points to the immutable caller capture and its SHA-256.  It
compares `q/full_v/latent/gradient`, `t`, and `dt` by logical role and exact
bits, requires exact-zero gradient, retains the old caller provenance and the
new process's actual source rows for `t` and `dt`, and binds the new gradient
pointer to its stack observation.  It records both process identities as
distinct, denies any cross-process address-equality claim, and sets
`old_capture_continuation_claimed=false`.

## Other receipt schemas

`execution.json` uses `regular-2step-execution-v1` and records the exact command,
cwd, launcher/inferior identity, return code, wall time, environment/package
versions, source pins, harness source proof, normal completion, and that no
machine mapping was read during acquisition.  Normal completion requires a
GDB exited event with exit code zero, the original inferior PID, the selected
inferior becoming zero, and the matching sealed `exited normally` transcript.

`source_pinset.json` uses `regular-2step-source-pinset-v1`; `files` and
`exact_key_set` cover every reused acquisition source and new launcher/GDB/
checker/contract source before GDB starts.

`acquisition_seal.json` uses `regular-2step-acquisition-seal-v1`.  It seals the
six already-existing raw/receipt files by SHA-256 and declares the exact eight
final file names.  `structure_report.json` is produced only after validating
that seal and hashes the seal, capture, and trace.

`structure_report.json` uses `regular-2step-structure-report-v1`.  A
`REUSE_PROVEN` verdict requires contiguous init/step1/caller/step2 coverage,
the RET/corridor/entry seam and caller effect/non-overlap proof, matching process
identity, complete observations, raw instruction bytes at the packaged ELF
offset, an independent `objdump` decode, identical step1/step2 module-relative
instruction/byte order, identical control targets, and identical normalized
operation/storage roles.  Runtime addresses and value bits are not used as a
substitute for structure.  The report separately retains step1/step2 `t`, `dt`,
gradient-start differences, and the final endpoint bits.  Every raw row must
also satisfy runtime-PC/load-base/ELF-address equality, PRE/POST RIP equality,
executable mapping membership, and continuity within each fully traced region
and across the step1/caller/step2 seams.  The harness output must be canonical
64-bit hex and exactly equal step2's final q/full_v endpoint.

Fresh acquisition requires `--distinct-from` naming the authoritative known
capture.  The sealed fresh receipt binds the known capture hash, acquisition
ID, trace hash, and process identity and proves all three differ from fresh.
`structure.compare_pair` replays both complete captures.  It compares logical
roles, bits, and provenance across processes and never requires ASLR runtime
addresses to match.
