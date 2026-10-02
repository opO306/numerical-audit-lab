# Runtime Trace → Numeric IR regular 1-step independent audit

Date: 2026-10-02

## Scope

This audit is limited to:

- frozen gala 1.12.0
- regular orbit
- init + 1-step
- already-audited Runtime Trace ↔ Numeric IR

It does **not** certify Numeric IR → V2, V2 bound, 10-step, 100-step, chaotic orbit, long trajectories, a general x86 tracer, or physical correctness.

Target commit: `d679c8ba32d98e6076708b2b70b93c4eb37f5a49`

Start commit: `736b55198947bd3c8cecc024a12af156459cfa02`

Branch: `numeric-ir-regular-1step`

## Package integrity

Received ZIP:

`numeric-ir-regular-1step-d679c8b.zip`

Independently computed SHA-256:

`1c51942eed9debcf9b245e16ebb79cfb78a5449ae2e7f8aa736f69d0e666456d`

This exactly matches the supplied value.

The ZIP contains 822 entries total: `manifest.json` plus 821 manifest-covered entries. Every manifest entry was independently checked for presence, byte size, and SHA-256. Result: 0 missing, 0 extra, 0 size mismatches, 0 SHA mismatches. No unsafe/path-traversal ZIP path was found.

## Independent reconstruction method

The primary audit checker was written outside the snapshot and does not import:

- `runtime_trace.numeric_ir.translator`
- `runtime_trace.numeric_ir.checker`
- `runtime_trace.numeric_ir.normalization`
- `runtime_trace.semantics`
- `runtime_trace.correspondence`

For the audited scalar arithmetic it independently:

1. verified the raw trace SHA-256, record sequence, and record hash chain;
2. parsed ELF64 program headers directly to map ELF virtual addresses to file bytes;
3. verified packaged module SHA-256 and executed instruction bytes;
4. decoded the relevant legacy SSE scalar-double instruction bytes directly (`F2 0F 58/59/5C`, including REX/ModRM), rather than trusting the recorded opcode/kind;
5. reconstructed destination-pre/source operands using x86 ModRM and AT&T source/destination semantics;
6. reconstructed binary64 values as exact `Fraction` values and performed an independent round-to-nearest-ties-to-even conversion back to binary64 bits;
7. reconstructed byte-level value/provenance state for registers, memory, boundary buffers, stack, GPR/XMM copies, constants, zeros, zero-extension/upper-zeroing, and arithmetic results;
8. rebuilt the expected Numeric IR operation/value arrays and compared them exactly with the delivered artifacts;
9. independently canonicalized `{schema, operations, values}` and computed the normalized SHA-256.

The implementation's pre-existing checker reports, coverage reports, and normalized comparison were not used as oracles.

## Core independent measurements

For both `attempt-05` and `closure-fresh-01`:

- raw trace records: 446
- independently found scalar binary64 arithmetic occurrences: 36
- IR arithmetic nodes: 36
- phase split: init 14, step 22
- opcode split: `addsd` 12, `subsd` 8, `mulsd` 16
- value nodes: 254
- `COPY_BITS`: 135
- `ZERO_BITS`: 72
- `ARITHMETIC_RESULT`: 36
- `LOAD_BITS`: 9
- `CONST_BITS`: 2
- source-slice provenance edges: 140
- arithmetic input edges: 72
- total relevant provenance links: 212

The independently derived arithmetic trace sequences are:

`104, 105, 106, 107, 108, 111, 112, 113, 114, 139, 153, 154, 173, 174, 223, 226, 247, 250, 349, 350, 351, 352, 353, 356, 357, 358, 359, 382, 395, 396, 399, 402, 423, 424, 427, 430`

All 36 operation records matched the IR exactly for operation order, trace sequence, module SHA, ELF address, instruction bytes, opcode, operand bits, result bits, and value IDs. All 36 independently recomputed RN-even results matched the raw output bits.

The independently calculated normalized SHA-256 for each artifact is:

`1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2`

This value was calculated before comparing it with the supplied expected value. The two independently reconstructed normalized documents are exactly equal.

## A1 — Input provenance and independence: PASS

Code review showed the translator obtains source data from `trace.jsonl` and sibling `capture.json`, and obtains frozen module bytes through the packaged frozen-binary manifest. It does not call the correspondence mapping checker and does not consume `machine_mapping.json`, `T_bin`, V2 data, an existing Numeric IR artifact, or a hard-coded expected arithmetic count.

