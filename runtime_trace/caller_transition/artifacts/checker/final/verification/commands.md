# Task 2 final commands

All Python commands used the frozen interpreter
`/home/otherside123/venvs/gate2c1-trace/bin/python` in WSL distribution
`Ubuntu-24.04`, from `/mnt/d/numerical-audit-lab-recovered-2026-10-01`.

```sh
/home/otherside123/venvs/gate2c1-trace/bin/python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/audited-attempt-05 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round1/audited-attempt-05/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/final/audited-attempt-05 \
  --root .

/home/otherside123/venvs/gate2c1-trace/bin/python -m runtime_trace.caller_transition.checker \
  --capture-dir runtime_trace/caller_transition/artifacts/fresh-closure-fresh-01 \
  --transition runtime_trace/caller_transition/artifacts/producer-fix-round1/fresh-closure-fresh-01/transition.json \
  --out runtime_trace/caller_transition/artifacts/checker/final/fresh-closure-fresh-01 \
  --root .

PYTHONPATH=. /home/otherside123/venvs/gate2c1-trace/bin/python \
  /mnt/d/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-mutation-generator-20261003-01/generate.py

/home/otherside123/venvs/gate2c1-trace/bin/python -m pytest \
  runtime_trace/caller_transition/tests/test_caller_checker.py \
  runtime_trace/caller_transition/tests/test_caller_mutations.py \
  -q --junitxml=/mnt/d/numerical-audit-lab-caller-continuity-delivery-2026-10-03/task2-final-dedicated-20261003-02/pytest.xml

/home/otherside123/venvs/gate2c1-trace/bin/python -m py_compile \
  runtime_trace/caller_transition/checker.py \
  runtime_trace/caller_transition/tests/test_caller_checker.py \
  runtime_trace/caller_transition/tests/test_caller_mutations.py
```

The two checker commands, mutation generator, dedicated tests, and `py_compile`
all exited 0. The two checker stderr streams and the mutation-generator stderr
stream were empty. The dedicated pytest stream is saved as
`dedicated-pytest.log`; its JUnit form is `dedicated-pytest.xml`.
