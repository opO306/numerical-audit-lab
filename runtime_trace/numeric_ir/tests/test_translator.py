from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from runtime_trace.numeric_ir.schema import canonical_json, normalized_document
from runtime_trace.numeric_ir.translator import (
    ConversionRefused,
    translate,
    translate_to_directory,
)


OPERATION_KEYS = {
    "ir_sequence",
    "trace_sequence",
    "module_sha256",
    "elf_address",
    "instruction_bytes",
    "opcode",
    "operation_kind",
    "input0_value_id",
    "input1_value_id",
    "output_value_id",
    "input0_raw_bits",
    "input1_raw_bits",
    "output_raw_bits",
    "mxcsr",
    "phase",
    "step",
}

VALUE_KEYS = {
    "value_id",
    "producer_kind",
    "raw_bits",
    "width",
    "producer",
    "storage",
    "source_slices",
}


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
    (source / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")


def _value_by_producer(ir: dict, sequence: int, role: str) -> dict:
    return next(
        value
        for value in ir["values"]
        if value["producer"].get("trace_sequence") == sequence
        and value["producer"].get("role") == role
    )


def test_translates_each_scalar_occurrence_and_preserves_destination_source_order(
    attempt05, repo_root
):
    ir = translate(attempt05, root=repo_root)

    assert ir["schema"] == "runtime-trace-numeric-ir-regular-1step-v1"
    assert set(ir) >= {"schema", "source", "operations", "values"}
    assert len(ir["operations"]) == 36
    assert [op["ir_sequence"] for op in ir["operations"]] == list(range(36))
    assert all(set(op) == OPERATION_KEYS for op in ir["operations"])

    operation = next(op for op in ir["operations"] if op["trace_sequence"] == 139)
    assert operation["operation_kind"] == "MUL_BINARY64"
    assert operation["input0_raw_bits"] == "0x3f90000000000000"
    assert operation["input1_raw_bits"] == "0x3fe0000000000000"
    assert operation["output_raw_bits"] == "0x3f80000000000000"
    assert operation["mxcsr"] == 8096


def test_equal_bits_from_distinct_occurrences_keep_distinct_value_identities(
    attempt05, repo_root
):
    ir = translate(attempt05, root=repo_root)
    by_trace = {operation["trace_sequence"]: operation for operation in ir["operations"]}

    assert by_trace[104]["output_raw_bits"] == by_trace[105]["output_raw_bits"]
    assert by_trace[104]["output_value_id"] != by_trace[105]["output_value_id"]
    assert by_trace[107]["input0_raw_bits"] == by_trace[107]["input1_raw_bits"]
    assert by_trace[107]["input0_value_id"] != by_trace[107]["input1_value_id"]


def test_values_have_byte_slice_provenance_and_partial_zero_generation(
    attempt05, repo_root
):
    ir = translate(attempt05, root=repo_root)
    assert all(set(value) == VALUE_KEYS for value in ir["values"])
    assert len({value["value_id"] for value in ir["values"]}) == len(ir["values"])

    copied = _value_by_producer(ir, 348, "copy_result")
    assert copied["producer_kind"] == "COPY_BITS"
    assert copied["width"] == 16
    assert sum(part["width"] for part in copied["source_slices"]) == 16

    zero_upper = _value_by_producer(ir, 298, "zero_upper")
    assert zero_upper["producer_kind"] == "ZERO_BITS"
    assert zero_upper["storage"]["space"] == "register"
    assert zero_upper["storage"]["byte_offset"] == 4
    assert zero_upper["width"] == 12


def test_phase_transition_preserves_state_edges_but_scratch_is_new_boundary(
    attempt05, repo_root
):
    ir = translate(attempt05, root=repo_root)
    boundaries = {
        (value["producer"].get("phase"), value["producer"].get("boundary")): value
        for value in ir["values"]
        if value["producer"].get("role") == "boundary"
    }
    for name in ("q", "full_v", "latent"):
        value = boundaries["step", name]
        assert value["producer_kind"] == "COPY_BITS"
        assert value["source_slices"]
        assert all(part["value_id"] != value["value_id"] for part in value["source_slices"])

    gradient = boundaries["step", "gradient"]
    assert gradient["producer_kind"] == "LOAD_BITS"
    assert gradient["source_slices"] == []
    assert boundaries["step", "xmm0"]["producer_kind"] == "LOAD_BITS"
    assert boundaries["step", "xmm1"]["producer_kind"] == "LOAD_BITS"


def test_old_and_fresh_have_identical_address_independent_numeric_form(
    attempt05, fresh, repo_root
):
    old = translate(attempt05, root=repo_root)
    new = translate(fresh, root=repo_root)

    assert normalized_document(old) == normalized_document(new)
    assert old["source"]["trace_sha256"] != new["source"]["trace_sha256"]
    assert old["source"]["normalized_numeric_sha256"] == new["source"][
        "normalized_numeric_sha256"
    ]


def test_trace_raw_hash_mismatch_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    stream = bytearray((source / "trace.jsonl").read_bytes())
    stream[-2] ^= 1
    (source / "trace.jsonl").write_bytes(stream)

    with pytest.raises(ConversionRefused, match="trace raw hash"):
        translate(source, root=repo_root)


def test_sequence_gap_is_refused_even_after_hashes_are_recomputed(
    tmp_path, attempt05, repo_root
):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[10]["seq"] = 11
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="sequence"):
        translate(source, root=repo_root)


