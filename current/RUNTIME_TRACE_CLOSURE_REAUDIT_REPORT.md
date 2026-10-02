# Runtime Trace regular 1-step prototype — closure independent re-audit

## Scope

This re-audit is limited to closure of the prior blockers in the frozen gala 1.12.0 regular-orbit 1-step Runtime Trace prototype. It does not certify Numeric IR, V2, 10/100-step runs, general x86 tracing, or physical correctness.

Target closure commit: `736b55198947bd3c8cecc024a12af156459cfa02`  
Parent: `d408a07774bee44728d41d9a598b6d8142808075`

Prior verdict: `CONDITIONAL` — Critical 0 / Major 1 / Minor 1.

## Executive verdict

**Final: PASS**

- Critical: **0**
- Major: **0**
- Minor: **0**
- Substantive UNRESOLVED within closure scope: **0**
- Previous Major M1 (missing captured libc image): **CLOSED**
- Previous Minor m1 (absolute runtime-path dependency): **CLOSED**

Revised prior items:

- A1 Raw trace integrity: **PASS**
- A2 Actual executed instruction correspondence: **PASS**
- A3 Scalar FP completeness: **PASS**
- A15 Tests / reproduction: **PASS**

The live current working-tree state of the developer's machine is not proven by the bundle and is not claimed here. The bundle does independently prove the delivered snapshot's Git commit/history relationship.

---

## ZIP identity

Independently recomputed SHA-256 of `runtime-trace-closure-736b551.zip`:

`e11e872bc0cdd146d9c8869c245d1c3a98b6ae1415d9fc95006d0acbb485adab`

This matches the supplied value. The ZIP archive comment contains closure commit `736b55198947bd3c8cecc024a12af156459cfa02`.

---

## R1 — libc original image: PASS

Packaged file:

`runtime_trace/frozen_binaries/libc.so.6`

Independent SHA-256:

`3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`

This exactly matches the libc hash recorded in the old attempt-05 capture. No current-system libc was substituted for the binding check.

**Verdict: PASS. Previous Major M1's missing-image premise is closed.**

---

## R2 — attempt-05 libc record binding: PASS

The raw `attempt-05/trace.jsonl` was parsed without using producer counts as expected constants.

Independent raw counts:

- total records: **446**
- leapfrog module: **366**
- libc module: **22**
- cybuiltin module: **58**

For every libc occurrence, the independent checker verified:

1. `runtime_pc - module_load_base == elf_address`
2. ELF64/x86-64 PT_LOAD segment membership using a separate standard-library ELF parser
3. ELF virtual-address to file-offset translation
4. equality with the trace `elf_file_offset`
5. exact instruction bytes from the packaged libc
6. executable mapping/page relationship
7. independent GNU `objdump` decode and opcode correspondence

Result: **22/22 libc records bound successfully**.

The same independent procedure was then applied to all modules and all records:

**446/446 executable records bound successfully.**

No record failed ELF offset, byte, mapping, or decode checks.

**Verdict: PASS.**

---

## R3 — A1/A2/A3 closure: PASS

### A1 Raw trace integrity

Independent checks on attempt-05 included:

- raw trace SHA-256 against capture metadata
- independent record hash-chain recomputation
- exact continuous sequence numbering
- complete init/step region coverage
- PC pre/post linkage across every adjacent instruction
- register/XMM/MXCSR/eflags state linkage between adjacent records
- unique execution PID/TID throughout the traced region
- executable binding for all 446 records

Observed phase split was derived from the raw trace rather than injected as an expected constant:

- init: 191 records
- step: 255 records
- sole transition at sequence 191

### A2 Actual executed instruction correspondence

The prior unresolved byte-binding hole is now removed. All 446 records connect runtime PC, load bias, ELF address, file offset, packaged executable bytes, and an independent decode. The acquisition code itself was not changed by the closure commit; the relevant implementation change is in post-acquisition frozen-binary resolution.

### A3 Scalar FP completeness

Scalar FP arithmetic was derived from the independently decoded executed instruction stream:

- total scalar binary64 arithmetic occurrences: **36**
- `mulsd`: **16**
- `addsd`: **12**
- `subsd`: **8**

The independent decoder found no executed unsupported FP arithmetic in the traced regions: no DIV/SQRT/FMA/packed FP arithmetic occurrence was present in the 446-occurrence stream.

