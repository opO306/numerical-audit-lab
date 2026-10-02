from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path

import pytest


SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
REPORT_SCHEMA = "numeric-ir-frozen-v2-adapter-report-v1"
KIND_MAP = {
    "ADD_BINARY64": "ADD",
    "SUB_BINARY64": "SUB",
    "MUL_BINARY64": "MUL",
}


def _write_json(path: Path, document: object) -> None:
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _state_by_id(output: dict) -> dict[str, dict]:
    return {state["state_id"]: state for state in output["state_bindings"]}


def test_audited_input_preserves_ir_and_executes_exact_order(
    adapter_api, audited_ir_path: Path, audited_ir: dict, repo_root: Path
) -> None:
    _, adapt, _ = adapter_api

    output = adapt(audited_ir_path, root=repo_root)

    assert output["schema"] == SCHEMA
    assert output["values"] == audited_ir["values"]
    assert len(output["operations"]) == len(audited_ir["operations"])
    assert [op["ir_sequence"] for op in output["operations"]] == [
        op["ir_sequence"] for op in audited_ir["operations"]
    ]
    assert [op["v2_sequence"] for op in output["operations"]] == list(
        range(len(audited_ir["operations"]))
    )
    assert [op["v2_operation_kind"] for op in output["operations"]] == [
        KIND_MAP[op["operation_kind"]] for op in audited_ir["operations"]
    ]
    assert Counter(op["v2_operation_kind"] for op in output["operations"]) == Counter(
        KIND_MAP[op["operation_kind"]] for op in audited_ir["operations"]
    )


def test_destination_source_identity_and_form_snapshots_are_occurrence_specific(
    adapter_api, audited_ir_path: Path, audited_ir: dict, repo_root: Path
) -> None:
    _, adapt, _ = adapter_api
    output = adapt(audited_ir_path, root=repo_root)
    states = _state_by_id(output)

    for actual, ir_op in zip(output["operations"], audited_ir["operations"], strict=True):
        assert actual["input0_value_id"] == ir_op["input0_value_id"]
        assert actual["input1_value_id"] == ir_op["input1_value_id"]
        assert actual["output_value_id"] == ir_op["output_value_id"]
        assert states[actual["input0_state_id"]]["value_id"] == ir_op["input0_value_id"]
        assert states[actual["input1_state_id"]]["value_id"] == ir_op["input1_value_id"]
        assert states[actual["output_state_id"]]["value_id"] == ir_op["output_value_id"]
        assert actual["input0_form"] == states[actual["input0_state_id"]]["form"]
        assert actual["input1_form"] == states[actual["input1_state_id"]]["form"]
        assert actual["output_form"] == states[actual["output_state_id"]]["form"]

    equal_bits = next(
        op for op in output["operations"]
        if op["input0_raw_bits"] == op["input1_raw_bits"]
        and op["input0_value_id"] != op["input1_value_id"]
    )
    assert equal_bits["input0_state_id"] != equal_bits["input1_state_id"]


def test_boundary_copy_is_state_handoff_with_null_trace_and_no_v2_operation(
    adapter_api, audited_ir_path: Path, repo_root: Path
) -> None:
    _, adapt, _ = adapter_api
    output = adapt(audited_ir_path, root=repo_root)
    states = _state_by_id(output)
    boundary = next(item for item in output["boundaries"] if item["value_id"] == "v:boundary:step:q")

    assert boundary["classification"] == "CAPTURED_STATE_HANDOFF"
    assert boundary["trace_sequence"] is None
    assert len(boundary["state_ids"]) == 2
    assert not any(op["output_value_id"] == boundary["value_id"] for op in output["operations"])
    for state_id in boundary["state_ids"]:
        state = states[state_id]
        assert state["binding_kind"] == "COPY"
        assert state["source_state_id"] is not None
        assert state["form"] == states[state["source_state_id"]]["form"]


def test_frozen_step_forms_is_called_once_per_ir_operation_with_exact_occurrences(
    adapter_api, audited_ir_path: Path, audited_ir: dict, repo_root: Path, monkeypatch
) -> None:
    _, adapt, _ = adapter_api
    from lab import v2_bound

    calls: list[tuple[list, dict, dict]] = []
    real_step_forms = v2_bound.step_forms

    def observing_step_forms(structure, regs, inputs):
        calls.append((copy.deepcopy(structure), dict(regs), dict(inputs)))
        return real_step_forms(structure, regs, inputs)

    monkeypatch.setattr(v2_bound, "step_forms", observing_step_forms)
    output = adapt(audited_ir_path, root=repo_root)

    assert len(calls) == len(audited_ir["operations"])
    for call, actual, ir_op in zip(calls, output["operations"], audited_ir["operations"], strict=True):
        structure, regs, inputs = call
        assert structure == [(
            KIND_MAP[ir_op["operation_kind"]],
            actual["output_state_id"],
            [actual["input0_state_id"], actual["input1_state_id"]],
            None,
        )]
        assert regs == {
            actual["input0_state_id"]: int(ir_op["input0_raw_bits"], 16),
            actual["input1_state_id"]: int(ir_op["input1_raw_bits"], 16),
            actual["output_state_id"]: int(ir_op["output_raw_bits"], 16),
        }
        assert set(inputs) == {actual["input0_state_id"], actual["input1_state_id"]}


