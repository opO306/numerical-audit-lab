# Caller Transition / Error-Continuity Gate

```text
IMPLEMENTED
CHECKER PASS
INDEPENDENT AUDIT PENDING
```

This Gate connects the actual first `c_leapfrog_step` return to the actual
second entry in frozen Gala 1.12.0. The regular `H.integrate_orbit` harness is
an exact sibling of the audited harness: only its executed `n_steps=1` token
changes to `n_steps=2`. It retains the production Cython caller, `save_all`
path, and helpers. Both accepted acquisitions stop before the first second-body
instruction. `CONTROLLED_STOP` means debugger termination, not normal harness
completion. Second-step arithmetic and its Numeric IR/V2 expansion are outside
this implementation.

Read [SOURCE_PATH.md](SOURCE_PATH.md), [CONTINUITY_CONTRACT.md](CONTINUITY_CONTRACT.md)
and [READPROOF.md](READPROOF.md) for source/ABI classification and the conditional
error contract. The existing n_steps=1 evidence supplies byte-pinned endpoint
antecedents; it contains no next-step caller continuation.

The accepted files are:

| Role | Audited endpoint case | Separate fresh case |
|---|---|---|
| Raw acquisition | `artifacts/audited-attempt-05-readproof-01/` | `artifacts/fresh-closure-fresh-01-readproof-01/` |
| Transition | `artifacts/producer-fix-round2/audited-attempt-05-readproof-01/transition.json` | `artifacts/producer-fix-round2/fresh-closure-fresh-01-readproof-01/transition.json` |
| Independent checker report | `artifacts/checker/fix-round2/audited-attempt-05-readproof-01/checker_report.json` | `artifacts/checker/fix-round2/fresh-closure-fresh-01-readproof-01/checker_report.json` |

These are different inferior processes (PID 394/start ticks 12881 and PID 449/start
ticks 13968) within the same boot/machine. No cross-system or ASLR-diversity
claim follows. Each capture has 728 instructions, 219 pre-memory observations,
111 possible writes including 21 same-value stores, 16 indirect control targets,
23 return targets, and zero executed second-body instructions. All rows record
FS/GS bases; the write-set includes actual FS-relative stores 369/374/457.

For the six q/full_v/latent lanes the checker requires identical addresses and
bits, exact endpoint COPY/dynamic identity and Form provenance, and no intervening
decoded write overlap. The caller gradient zeroing at 714/715 covers 16 bytes and
creates a fresh exact-zero scratch root. Time comes from the new schedule load
at 718 (`0x3fa0000000000000`); dt comes from the actual load at 723
(`0x3f90000000000000`). Entry temporary registers/XMM are fresh captured roots.
Native Gala does not execute Form objects. Carrying the unchanged error Form and
shared basis remains conditional on the existing external endpoint/Form audits.

`checker.py` imports only standard-library modules and invokes GNU objdump. Its
own ELF/parser/effect/interpreter checks module SHA, load base, ELF address, file
offset, bytes/decode, dense record chains, observations, memory shadow, writes,
defined flags, GPR/XMM post-state, actual control targets and final ABI def-use.
An independent origin track propagates authenticated context and exact-address
memory roots through Load/Store/Copy/Arithmetic/InstructionResult nodes, keeps
XMM lanes separate, and validates all nine final ABI origin chains. Legacy
memory-source MOVSD clears the upper 64 bits; register-source MOVSD preserves
them. Receipt preflight derives counts and sequence declarations before
instruction semantics, so stale and fully repaired sequence attacks are distinct.
Unknown forms and missing observations/segment bases are refused. The frozen
wheel, 3 module identities, exact 11-source set, execution/seal/process receipts and
audited IR/correspondence hashes are literal pins, not mutable evidence defaults.
The public API/CLI accepts only the two exact relative paths and frozen identities
above. The private in-memory test-pin hook is absent from the public signature
and CLI. GNU objdump's AT&T decode remains an external tool boundary; this is a
corridor-specific checker, not a general x86 emulator.

Run the public checker from this repository or the package's `snapshot/` root:

```bash
/home/otherside123/venvs/gate2c1-trace/bin/python \
  -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/audited-attempt-05-readproof-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round2/audited-attempt-05-readproof-01/transition.json \
  --out NEW_EXCLUSIVE_CHECKER_DIRECTORY --root .
```

For the separate case replace both case names with
`fresh-closure-fresh-01-readproof-01`. Original capture absolute module paths are
provenance metadata; decode uses packaged SHA-bound frozen binaries. The recorded
environment is WSL Python 3.12.3, GDB 15.1, Gala 1.12.0 and GNU objdump 2.42.

To collect a new candidate acquisition into an exclusive directory:

```bash
/home/otherside123/venvs/gate2c1-trace/bin/python \
  -m runtime_trace.caller_transition.run_acquisition_reads \
  --out NEW_EXCLUSIVE_ACQUISITION_DIRECTORY --antecedent attempt-05
```

A new candidate is not automatically trusted by the literal-pinned public checker.
It requires a separately reviewed immutable pin handoff. Original acquisition
sources and all v1 raw/producer/checker outputs remain preserved. The public
checker refuses v1 evidence as `SUPERSEDED_EVIDENCE`; old 21-test/18-mutation and
526-test results predate the repaired semantic checker and do not establish this
Gate's soundness.

The final dedicated suite records 101 passed in 68.67s, failures/errors/skips 0.
Both public normal cases return `CHECKER_PASS`. The 41 saved mutation cases in
`artifacts/checker/fix-round3/mutations/manifest.json` all return `REFUSED` with
the unchanged approved checker. All prior 35 cases and six fix-round2 regressions
have actual inputs: 27 full raw bundles with transitions, 12 transition-only
inputs and two structured unit fixtures. Every input, receipt and result has a
recorded SHA-256. The committed `generate_checker_fix3_mutations.py` reproduces
the complete 367-file mutation tree byte-for-byte into an exclusive directory.

Of these, 38 cases use explicit `TEST_ONLY_REPIN`, one uses
`PUBLIC_RIGID_PRODUCTION`, and two use distinct unit modes. Identity pins stay
fixed in private semantic tests; the public coherent-repin attack is refused
before semantics. Fully repaired deletion/reorder reach `TRACE_CONTROL_TARGET`
after receipt preflight; deliberately stale controls refuse at
`SEQUENCE_RECEIPT`. Final command, JUnit, source/result hashes and preservation
receipts are under `artifacts/checker/fix-round3/verification/`. The fix-round2
normal reports remain authoritative because this evidence-only fix did not
change the checker. Earlier 91/99-test results and receipt-only mutation evidence
remain historical; the final saved-input set supersedes their coverage claims.

The root implementation report and combined test logs are delivered separately
with the exact HEAD snapshot,manifest,Git bundle,recovery checks and preserved
failed/superseded runs. Internal implementation reviews are not external audit
closure. This Gate does not claim completed 2-step arithmetic, 10/100-step,
trajectory/global accumulated-error bounds or physical/observable accuracy.
Push was not performed.