**A1: PASS  
A2: PASS  
A3: PASS**

---

## R4 — absolute-path dependency: PASS

The closure diff replaces direct reads of captured runtime module paths with a `FrozenBinaryResolver` keyed by module SHA-256 and restricted to package-relative manifest entries.

Independent dynamic tests were added outside the package's own tests:

1. **Captured old paths forcibly blocked**: access to `/home/otherside123/...` and the captured `/usr/lib/x86_64-linux-gnu/libc.so.6` was instrumented to raise. Full attempt-05 correspondence verification still returned PASS. Forbidden access attempts observed: **0**.
2. **All trace module paths replaced by nonexistent paths** while preserving hashes and rehashing trace integrity metadata: verification still returned PASS. This demonstrates that runtime path is provenance/key metadata, not the binary source.
3. **Packaged libc removed**: explicit refusal, `packaged module missing`.
4. **Packaged libc modified by one byte**: explicit refusal, `packaged module raw hash`.
5. **Unregistered module SHA plus an actually existing arbitrary ELF file**: explicit refusal, `unpackaged module SHA-256`; no fallback to that path occurred.

The resolver also rejects package-relative path escape.

**Verdict: PASS. Previous Minor m1 is CLOSED.**

---

## R5 — attempt-05 immutable evidence: PASS

The previous audit ZIP and closure ZIP were independently extracted and the complete `runtime_trace/artifacts/attempt-05` directory compared byte-for-byte.

- previous attempt-05 files: **11**
- closure attempt-05 files: **11**
- added/removed files inside attempt-05: **0**
- byte differences: **0**

The old raw trace remains:

`fec0379874f2a3ae792f041d553dd34533f90b02ad9bcf9d43cb022ef03e149c`

The Git bundle independently gives the same result: all 11 attempt-05 paths have identical blobs in parent `d408a07...` and closure HEAD `736b551...`.

**Verdict: PASS. The successful old artifact was not rewritten to obtain closure.**

---

## R6 — fresh acquisition: PASS, with environment note

This audit environment has Python **3.13.5** and does not provide `gdb` or `python3.12`, so a third live GDB acquisition could not be run here. The re-audit therefore used the fallback allowed by the closure request: independently inspect whether `closure-fresh-01` is a distinct, internally valid fresh-acquisition artifact rather than a copy of attempt-05.

Fresh artifact metadata and content show:

- GDB: **15.1**
- GDB Python: **3.12.3**
- frozen gala wheel SHA-256: `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`
- GDB return code: **0**
- capture verdict: `CAPTURED`
- pending uncompleted instruction: `null`
- machine mapping read by tracer: `false`
- source hashes recorded before execution match the delivered `run.py`, `harness.py`, `semantics.py`, and `gdb_capture.py` bytes exactly
- fresh trace independently passes the same 446/446 ELF/byte/decode binding

Evidence that this is not a literal reuse of the old trace:

- old trace SHA: `fec0379874f2a3ae792f041d553dd34533f90b02ad9bcf9d43cb022ef03e149c`
- fresh trace SHA: `e0bd088e844561ef6752b6498d734e32d94d20ae0abbfc7853b0fd85504cad86`
- old inferior PID/TID: 409
- fresh inferior PID/TID: 772
- heap/state pointer addresses differ consistently between trace, capture metadata, and GDB logs
- old and fresh GDB logs are not byte-identical and contain the corresponding independent process/pointer values
- the closure commit adds `closure-fresh-01` as new Git blobs rather than replacing attempt-05

The artifact does not contain an independently trusted absolute wall-clock acquisition timestamp; ZIP mtimes are packaging metadata and were not treated as acquisition evidence. That absence does not leave the old-copy question unresolved because the fresh process identity, pointer allocation differences, trace hash, GDB log, source hashes, and independent executable binding are mutually consistent.

**Verdict: PASS under the requested artifact-review fallback.**

---

## R7 — old vs fresh correspondence: PASS

The comparison was performed only after each trace independently passed raw integrity and executable binding.

Old and fresh are identical in:

- ELF-relative instruction occurrence sequence
- module SHA identity sequence
- instruction bytes
- independent decode/opcode sequence
- scalar FP operation sequence
- every scalar operand raw bit pattern
- every scalar result raw bit pattern
- final regular one-step output raw bits

They differ where a fresh process is expected to differ:

- trace raw bytes/hash
- PID/TID
- heap/state pointer addresses
- GDB log process-specific values

