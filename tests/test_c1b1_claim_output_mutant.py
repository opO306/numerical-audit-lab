"""Execute a source copy with F-CLAIM-1 output protection actually removed."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import pytest

from test_c1b1_claim_output_boundary import false_zero_claim, assert_output_refusal
from test_c1b1_mutants import load_copy, SOURCE


def detector(module, path):
    payload = false_zero_claim()
    before = copy.deepcopy(payload)
    process_limit = sys.get_int_max_str_digits()
    try:
        module.compare_claim(payload, path, opt_in=(path == "exact_fast"))
    except Exception as exc:
        assert_output_refusal(exc)
    else:
        raise AssertionError("unrepresentable output was published")
    assert payload == before
    assert sys.get_int_max_str_digits() == process_limit


def test_fclaim1_actual_output_guard_removal_is_detected(tmp_path):
    names = ("_claim_output_baseline", "_claim_output_mutant")
    edits = [("if abs(value) >= _OUTPUT_INTEGER_LIMIT:", "if False:")]
    try:
        load_copy(tmp_path / "baseline", names[0])
        _, mutant_hash = load_copy(tmp_path / "mutant", names[1], "claim_adapter.py", edits)
        baseline_hash = hashlib.sha256((tmp_path / "baseline/claim_adapter.py").read_bytes()).hexdigest()
        assert baseline_hash == hashlib.sha256((SOURCE / "claim_adapter.py").read_bytes()).hexdigest()
        assert mutant_hash != baseline_hash
        baseline, mutant = [importlib.import_module(name + ".claim_adapter") for name in names]
        rows = []
        for path in ("exact_slow", "exact_fast"):
            detector(baseline, path)  # Failing baseline never counts as detection.
            with pytest.raises(AssertionError) as caught:
                detector(mutant, path)
            rows.append({"path": path, "baseline": "PASS", "actual_mutant_execution": "DETECTED",
                         "detection": str(caught.value)})
        report_path = os.environ.get("C1B1_CLAIM_OUTPUT_MUTANT_REPORT")
        if report_path:
            with Path(report_path).open("x", encoding="utf-8") as output:
                json.dump({"finding": "F-CLAIM-1", "source": "claim_adapter.py", "edits": edits,
                           "baseline_sha256": baseline_hash, "mutant_sha256": mutant_hash,
                           "baseline": "PASS", "actual_mutant_execution": "DETECTED",
                           "observations": rows, "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED",
                           "review": "AUTHOR CHECK ONLY / INDEPENDENT RE-AUDIT PENDING"}, output, indent=2)
                output.write("\n")
    finally:
        for key in list(sys.modules):
            if any(key == name or key.startswith(name + ".") for name in names):
                del sys.modules[key]