def test_forms_are_serialized_as_finite_exact_float_hex(
    adapter_api, audited_ir_path: Path, repo_root: Path
) -> None:
    _, adapt, _ = adapter_api
    output = adapt(audited_ir_path, root=repo_root)

    for state in output["state_bindings"]:
        assert len(state["form"]["coef"]) == 4
        for encoded in [*state["form"]["coef"], state["form"]["box"]]:
            assert isinstance(encoded, str)
            decoded = float.fromhex(encoded)
            assert math.isfinite(decoded)
            assert decoded.hex() == encoded


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["operations"][0].__setitem__("ir_sequence", True),
        lambda d: d["operations"][0].__setitem__("trace_sequence", 104.0),
        lambda d: d["operations"][0].__setitem__("operation_kind", None),
        lambda d: d["values"][0].__setitem__("width", False),
        lambda d: d["values"][0].__setitem__("raw_bits", 0),
        lambda d: d["values"].append(copy.deepcopy(d["values"][0])),
        lambda d: d["operations"][0].__setitem__("input0_value_id", "v:missing"),
        lambda d: d["operations"].reverse(),
    ],
)
def test_malformed_type_duplicate_dangling_and_ordered_inputs_are_refused(
    adapter_api, audited_ir: dict, repo_root: Path, tmp_path: Path, mutate
) -> None:
    AdapterRefused, adapt, _ = adapter_api
    changed = copy.deepcopy(audited_ir)
    mutate(changed)
    path = tmp_path / "changed.json"
    _write_json(path, changed)

    with pytest.raises(AdapterRefused):
        adapt(path, root=repo_root)


def test_duplicate_json_object_key_is_refused_before_adaptation(
    adapter_api, audited_ir_path: Path, repo_root: Path, tmp_path: Path
) -> None:
    AdapterRefused, adapt, _ = adapter_api
    raw = audited_ir_path.read_text(encoding="utf-8")
    duplicate = raw.replace("{", '{"schema":"duplicate",', 1)
    assert duplicate != raw
    path = tmp_path / "duplicate-key.json"
    path.write_text(duplicate, encoding="utf-8")

    with pytest.raises(AdapterRefused, match="duplicate JSON key"):
        adapt(path, root=repo_root)


def test_changed_source_bytes_and_frozen_dependency_are_refused(
    adapter_api, audited_ir_path: Path, repo_root: Path, tmp_path: Path
) -> None:
    AdapterRefused, adapt, _ = adapter_api
    changed_ir = tmp_path / "changed-ir.json"
    changed_ir.write_bytes(audited_ir_path.read_bytes() + b"\n")
    with pytest.raises(AdapterRefused, match="audited Numeric IR byte identity"):
        adapt(changed_ir, root=repo_root)

    fake_root = tmp_path / "fake-root"
    (fake_root / "lab").mkdir(parents=True)
    frozen = (repo_root / "lab/v2_bound.py").read_bytes()
    (fake_root / "lab/v2_bound.py").write_bytes(frozen + b"\n# changed\n")
    with pytest.raises(AdapterRefused, match="frozen V2"):
        adapt(audited_ir_path, root=fake_root)


def test_publication_is_exclusive_complete_and_cleans_up_refusal(
    adapter_api, audited_ir_path: Path, repo_root: Path, tmp_path: Path
) -> None:
    AdapterRefused, _, adapt_to_directory = adapter_api
    out = tmp_path / "published"

    output = adapt_to_directory(audited_ir_path, out, root=repo_root)

    assert output == json.loads((out / "correspondence.json").read_text(encoding="utf-8"))
    report = json.loads((out / "completion_report.json").read_text(encoding="utf-8"))
    assert report == {
        "schema": REPORT_SCHEMA,
        "verdict": "ADAPTED",
        "correspondence_sha256": hashlib.sha256((out / "correspondence.json").read_bytes()).hexdigest(),
        "source_numeric_ir_sha256": output["source"]["numeric_ir_sha256"],
        "source_normalized_numeric_sha256": output["source"]["normalized_numeric_sha256"],
        "operation_count": len(output["operations"]),
        "state_binding_count": len(output["state_bindings"]),
        "boundary_count": len(output["boundaries"]),
    }
    sentinel = out / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        adapt_to_directory(audited_ir_path, out, root=repo_root)
    assert sentinel.read_text(encoding="utf-8") == "keep"

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    refused_out = tmp_path / "refused"
    with pytest.raises(AdapterRefused):
        adapt_to_directory(invalid, refused_out, root=repo_root)
    assert not refused_out.exists()


def test_publication_cleans_new_directory_after_completion_write_error(
    adapter_api, audited_ir_path: Path, repo_root: Path, tmp_path: Path, monkeypatch
) -> None:
    _, _, adapt_to_directory = adapter_api
    from runtime_trace.numeric_ir.v2 import adapter as adapter_module

    real_write = adapter_module.write_canonical

    def fail_completion(path, value):
        if path.name == "completion_report.json":
            raise OSError("injected completion write failure")
        return real_write(path, value)

    monkeypatch.setattr(adapter_module, "write_canonical", fail_completion)
    out = tmp_path / "partial-publication"
    with pytest.raises(OSError, match="injected completion write failure"):
        adapt_to_directory(audited_ir_path, out, root=repo_root)
    assert not out.exists()


@pytest.mark.parametrize("mode", ["missing", "nonfinite"])
def test_invalid_frozen_v2_output_is_refused(
    adapter_api, audited_ir_path: Path, repo_root: Path, monkeypatch, mode: str
) -> None:
    AdapterRefused, adapt, _ = adapter_api
    from lab import v2_bound

    def invalid_step_forms(structure, regs, inputs):
        output_state = structure[0][1]
        if mode == "missing":
            return dict(inputs)
        return {output_state: v2_bound.Form([0.0] * v2_bound.K, math.inf)}

    monkeypatch.setattr(v2_bound, "step_forms", invalid_step_forms)
    expected = "output linkage missing" if mode == "missing" else "invalid Form"
    with pytest.raises(AdapterRefused, match=expected):
        adapt(audited_ir_path, root=repo_root)
