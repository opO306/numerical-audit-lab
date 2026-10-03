# Task 2 fix round 1 verification commands

All Python commands used the frozen interpreter
`/home/otherside123/venvs/gate2c1-trace/bin/python` from repository root
`/mnt/d/numerical-audit-lab-recovered-2026-10-01`.

```sh
python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/audited-attempt-05-readproof-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round2/audited-attempt-05-readproof-01/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round1/audited-attempt-05-readproof-01 \
  --root /mnt/d/numerical-audit-lab-recovered-2026-10-01

python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/fresh-closure-fresh-01-readproof-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round2/fresh-closure-fresh-01-readproof-01/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/fix-round1/fresh-closure-fresh-01-readproof-01 \
  --root /mnt/d/numerical-audit-lab-recovered-2026-10-01

PYTHONPATH=. python /mnt/d/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-fix1-mutation-generator.py

python -m py_compile runtime_trace/caller_transition/checker.py
python -m pytest runtime_trace/caller_transition/tests -q \
  --junitxml=runtime_trace/caller_transition/artifacts/checker/fix-round1/verification/dedicated-pytest.xml
```

The first two commands used public rigid production trust. Mutation generation
used the private test-only in-memory acquisition-pin injection for semantic
attacks and separately exercised the public rigid path for coherent local
repinning. The private hook is absent from the CLI and public function
signature.
