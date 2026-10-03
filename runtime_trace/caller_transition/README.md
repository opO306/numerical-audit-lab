# Caller transition producer evidence

This directory contains Task 1 only: the actual frozen Gala native
first-return-to-second-entry acquisitions, fail-closed producer, source path,
and conditional continuity contract.  The independent checker is a separate
owner and is not implemented here.

Two fresh processes are preserved under `artifacts/`:

- `audited-attempt-05`: new caller corridor linked to the audited
  `attempt-05` endpoint antecedent;
- `fresh-closure-fresh-01`: a separate new process linked to the independently
  acquired `closure-fresh-01` endpoint antecedent.

Both stop under debugger control before the first second-step body
instruction.  `CONTROLLED_STOP` is not normal harness completion.

Run a new exclusive acquisition with the frozen WSL interpreter:

```bash
/home/otherside123/venvs/gate2c1-trace/bin/python \
  -m runtime_trace.caller_transition.run_acquisition \
  --out NEW_DIRECTORY --antecedent attempt-05
```

Produce the conditional binding from raw evidence:

```bash
/home/otherside123/venvs/gate2c1-trace/bin/python \
  -m runtime_trace.caller_transition.producer \
  --evidence EVIDENCE_DIRECTORY --antecedent attempt-05 \
  --out EVIDENCE_DIRECTORY/transition.json --root .
```

Task-1 tests are under `tests/`.  No status here claims checker PASS or
independent audit closure.
