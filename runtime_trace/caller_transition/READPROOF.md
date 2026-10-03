# Caller transition v2 read-proof supplement

This supplement adds live pre-instruction memory-source evidence without
changing the v1 acquisitions, producer outputs, or independent checker.

Accepted raw acquisitions:

- `artifacts/audited-attempt-05-readproof-01/`
- `artifacts/fresh-closure-fresh-01-readproof-01/`

Accepted producer outputs for the next Task 2 repair:

- `artifacts/producer-fix-round2/audited-attempt-05-readproof-01/transition.json`
- `artifacts/producer-fix-round2/fresh-closure-fresh-01-readproof-01/transition.json`

Each raw directory contains one canonical execution receipt, chained v2 trace,
canonical capture, harness proof, exact source and module pinsets, GDB log,
disassembly, and a final acyclic acquisition seal.  The seal hashes the exact
eight-file raw set.  The capture hashes the execution and trace, while the
seal hashes the completed capture, so no hash cycle exists.

Every trace row retains the v1 register and possible-write evidence and adds
live raw pre-instruction bytes for every explicit memory source and every
implicit `ret`, `pop`, and `leave` source.  It also records FS and GS bases in
both pre and post state.  The final call row includes the live gradient stack
argument, and the second-entry ABI contains a separate live stack observation.

The v2 write helper also closes three FS-relative writes at sequences 369,
374, and 457 that v1 did not classify.  Therefore each accepted v2 trace has
111 possible writes and 21 same-value writes, rather than the historical v1
counts of 108 and 20.  This is a correction in new sibling evidence; no v1
byte or claim is rewritten.

Both captures stop under debugger control at the second
`c_leapfrog_step` entry before any second-step body instruction.  Their status
is `IMPLEMENTED / INDEPENDENT CHECKER PENDING`.  Task 2 must independently
decode instructions, derive reads and writes, and use root-transferred literal
seal/source/module/antecedent pins.  This supplement does not claim checker or
external-audit PASS.
