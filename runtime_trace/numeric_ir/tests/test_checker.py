from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from runtime_trace.numeric_ir.checker import IRCheckError, check
from runtime_trace.numeric_ir.translator import translate


def _clone_source(tmp_path: Path, source: Path) -> Path:
    target = tmp_path / "source"
    target.mkdir(parents=True)
    shutil.copy2(source / "trace.jsonl", target / "trace.jsonl")
    shutil.copy2(source / "capture.json", target / "capture.json")
    return target


def _rows(source: Path) -> list[dict]:
    return [json.loads(line) for line in (source / "trace.jsonl").read_text().splitlines()]


def _resign(source: Path, rows: list[dict]) -> None:
    chain = "0" * 64
    encoded_lines = []
    for record in rows:
        unsigned = {key: value for key, value in record.items() if key != "chain"}
        encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        chain = hashlib.sha256(bytes.fromhex(chain) + encoded).hexdigest()
        record["chain"] = chain
        encoded_lines.append(json.dumps(record, separators=(",", ":")))
    stream = ("\n".join(encoded_lines) + "\n").encode()
    (source / "trace.jsonl").write_bytes(stream)
    capture = json.loads((source / "capture.json").read_text())
    capture["trace_sha256"] = hashlib.sha256(stream).hexdigest()
    capture["final_chain"] = chain
    capture["record_count"] = len(rows)
    capture["scalar_fp_count"] = sum(
        record.get("kind") in {"ADD", "SUB", "MUL"} for record in rows
    )
    capture["opcode_histogram"] = dict(Counter(record["opcode"] for record in rows))
    (source / "capture.json").write_text(json.dumps(capture))


def test_checker_accepts_independently_reconstructed_attempt05(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)

    report = check(candidate, attempt05, root=repo_root)

    assert report["verdict"] == "PASS"
    assert report["operation_count"] == 36
    assert report["value_count"] == 254
    assert report["source_trace_sha256"] == candidate["source"]["trace_sha256"]
    assert report["normalized_numeric_sha256"] == candidate["source"][
        "normalized_numeric_sha256"
    ]