def test_arithmetic_width_mismatch_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[104]["operands"][0]["width"] = 4
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="width"):
        translate(source, root=repo_root)


def test_unknown_numeric_provenance_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[104]["operands"][0]["origins"] = [None] * 8
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="origin|provenance"):
        translate(source, root=repo_root)


def test_nonfinite_scalar_input_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[104]["operands"][0]["raw_bits"] = "0x7ff0000000000000"
    rows[104]["pre"]["xmm"]["xmm0"] = "0x00000000000000007ff0000000000000"
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="nonfinite"):
        translate(source, root=repo_root)


def test_unsupported_mxcsr_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[0]["pre"]["mxcsr"] |= 3 << 13
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="MXCSR"):
        translate(source, root=repo_root)


def test_unknown_fp_opcode_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[104]["instruction"] = "divsd %xmm0,%xmm2"
    rows[104]["opcode"] = "divsd"
    rows[104]["kind"] = "DIV"
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="unsupported"):
        translate(source, root=repo_root)


def test_module_instruction_byte_mismatch_is_refused(
    tmp_path, attempt05, repo_root
):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[0]["bytes"] = "00" + rows[0]["bytes"][2:]
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="instruction bytes"):
        translate(source, root=repo_root)


def test_memory_alias_disagreement_is_refused(tmp_path, attempt05, repo_root):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[139]["operands"][0]["address"] += 8
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="effective address|alias"):
        translate(source, root=repo_root)


def test_scalar_result_mismatch_is_refused_after_hashes_are_recomputed(
    tmp_path, attempt05, repo_root
):
    source = _clone_source(tmp_path, attempt05)
    rows = _rows(source)
    rows[139]["result_bits"] = "0x3f80000000000001"
    rows[139]["post"]["xmm"]["xmm1"] = "0x00000000000000003f80000000000001"
    _resign(source, rows)

    with pytest.raises(ConversionRefused, match="scalar result|rounding|linkage"):
        translate(source, root=repo_root)


def test_translation_does_not_require_mapping_file(
    attempt05, root_without_mapping
):
    assert not (root_without_mapping / "audit/gate2c1/machine_mapping.json").exists()
    ir = translate(attempt05, root=root_without_mapping)
    assert len(ir["operations"]) == 36


def test_translation_succeeds_when_mapping_file_access_is_denied(
    attempt05, root_without_mapping
):
    mapping = root_without_mapping / "audit/gate2c1/machine_mapping.json"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text("access to this file is forbidden")
    mapping.chmod(0)
    try:
        ir = translate(attempt05, root=root_without_mapping)
        assert len(ir["operations"]) == 36
    finally:
        mapping.chmod(0o600)


def test_missing_packaged_module_is_refused(attempt05, root_without_mapping):
    manifest = json.loads(
        (root_without_mapping / "runtime_trace/frozen_binaries/manifest.json").read_text()
    )
    gala_hash = "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc"
    (root_without_mapping / manifest["modules"][gala_hash]).unlink()

    with pytest.raises(ConversionRefused, match="packaged module missing"):
        translate(attempt05, root=root_without_mapping)


def test_directory_api_is_exclusive_and_never_leaves_partial_ir(
    tmp_path, attempt05, repo_root
):
    out = tmp_path / "numeric-ir"
    ir = translate_to_directory(attempt05, out, root=repo_root)
    assert json.loads((out / "numeric_ir.json").read_text()) == ir
    report = json.loads((out / "conversion_report.json").read_text())
    assert report["verdict"] == "CONVERTED"
    assert report["operation_count"] == 36
    assert report["value_count"] == len(ir["values"])
    with pytest.raises(FileExistsError):
        translate_to_directory(attempt05, out, root=repo_root)

    refused_source = _clone_source(tmp_path / "refused", attempt05)
    refused_rows = _rows(refused_source)
    refused_rows[5]["seq"] = 99
    _resign(refused_source, refused_rows)
    refused_out = tmp_path / "refused-output"
    with pytest.raises(ConversionRefused):
        translate_to_directory(refused_source, refused_out, root=repo_root)
    assert not refused_out.exists()


def test_canonical_json_is_stable_and_has_no_diagnostic_source_fields(
    attempt05, repo_root
):
    ir = translate(attempt05, root=repo_root)
    normalized = normalized_document(ir)
    encoded = canonical_json(normalized)

    assert encoded == canonical_json(json.loads(encoded))
    assert b"runtime_pc" not in encoded
    assert b"module_load_base" not in encoded
    assert b"module_path" not in encoded


def test_module_cli_creates_output_without_runtime_warning(
    tmp_path, attempt05, repo_root
):
    out = tmp_path / "cli-output"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime_trace.numeric_ir.translator",
            "--source",
            str(attempt05),
            "--out",
            str(out),
            "--root",
            str(repo_root),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["verdict"] == "CONVERTED"
    assert (out / "numeric_ir.json").is_file()
