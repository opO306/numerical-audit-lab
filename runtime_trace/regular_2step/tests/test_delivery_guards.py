import copy
import hashlib
import json

import pytest

from runtime_trace.regular_2step.delivery import (
    REVIEWED_TESTED_RECEIPT,
    SealRefused,
    validate_reviewed_tested_seal,
)


SOURCE_MAP_PATH = "runtime_trace/regular_2step/artifacts/validation/source_test_map.json"
REVIEW_DISPOSITIONS = {
    "task-3-review.md": "HISTORICAL_NEEDS_FIXES",
    "task-3-fix1-review.md": "APPROVED",
    "whole-branch-review.md": "APPROVED",
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _entry(path, raw):
    return {
        "path": path,
        "sha256": _sha(raw),
        "bytes": len(raw),
        "physical_lines": len(raw.splitlines()),
    }


def _fixture(tmp_path):
    head = "a" * 40
    sources = {
        "runtime_trace/regular_2step/delivery.py": b"def deliver():\n    return True\n",
        "runtime_trace/regular_2step/tests/test_delivery_guards.py": b"def test_guard():\n    pass\n",
        "runtime_trace/regular_2step/README.md": b"# tested docs\n",
    }
    source_map = {
        "schema": "regular-2step-final-source-test-map-v1",
        "production": [_entry("runtime_trace/regular_2step/delivery.py", sources[
            "runtime_trace/regular_2step/delivery.py"])],
        "tests": [_entry("runtime_trace/regular_2step/tests/test_delivery_guards.py", sources[
            "runtime_trace/regular_2step/tests/test_delivery_guards.py"])],
        "documentation": [_entry("runtime_trace/regular_2step/README.md", sources[
            "runtime_trace/regular_2step/README.md"])],
    }
    map_raw = (json.dumps(source_map, sort_keys=True) + "\n").encode()
    committed = {**sources, SOURCE_MAP_PATH: map_raw}
    workflow = tmp_path / "workflow"
    workflow.mkdir()
    reviews = {
        "task-3-review.md": b"Assessment: Needs fixes\n",
        "task-3-fix1-review.md": b"Assessment: APPROVED\n",
        "whole-branch-review.md": b"Assessment: APPROVED\n",
    }
    for name, raw in reviews.items():
        (workflow / name).write_bytes(raw)
    receipt = {
        "schema": "regular-2step-final-reviewed-tested-head-v1",
        "git_head": head,
        "source_test_map": {"path": SOURCE_MAP_PATH, "sha256": _sha(map_raw)},
        "reviews": [
            {"path": name, "sha256": _sha(reviews[name]), "disposition": disposition}
            for name, disposition in REVIEW_DISPOSITIONS.items()
        ],
        "review_gate": "APPROVED",
    }
    (workflow / REVIEWED_TESTED_RECEIPT).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return committed, workflow, head


def test_correct_frozen_binding_is_accepted(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    result = validate_reviewed_tested_seal(committed, workflow, head)
    assert result["verdict"] == "PASS"
    assert result["git_head"] == head
    assert result["tested_python_files"] == 2
    assert result["review_gate"] == "APPROVED"


def test_changed_source_hash_is_refused(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    committed["runtime_trace/regular_2step/delivery.py"] += b"# untested\n"
    with pytest.raises(SealRefused, match="source identity"):
        validate_reviewed_tested_seal(committed, workflow, head)


def test_changed_python_path_set_is_refused(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    committed["runtime_trace/regular_2step/new_source.py"] = b"UNTESTED = True\n"
    with pytest.raises(SealRefused, match="Python path set"):
        validate_reviewed_tested_seal(committed, workflow, head)


def test_mismatched_reviewed_head_is_refused(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    receipt = json.loads((workflow / REVIEWED_TESTED_RECEIPT).read_text())
    receipt["git_head"] = "b" * 40
    (workflow / REVIEWED_TESTED_RECEIPT).write_text(json.dumps(receipt) + "\n")
    with pytest.raises(SealRefused, match="HEAD"):
        validate_reviewed_tested_seal(committed, workflow, head)


def test_missing_approved_review_is_refused(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    (workflow / "task-3-fix1-review.md").unlink()
    with pytest.raises(SealRefused, match="review file"):
        validate_reviewed_tested_seal(committed, workflow, head)


def test_mismatched_review_hash_is_refused(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    (workflow / "whole-branch-review.md").write_text("Assessment: REJECTED\n")
    with pytest.raises(SealRefused, match="review identity"):
        validate_reviewed_tested_seal(committed, workflow, head)


def test_old_needs_fixes_review_cannot_substitute_for_approvals(tmp_path):
    committed, workflow, head = _fixture(tmp_path)
    receipt_path = workflow / REVIEWED_TESTED_RECEIPT
    receipt = json.loads(receipt_path.read_text())
    receipt["reviews"] = [receipt["reviews"][0]]
    receipt_path.write_text(json.dumps(receipt) + "\n")
    with pytest.raises(SealRefused, match="review inventory"):
        validate_reviewed_tested_seal(committed, workflow, head)
