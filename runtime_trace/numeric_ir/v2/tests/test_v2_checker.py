from __future__ import annotations

import builtins
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _candidate(adapter_api, audited_ir_path, repo_root):
    _, adapt, _ = adapter_api
    return adapt(audited_ir_path, root=repo_root)


def test_checker_accepts_independently_reconstructed_candidate(
    adapter_api, audited_ir_path, repo_root
):
    candidate = _candidate(adapter_api, audited_ir_path, repo_root)

    from runtime_trace.numeric_ir.v2.checker import check

    report = check(candidate, audited_ir_path, root=repo_root)

    assert report["verdict"] == "PASS"
    assert report["operation_count"] == len(candidate["operations"])
    assert report["ir_to_v2_missing"] == 0
    assert report["ir_to_v2_duplicate"] == 0
    assert report["ir_to_v2_extra"] == 0
    assert report["ir_to_v2_reorder"] == 0


def test_checker_accepts_separately_audited_fresh_candidate(adapter_api, repo_root):
    _, adapt, _ = adapter_api
    fresh_ir = repo_root / "runtime_trace/numeric_ir/artifacts/closure-fresh-01/numeric_ir.json"
    candidate = adapt(fresh_ir, root=repo_root)
    from runtime_trace.numeric_ir.v2.checker import check

    report = check(candidate, fresh_ir, root=repo_root)

    assert report["verdict"] == "PASS"
    assert report["source_numeric_ir_sha256"] == (
        "c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296"
    )


def test_checker_does_not_import_adapter_core(
    adapter_api, audited_ir_path, repo_root, monkeypatch
):
    candidate = _candidate(adapter_api, audited_ir_path, repo_root)
    from runtime_trace.numeric_ir.v2.checker import check

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "runtime_trace.numeric_ir.v2.adapter":
            raise AssertionError("checker imported adapter core")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert check(candidate, audited_ir_path, root=repo_root)["verdict"] == "PASS"


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (("operations", 0, "v2_sequence"), True),
        (("operations", 0, "input0_raw_bits"), 0.0),
        (("state_bindings", 0, "width"), True),
        (("state_bindings", 0, "form", "coef", 0), 0.0),
        (("boundaries", 0, "trace_sequence"), False),
    ],
)
def test_checker_rejects_bool_float_and_non_string_type_confusion(
    adapter_api, audited_ir_path, repo_root, path, bad
):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    candidate = copy.deepcopy(_candidate(adapter_api, audited_ir_path, repo_root))
    target = candidate
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad

    with pytest.raises(V2CheckError):
        check(candidate, audited_ir_path, root=repo_root)