As an empirical isolation test, the source was relocated to a directory containing only `trace.jsonl` and `capture.json`; the `--root` contained only the frozen-binary manifest and packaged ELF images. Translation still produced exactly 36 operations and 254 values with normalized SHA-256 `1ba19c...8f2`.

The 36 arithmetic occurrences were independently derived from raw executed instruction bytes, not taken from implementation reports.

## A2 — Runtime arithmetic ↔ IR arithmetic 1:1: PASS

The independent byte decoder found exactly 36 scalar binary64 arithmetic occurrences in `attempt-05`. Exact array comparison against the delivered IR found:

- missing: 0
- duplicate: 0
- extra: 0
- reorder: 0
- opcode mismatch: 0
- trace-sequence mismatch: 0
- module-SHA mismatch: 0
- ELF-address mismatch: 0
- instruction-byte mismatch: 0

The same result holds independently for `closure-fresh-01`.

## A3 — Arithmetic semantics: PASS

For every arithmetic occurrence, input0 was reconstructed from the destination register's pre-state, input1 from the source operand, and output from the destination post-state. The check used the machine-byte ModRM fields and AT&T source/destination convention independently of the project's Numeric IR code.

All 36 operations passed exact-rational binary64 RN-even recomputation. No IR output bit pattern was used as the arithmetic oracle.

## A4 — Value identity: PASS

The independently reconstructed graph contains 254 distinct value IDs. There are 30 groups in which multiple dynamic values have equal raw bits; the largest equal-bit group contains 74 distinct value occurrences. These occurrences remain distinct by producer/storage/dynamic occurrence identity.

New equal-bit attacks that merged, swapped, or globally permuted same-bit identities were rejected after normalized hashes and graph references were repaired.

## A5 — Provenance graph: PASS

The complete independently reconstructed value array matched the delivered value array exactly, including producer objects, storage objects, byte lanes, and source slices.

Observed source-slice relations include:

- buffer → buffer: 12
- buffer → register: 16
- register → buffer: 16
- register → register: 80
- register → stack: 8
- stack → register: 6
- instruction → stack: 2

The graph also independently accounts for GPR/XMM state, ELF constants, explicit zero creation, zero extension/upper-zeroing, and arithmetic-result producers. Arithmetic inputs are therefore justified by dynamic byte provenance, not merely by equal final bits.

## A6 — Init → step boundary: PASS

The contract explicitly states that step `q`, `full_v`, and `latent` `COPY_BITS` nodes are captured phase-boundary state links, not observed caller copy instructions. It explicitly disclaims proof of the out-of-capture caller execution and disclaims proof that no same-bit writes occurred there.

The artifact implements this distinction mechanically:

- `v:boundary:step:q`: `COPY_BITS`, producer role `boundary`, producer `trace_sequence=null`, slice `trace_sequence=null`, `source_operand_index=null`
- `v:boundary:step:full_v`: same boundary form
- `v:boundary:step:latent`: two slices from the actual captured init endpoint producers, each with null trace sequence/operand index
- step `gradient`, `xmm0`, `xmm1`: new `LOAD_BITS` boundary roots

No fabricated caller instruction or fabricated trace sequence is present.

Independent judgment: this abstraction is appropriate for the current 1-step contract **only as an observed state handoff/equality relation**. A downstream V2 consumer may use it to justify that the captured step starts with those linked bytes, but may not infer an actual caller copy instruction, absence of intervening same-bit writes, caller arithmetic, timing/rounding behavior, or whole-caller provenance.

## A7 — Checker independence / shared-helper risk: PASS for this audit scope

The shipped `checker.py` does not import or call the translator and independently implements the value/provenance reconstruction. It does share `runtime_trace.semantics.decode` and the already-audited raw/ELF correspondence helpers with the translator. The shared decoder is a potential common-mode layer for opcode/form classification, so the shipped checker was **not** treated as independent evidence for that layer.

This audit closed that risk for the present frozen trace by decoding the relevant SSE instruction bytes and ModRM fields independently, without importing the shared helper, and by rebuilding the full operation/value/provenance arrays outside the repository implementation. All 36 arithmetic forms and all 254 value nodes matched.

This PASS does not imply that the shipped checker is implementation-independent for future/unseen instruction forms.

## A8 — Old / fresh normalized IR: PASS

`attempt-05` and `closure-fresh-01` were reconstructed separately before comparison. Their complete normalized `{schema, operations, values}` documents are exactly equal.

Therefore equality covers, among other included fields:

