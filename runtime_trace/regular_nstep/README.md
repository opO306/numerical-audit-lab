# Regular finite N-step integrated candidate

This extension runs the original pinned Gala 1.12.0 API and native wheel. The
existing harness text changes only the requested `n_steps` parameter and its
receipt metadata. GDB collects actual instructions from the same inferior and
thread. No handwritten replacement of Gala's equations supplies the trace.

One source path takes an integer N in 1..100. Fresh, connected native runs have
been validated for N=10 and N=100; the interface range is not an assertion that
every initial condition or future path passes. See
`current/RUNTIME_NSTEP_INTEGRATED_CANDIDATE_2026-10-05.md` for measured results,
costs, independent review and retained limitations.

## Acceptance contract

The supported case is the inherited regular Henon-Heiles orbit, one orbit and
two coordinates, represented dt=1/64, Linux x86-64, CPython 3.12, and the pinned
Gala wheel and frozen module images. The checker accepts only the defined finite
instruction/effect/helper set. IEEE-754 checks use exact arithmetic for the
observed scalar ADD/SUB/MUL operations; unsupported effects refuse.

The raw record must contain complete ordered init/body/caller/terminal regions,
dense global and local sequence numbers, module/decode correspondence, a single
process/thread birth identity, actual control seams, register/defined-flag and
memory effects, and normal exit. Dynamic occurrences retain distinct identities
even when their bits match. Every body is reconstructed, rather than copied from
a repeated template. A shared memory shadow validates the actual previous
body's output and the next body's input across each caller corridor. Same-value
writes remain observable. All four final output stores and their addresses,
stride and consecutive save indices must agree with actual state and harness
output bits.

Numeric IR is generated automatically from acquired rows. The unchanged frozen
V2 evaluates each operation. The independent checker imports neither the
producer nor that evaluator as its oracle: it reconstructs the graph from raw
rows, checks exact IEEE-754/def-use correspondence, and independently propagates
all coefficients and boxes. Six q/full_v/latent lanes carry their exact previous
dynamic state and Form within one acquisition and one K=4 computed-minus-true
basis. Only the observed gradient zero reset is permitted. Carried errors are
never reseeded or reset because their center bits happen to match.

Hash, decode, source identity, semantic, state/Form, completion, subprocess and
resource failures all refuse. A final resource receipt saying `EXECUTED` only
means the bounded subprocess exited successfully; it never certifies a run.
The public runner requires a separately generated fresh checker report with
`CHECKER_PASS`, exact integer `requested_steps == checked_steps == N`, and
`requested_complete: true` before publishing `run_result.json`. Failed runs
publish `run_refusal.json` with the available captured, native and V2 frontiers;
no valid prefix substitutes for requested completion. Source file set and
bytes must be identical at the beginning and end of each public run.

## Conditional boundaries

`init-return -> step1-entry` and the native terminal frontier -> Python wrapper
tail remain **UNTRACED**. Initial allocation/first save-column identity is an
inherited root premise; malloc is not traced. Collector/GDB/OS execution truth
is a trust premise, not proven by hashes. Represented t/dt inputs are checked;
schedule-generation error and exact-reference branch equivalence are excluded.
Native symbolic coefficients in the observed runs are zero; nonzero box carry
and separate nonzero-coefficient algebra tests do not supply a native nonzero
coefficient capture. ASLR diversity, physical trajectory accuracy, universal
program support, formal certification and external independent audit closure
are not established. Successful requested completion is conditional on these
unchanged boundaries.

## Reproduction

Use the existing Python 3.12 Linux environment with Gala, GDB, GNU objdump,
systemd user services and delegated cgroup v2 memory/cpu/pids controllers. Check
the remaining cumulative time and storage ledger before starting. Use a new
exclusive output directory; retain failed attempts. Run N=10 first, then N=100
with the same source set:

```sh
python -m runtime_trace.regular_nstep.run --steps 10 \
  --out runtime_trace/regular_nstep/artifacts/new10 \
  --ledger runtime_trace/regular_nstep/artifacts/budget.json
python -m runtime_trace.regular_nstep.run --steps 100 \
  --out runtime_trace/regular_nstep/artifacts/new100 \
  --ledger runtime_trace/regular_nstep/artifacts/budget.json
```

The delivered ledger already includes this development's numerical jobs. Do not
reset it to obtain extra execution allowance. Linux jobs enforce at most 600s,
4 GiB for the whole process tree and no swap, subject to the remaining 3600s
cumulative ceiling. Every actual acquisition/producer/log writer uses a locked
per-job allocation; raw trace is additionally limited to 512 MiB. New evidence
uses an 8 GiB aggregate ceiling with separately inventoried external relocation
proof and laptop copies. This is not an arbitrary filesystem-wide OS quota.

The separate Windows laptop script in
`current/runtime-nstep-audit-2026-10-05/laptop_independent.py` checks the saved
Linux acquisition with its own exact arithmetic and Form replay. It does not
execute Gala on Windows or duplicate the full Linux x86/ELF semantic checker.
Its environment, outputs, bounded Windows Job Object measurements and source
hash are recorded separately. Paid resources, commit, push and Verified Driver
implementation are outside this delivery.