Both traces independently derive:

- 446 records total
- 36 scalar FP operations
- `mulsd 16 / addsd 12 / subsd 8`

Final output bits in both:

- x: `0x3f70000000000000`
- y: `0x3f60000000000000`
- vx: `0x3fcffeff00000000`
- vy: `0x3fbffefe80000000`

**Verdict: PASS.**

---

## R8 — A15 tests / reproduction: PASS

The delivered snapshot was copied to a different temporary path before testing.

Independent executions:

`python -m pytest runtime_trace/tests -q`

→ **66 passed**, 0 failed.

`python -m pytest -q`

→ **250 passed**, because repository `pytest.ini` contains `testpaths = tests` and therefore does not automatically recurse into `runtime_trace/tests`.

Explicit full combined suite:

`python -m pytest tests runtime_trace/tests -q`

→ **316 passed**, 0 failed, 0 skipped.

Thus the producer's final 316 figure is reproducible when both repository tests and the separate runtime-trace suite are explicitly selected. The prior portable-path failures do not recur.

**A15: PASS.**

---

## R9 — Git provenance: PASS for delivered snapshot/history

Bundle SHA-256 independently recomputed:

`743ddf1551acb5afdbf19360b6267520260d5e8cf41278a8fa486f402654ad05`

`git bundle verify` reports the bundle is valid and records complete history.

Independent clone/check:

- HEAD: `736b55198947bd3c8cecc024a12af156459cfa02`
- sole parent: `d408a07774bee44728d41d9a598b6d8142808075`
- `git fsck --full`: no errors
- Git HEAD tree file count: **736**
- delivered `snapshot/` file count: **736**
- path-set mismatch: **0**
- blob-byte mismatch: **0**

This proves the delivered snapshot corresponds byte-for-byte to closure commit `736b551...` and that the stated parent relationship exists in the bundle.

It does **not** independently prove the developer PC's current post-package working tree, nor the current live state of the GitHub remote. Those are correctly separate from snapshot provenance and are not needed for this closure decision.

**Verdict: PASS.**

---

## R10 — package manifest: PASS

`MANIFEST.json` advertises **740** members. All 740 were independently checked for existence, byte length, and SHA-256.

Results:

- advertised members: **740**
- missing: **0**
- SHA mismatch: **0**
- size mismatch: **0**
- actual archive-extracted files: **741**
- extra relative to advertised set: exactly **1**, `MANIFEST.json` itself
- `snapshot/` files: **736**

This is internally consistent: 736 snapshot files + bundle + delivery README + delivery provenance + verifier = 740 advertised payload files, with the manifest self-file as the 741st extracted file.

**Verdict: PASS.**

---

## Closure impact on previous PASS items

The closure commit changes post-acquisition binary resolution in `runtime_trace/correspondence.py`, adds the frozen libc/manifest, adds resolver tests, and adds fresh/closure evidence. The scalar arithmetic implementation and GDB acquisition code used by the fresh run are not changed by the resolver patch.

Because `correspondence.py` is part of the verifier, affected fail-closed assumptions were re-exercised through the independent resolver mutations above and the complete 66-test Runtime Trace suite. No regression requiring reopening A4–A14 was found.

---

## Final required form

```text
R1 libc original image: PASS
R2 libc 22-record binding: PASS
R3 A1/A2/A3 closure: PASS
R4 absolute-path dependency: PASS
R5 attempt-05 immutability: PASS
R6 fresh acquisition: PASS
R7 old/fresh correspondence: PASS
R8 A15 tests/reproduction: PASS
R9 Git provenance: PASS
R10 package integrity: PASS

A1: PASS
A2: PASS
A3: PASS
A15: PASS

Previous Major M1: CLOSED
Previous Minor m1: CLOSED

Critical: 0
Major: 0
Minor: 0
UNRESOLVED: 0 within the requested closure scope

Final: PASS
```

## Meaning of PASS

This PASS means only that, for the delivered frozen gala 1.12.0 regular-orbit one-step Runtime Trace prototype, the previously identified closure blockers have been independently closed and the machine-execution ↔ runtime-trace correspondence in that stated scope is supported by the delivered evidence.

It does not extend to Numeric IR, V2, 10/100-step trajectories, long trajectories, general x86 tracing, other wheels/OS/CPU environments, or Hénon-Heiles physical-model correctness.
