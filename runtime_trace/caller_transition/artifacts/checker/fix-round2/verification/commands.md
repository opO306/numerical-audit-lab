# Task 2 fix round 2 verification commands

All Python commands use the frozen interpreter
`/home/otherside123/venvs/gate2c1-trace/bin/python` from repository root
`/mnt/d/numerical-audit-lab-recovered-2026-10-01`.

```sh
PYTHONPATH=. python -m runtime_trace.caller_transition.generate_checker_fix2_mutations \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round2/mutations

PYTHONPATH=. python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/audited-attempt-05-readproof-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round2/audited-attempt-05-readproof-01/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round2/audited-attempt-05-readproof-01 \
  --root /mnt/d/numerical-audit-lab-recovered-2026-10-01

PYTHONPATH=. python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/fresh-closure-fresh-01-readproof-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round2/fresh-closure-fresh-01-readproof-01/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round2/fresh-closure-fresh-01-readproof-01 \
  --root /mnt/d/numerical-audit-lab-recovered-2026-10-01

PYTHONPATH=. python -m py_compile \
  runtime_trace/caller_transition/checker.py \
  runtime_trace/caller_transition/generate_checker_fix2_mutations.py \
  runtime_trace/caller_transition/tests/test_caller_checker.py \
  runtime_trace/caller_transition/tests/test_caller_mutations.py \
  runtime_trace/caller_transition/tests/test_caller_fix1_mutations.py \
  runtime_trace/caller_transition/tests/test_caller_fix2_mutations.py

PYTHONPATH=. python -m pytest runtime_trace/caller_transition/tests -q \
  --junitxml=runtime_trace/caller_transition/artifacts/checker/fix-round2/verification/dedicated-pytest.xml
```

The two normal runs use only the public literal-pin CLI. The mutation generator
uses private in-memory test pins for repaired semantic attacks and has no CLI
or public checker trust override.
