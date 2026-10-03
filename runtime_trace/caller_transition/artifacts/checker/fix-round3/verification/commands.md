# Task 2 fix round 3 verification commands

All Python execution used frozen interpreter
`/home/otherside123/venvs/gate2c1-trace/bin/python` from repository root
`/mnt/d/numerical-audit-lab-recovered-2026-10-01`.

```sh
PYTHONPATH=. python -m runtime_trace.caller_transition.generate_checker_fix3_mutations \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round3/mutations

PYTHONPATH=. python -m py_compile \
  runtime_trace/caller_transition/generate_checker_fix3_mutations.py \
  runtime_trace/caller_transition/tests/test_caller_fix3_evidence.py

PYTHONPATH=. python -m pytest -q \
  runtime_trace/caller_transition/tests/test_caller_fix3_evidence.py \
  --junitxml=runtime_trace/caller_transition/artifacts/checker/fix-round3/verification/focused-pytest.xml

PYTHONPATH=. python -m pytest runtime_trace/caller_transition/tests -q \
  --junitxml=runtime_trace/caller_transition/artifacts/checker/fix-round3/verification/dedicated-pytest.xml
```

The generator uses private, in-memory test pins only for saved semantic attack
fixtures. `public-coherent-repin` is executed through the public checker and is
refused at `TRUST_PATH`. No production pin can be supplied by the generator
CLI.

The two preservation checks independently read the root-owned baselines,
rehash every listed path, compare byte counts, and run `git hash-object` on
each path. They record all 177 and all 262 entries in
`protected-177-verification.json` and `protected-262-verification.json`.

The initial focused RED is preserved outside the repository at
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-fix3-red-01`.
The first successful complete generator probe is preserved at
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-fix3-probe-01`.
The final exit-zero, byte-identical 367-file replay is preserved at
`D:/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-fix3-final-replay-01`.
The first committed generator wrapper wrote PowerShell's boolean success token
instead of a numeric exit code; that exact token is retained as
`mutation-generator-exit-code-shell-bool.txt`, and the verified numeric exit
code is in `mutation-generator-exit-code.txt`. The first focused wrapper made
an empty exit-code file after its successful two-test run; the empty file is
retained as `focused-pytest-exit-code-empty.txt`, and the verified numeric exit
code is in `focused-pytest-exit-code.txt`.