def test_checker_rejects_unpinned_ir_before_using_candidate(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    candidate = _candidate(adapter_api, audited_ir_path, repo_root)
    changed = json.loads(audited_ir_path.read_text(encoding="utf-8"))
    changed["source"]["record_count"] += 1
    changed_path = tmp_path / "changed-ir.json"
    changed_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(V2CheckError, match="audited"):
        check(candidate, changed_path, root=repo_root)


def test_checker_rejects_altered_requested_frozen_v2(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    candidate = _candidate(adapter_api, audited_ir_path, repo_root)
    altered_root = tmp_path / "altered-root"
    (altered_root / "lab").mkdir(parents=True)
    source = (repo_root / "lab/v2_bound.py").read_bytes()
    (altered_root / "lab/v2_bound.py").write_bytes(source + b"\n# altered\n")

    with pytest.raises(V2CheckError, match="frozen"):
        check(candidate, audited_ir_path, root=altered_root)


def test_checker_accepts_root_containing_only_exact_frozen_v2(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    from runtime_trace.numeric_ir.v2.checker import check

    candidate = _candidate(adapter_api, audited_ir_path, repo_root)
    minimal_root = tmp_path / "minimal-root"
    (minimal_root / "lab").mkdir(parents=True)
    (minimal_root / "lab/v2_bound.py").write_bytes((repo_root / "lab/v2_bound.py").read_bytes())

    assert check(candidate, audited_ir_path, root=minimal_root)["verdict"] == "PASS"


def test_cli_accepts_complete_adapter_publication(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    _, _, adapt_to_directory = adapter_api
    published = tmp_path / "published"
    adapt_to_directory(audited_ir_path, published, root=repo_root)
    report_path = tmp_path / "checker-report.json"
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(published / "correspondence.json"),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(report_path.read_text(encoding="utf-8"))["verdict"] == "PASS"


def test_cli_rejects_semantic_attack_even_with_repaired_completion_hash(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    _, _, adapt_to_directory = adapter_api
    published = tmp_path / "published"
    adapt_to_directory(audited_ir_path, published, root=repo_root)
    correspondence_path = published / "correspondence.json"
    correspondence = json.loads(correspondence_path.read_text(encoding="utf-8"))
    add = next(op for op in correspondence["operations"] if op["v2_operation_kind"] == "ADD")
    add["v2_operation_kind"] = "MUL"
    encoded = json.dumps(correspondence, sort_keys=True, separators=(",", ":")).encode()
    correspondence_path.write_bytes(encoded)
    completion_path = published / "completion_report.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["correspondence_sha256"] = hashlib.sha256(encoded).hexdigest()
    completion_path.write_text(
        json.dumps(completion, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    report_path = tmp_path / "checker-report.json"
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(correspondence_path),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["verdict"] == "FAIL"
    assert "v2_operation_kind" in result.stderr


def test_cli_reports_invalid_huge_form_even_with_repaired_completion_hash(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    _, _, adapt_to_directory = adapter_api
    published = tmp_path / "published"
    adapt_to_directory(audited_ir_path, published, root=repo_root)
    correspondence_path = published / "correspondence.json"
    correspondence = json.loads(correspondence_path.read_text(encoding="utf-8"))
    correspondence["state_bindings"][0]["form"]["box"] = "0x1p+999999"
    encoded = json.dumps(correspondence, sort_keys=True, separators=(",", ":")).encode()
    correspondence_path.write_bytes(encoded)
    completion_path = published / "completion_report.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["correspondence_sha256"] = hashlib.sha256(encoded).hexdigest()
    completion_path.write_text(
        json.dumps(completion, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    report_path = tmp_path / "checker-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(correspondence_path),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert "form" in report["reason"]


def test_cli_rejects_duplicate_json_keys_before_semantic_check(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    candidate = _candidate(adapter_api, audited_ir_path, repo_root)
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
    duplicate = encoded.replace(
        '"schema":"numeric-ir-frozen-v2-regular-1step-v1"',
        '"schema":"numeric-ir-frozen-v2-regular-1step-v1","schema":"numeric-ir-frozen-v2-regular-1step-v1"',
        1,
    )
    correspondence_path = tmp_path / "correspondence.json"
    correspondence_path.write_text(duplicate, encoding="utf-8")
    completion = {
        "schema": "numeric-ir-frozen-v2-adapter-report-v1",
        "verdict": "ADAPTED",
        "correspondence_sha256": hashlib.sha256(duplicate.encode()).hexdigest(),
        "source_numeric_ir_sha256": candidate["source"]["numeric_ir_sha256"],
        "source_normalized_numeric_sha256": candidate["source"]["normalized_numeric_sha256"],
        "operation_count": len(candidate["operations"]),
        "state_binding_count": len(candidate["state_bindings"]),
        "boundary_count": len(candidate["boundaries"]),
    }
    (tmp_path / "completion_report.json").write_text(
        json.dumps(completion, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(correspondence_path),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "duplicate JSON key" in result.stderr


def test_cli_reports_json_integer_digit_limit_as_explicit_fail(
    audited_ir_path, repo_root, tmp_path
):
    correspondence_path = tmp_path / "correspondence.json"
    correspondence_path.write_text('{"schema":' + ("1" * 5000) + "}", encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(correspondence_path),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert "malformed correspondence" in report["reason"]


def test_cli_will_not_overwrite_existing_report(
    adapter_api, audited_ir_path, repo_root, tmp_path
):
    _, _, adapt_to_directory = adapter_api
    published = tmp_path / "published"
    adapt_to_directory(audited_ir_path, published, root=repo_root)
    report_path = tmp_path / "checker-report.json"
    report_path.write_text("keep", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.v2.checker",
            "--correspondence",
            str(published / "correspondence.json"),
            "--ir",
            str(audited_ir_path),
            "--report",
            str(report_path),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert report_path.read_text(encoding="utf-8") == "keep"