def test_checker_cli_writes_new_pass_report(tmp_path, attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    ir_path = tmp_path / "candidate.json"
    ir_path.write_text(json.dumps(candidate))
    report_path = tmp_path / "checker-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.checker",
            "--ir",
            str(ir_path),
            "--source",
            str(attempt05),
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

    assert completed.returncode == 0, completed.stderr
    assert json.loads(report_path.read_text())["verdict"] == "PASS"


def test_checker_uses_content_identity_when_raw_source_is_relocated(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    relocated = tmp_path / "relocated-source"
    relocated.mkdir()
    shutil.copy2(attempt05 / "trace.jsonl", relocated / "trace.jsonl")
    shutil.copy2(attempt05 / "capture.json", relocated / "capture.json")

    report = check(candidate, relocated, root=repo_root)

    assert report["verdict"] == "PASS"


def test_missing_region_mxcsr_is_a_reasoned_refusal_not_metadata_keyerror(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(attempt05 / "trace.jsonl", source / "trace.jsonl")
    capture = json.loads((attempt05 / "capture.json").read_text())
    del capture["regions"][0]["mxcsr"]
    (source / "capture.json").write_text(json.dumps(capture))

    with pytest.raises(IRCheckError, match="region 0 MXCSR"):
        check(candidate, source, root=repo_root)


def test_checker_validates_without_mapping_or_tbin_files(
    attempt05, root_without_mapping
):
    candidate = translate(attempt05, root=root_without_mapping)

    report = check(candidate, attempt05, root=root_without_mapping)

    assert report["verdict"] == "PASS"


def test_production_checker_imports_without_translator_module(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    ir_path = tmp_path / "candidate.json"
    ir_path.write_text(json.dumps(candidate))
    script = """
import importlib.abc
import json
from pathlib import Path
import sys

class BlockTranslator(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "runtime_trace.numeric_ir.translator":
            raise RuntimeError("translator import forbidden")
        return None

sys.meta_path.insert(0, BlockTranslator())
from runtime_trace.numeric_ir.checker import check
report = check(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), Path(sys.argv[3]))
assert report["verdict"] == "PASS"
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(ir_path), str(attempt05), str(repo_root)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_malformed_capture_and_trace_shapes_are_reasoned_refusals(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    capture_source = _clone_source(tmp_path / "capture-case", attempt05)
    (capture_source / "capture.json").write_text("[]\n")
    with pytest.raises(IRCheckError, match="capture JSON object"):
        check(candidate, capture_source, root=repo_root)

    row_source = _clone_source(tmp_path / "row-case", attempt05)
    lines = (row_source / "trace.jsonl").read_bytes().splitlines()
    lines[0] = b"[]"
    stream = b"\n".join(lines) + b"\n"
    (row_source / "trace.jsonl").write_bytes(stream)
    capture = json.loads((row_source / "capture.json").read_text())
    capture["trace_sha256"] = hashlib.sha256(stream).hexdigest()
    (row_source / "capture.json").write_text(json.dumps(capture))
    with pytest.raises(IRCheckError, match="trace row 0 must be an object"):
        check(candidate, row_source, root=repo_root)


def test_missing_canonical_and_implicit_effective_address_gpr_is_refused(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    assert "(%rdx,%rax,4)" in rows[38]["instruction"]
    del rows[38]["pre"]["gpr"]["rax"]
    del rows[38]["post"]["gpr"]["rax"]
    _resign(source, rows)

    with pytest.raises(
        IRCheckError, match="trace row 38 pre missing captured canonical GPRs: rax"
    ):
        check(candidate, source, root=repo_root)


def test_missing_region_entry_xmm_boundary_is_refused(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    del rows[0]["pre"]["xmm"]["xmm0"]
    _resign(source, rows)

    with pytest.raises(IRCheckError, match="region init entry missing XMM boundary xmm0"):
        check(candidate, source, root=repo_root)


def test_rehashed_raw_kind_label_cannot_override_independent_decode(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    assert rows[104]["kind"] == "MUL"
    rows[104]["kind"] = "ADD"
    _resign(source, rows)
    resigned_capture = json.loads((source / "capture.json").read_text())
    candidate["source"]["trace_sha256"] = resigned_capture["trace_sha256"]
    candidate["source"]["final_chain"] = resigned_capture["final_chain"]

    with pytest.raises(IRCheckError, match="decoded kind"):
        check(candidate, source, root=repo_root)


@pytest.mark.parametrize(("field", "value"), [("start_seq", 447), ("end_seq", -1)])
def test_invalid_region_ranges_are_refused(
    tmp_path, attempt05, repo_root, field, value
):
    candidate = translate(attempt05, root=repo_root)
    source = _clone_source(tmp_path, attempt05)
    capture = json.loads((source / "capture.json").read_text())
    capture["regions"][0][field] = value
    (source / "capture.json").write_text(json.dumps(capture))

    with pytest.raises(IRCheckError, match="region 0 sequence range"):
        check(candidate, source, root=repo_root)


@pytest.mark.parametrize("offset", [0, 8])
def test_overlapping_boundary_storage_is_refused_before_seeding(
    tmp_path, attempt05, repo_root, offset
):
    candidate = translate(attempt05, root=repo_root)
    source = _clone_source(tmp_path, attempt05)
    capture = json.loads((source / "capture.json").read_text())
    for region in capture["regions"]:
        region["pointers"]["gradient"] = region["pointers"]["q"] + offset
    (source / "capture.json").write_text(json.dumps(capture))

    with pytest.raises(IRCheckError, match="ambiguous boundary memory alias"):
        check(candidate, source, root=repo_root)


def test_checker_cli_writes_fail_report_for_semantic_attack(
    tmp_path, attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    candidate["operations"][0]["operation_kind"] = "ADD_BINARY64"
    ir_path = tmp_path / "attacked.json"
    ir_path.write_text(json.dumps(candidate))
    report_path = tmp_path / "failure-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.checker",
            "--ir",
            str(ir_path),
            "--source",
            str(attempt05),
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

    assert completed.returncode == 2
    failure = json.loads(report_path.read_text())
    assert failure["verdict"] == "FAIL"
    assert "Traceback" not in completed.stderr