- module SHA
- ELF address
- arithmetic order and opcode
- operand/result raw bits
- producer identity
- storage relation
- byte-slice provenance

The fresh acquisition is not merely a byte-for-byte duplicate of process state: all 446 PID fields differ and 142 memory-operand addresses differ. These process-specific addresses are correctly excluded from normalized semantic equality.

Independent normalized SHA-256: `1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2`, matching the supplied value only after independent computation.

## A9 — Fail-closed behavior: PASS

Independently generated mutations did not produce PASS.

Raw-source/translator mutations were rejected as `REFUSED`, including:

- unsupported opcode
- missing trace record
- duplicate trace record
- reordered record
- arithmetic width mismatch
- operand-bit mutation
- output-bit mutation
- module/ELF-address mutation
- an actual packaged ELF byte flip (frozen manifest unchanged), rejected on packaged-module raw hash

IR/checker mutations were rejected as `FAIL`, including:

- missing producer
- ambiguous producer
- dangling provenance edge
- provenance cycle
- duplicated value identity
- invalid boundary root
- malformed type
- IR module-SHA mutation
- IR output-bit mutation

Thus raw source outside the supported conversion contract is refused, while malformed/inconsistent submitted IR is invalidated/failed rather than converted into a PASS.

## A10 — Independent mutation retest: PASS

Five new coordinated attacks were added outside the repository tests. All recomputed the normalized hash after mutation where applicable; none passed:

1. **Equal-bit read full-merge/delete**: redirected references to one same-bit dynamic read and deleted the other node. Result: `FAIL`.
2. **Equal-bit arithmetic-producer swap**: swapped producer objects between two same-zero arithmetic results with compatible local-looking kinds. Result: `FAIL`.
3. **Boundary COPY disguised as arithmetic**: changed a step boundary link into an arithmetic-style producer and repaired the candidate hash. Result: `FAIL`.
4. **Compensated source/destination slice shift**: shifted both ends of an all-zero byte slice together so local bytes still agreed, then repaired the hash. Result: `FAIL`.
5. **Global equal-bit value-ID permutation**: permuted two equal-bit value IDs throughout the graph so connectivity remained isomorphic, then repaired the hash. Result: `FAIL`.

These are in addition to the A9 malformed-source/graph tests and were not accepted on the basis of the package's pre-existing mutation report.

## A11 — Test reproduction: PASS

The snapshot was copied to a separate temporary location before running tests.

To avoid unrelated globally installed pytest plugins from dominating this sandbox's runtime, the repository tests were run with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; test targets and pytest arguments were otherwise the requested ones.

Results:

```text
python -m pytest runtime_trace/numeric_ir/tests -q
94 passed in 48.78s
```

```text
python -m pytest tests runtime_trace/tests runtime_trace/numeric_ir/tests -q
410 passed in 78.54s (0:01:18)
```

Both exited with status 0. No failure, skip, or xfail was counted as a pass.

## A12 — Git / package provenance: PASS

The bundle was verified in a separate empty repository.

- bundle branch head: `d679c8ba32d98e6076708b2b70b93c4eb37f5a49`
- checked-out HEAD: same
- start commit exists: `736b55198947bd3c8cecc024a12af156459cfa02`
- start is an ancestor of HEAD: yes
- `git fsck --full`: clean
- tracked files at HEAD: 761
- snapshot files: 761
- missing/extra snapshot files: 0/0
- tracked-byte mismatches between snapshot and HEAD: 0

The supplied protected-file list contains 141 files. Independently comparing those paths at the start commit and target HEAD found all 141 present in both and 0 byte changes. Git diff also shows no change under existing `runtime_trace` outside the new `runtime_trace/numeric_ir/**` subtree.

All 821 package-manifest entries passed presence/size/SHA-256 verification.

## Defect classification

Critical: 0

Major: 0

Minor: 0

UNRESOLVED: 0

## Final verdict

### PASS

Meaning of PASS is strictly limited to:

```text
frozen gala 1.12.0
regular orbit
init + 1-step

audited Runtime Trace
       ↕
Numeric IR
```

Within that scope, the audit independently supports 1:1 arithmetic occurrence correspondence, arithmetic bit semantics, dynamic value identity, byte-level provenance, the explicitly limited init→step state-boundary abstraction, old/fresh normalized equality, fail-closed mutation behavior, test reproduction, and package/Git provenance.

No conclusion is made about Numeric IR → V2, V2 bounds, 10/100-step behavior, chaotic or long trajectories, general x86 tracing, or physical correctness.
