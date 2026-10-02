"""Independent checker for Numeric IR to frozen V2 correspondence v1.

This module intentionally does not import the adapter.  It rebuilds the selected
scalar state graph and every frozen V2 call directly from the byte-pinned IR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import NoReturn


SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
IR_SCHEMA = "runtime-trace-numeric-ir-regular-1step-v1"
REPORT_SCHEMA = "numeric-ir-frozen-v2-check-report-v1"
COMPLETION_SCHEMA = "numeric-ir-frozen-v2-adapter-report-v1"
PINS_SCHEMA = "numeric-ir-frozen-v2-audited-input-pins-v1"
FROZEN_MODULE = "lab.v2_bound"
FROZEN_OPERATOR = "step_forms"
ARITHMETIC_MAP = {
    "ADD_BINARY64": "ADD",
    "SUB_BINARY64": "SUB",
    "MUL_BINARY64": "MUL",
}
VALUE_KINDS = {"LOAD_BITS", "CONST_BITS", "COPY_BITS", "ZERO_BITS", "ARITHMETIC_RESULT"}
STATE_KIND = {
    "LOAD_BITS": "LOAD",
    "CONST_BITS": "CONST",
    "COPY_BITS": "COPY",
    "ZERO_BITS": "ZERO",
    "ARITHMETIC_RESULT": "ARITHMETIC_RESULT",
}
HEX64 = re.compile(r"0x[0-9a-f]{16}\Z")
HEX256 = re.compile(r"[0-9a-f]{64}\Z")

IR_TOP_KEYS = {"schema", "source", "operations", "values"}
IR_SOURCE_KEYS = {
    "capture_schema",
    "trace_sha256",
    "final_chain",
    "record_count",
    "scalar_fp_count",
    "module_sha256s",
    "regions",
    "normalized_numeric_sha256",
    "diagnostic",
}
IR_OPERATION_KEYS = {
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
VALUE_KEYS = {"value_id", "producer_kind", "raw_bits", "width", "producer", "storage", "source_slices"}
STORAGE_KEYS = {"space", "name", "byte_offset", "width"}
SLICE_KEYS = {
    "value_id",
    "source_offset",
    "destination_offset",
    "width",
    "trace_sequence",
    "source_operand_index",
    "source_storage",
    "destination_storage",
}
OUTPUT_TOP_KEYS = {"schema", "source", "values", "boundaries", "state_bindings", "operations"}
OUTPUT_SOURCE_KEYS = {
    "audited_input_label",
    "numeric_ir_sha256",
    "normalized_numeric_sha256",
    "numeric_ir_schema",
    "numeric_ir_source",
    "frozen_v2",
}
FROZEN_KEYS = {
    "module",
    "operator",
    "k",
    "lf_sha256",
    "imported_lf_sha256",
    "requested_lf_sha256",
}
STATE_KEYS = {
    "state_id",
    "value_id",
    "byte_offset",
    "width",
    "raw_center_bits",
    "form",
    "binding_kind",
    "source_state_id",
    "producer_ir_sequence",
    "phase",
    "trace_sequence",
}
BOUNDARY_KEYS = {
    "value_id",
    "phase",
    "boundary",
    "producer_kind",
    "classification",
    "trace_sequence",
    "state_ids",
}
ADAPTER_OPERATION_KEYS = {
    "v2_sequence",
    "v2_operation_kind",
    "input0_state_id",
    "input1_state_id",
    "output_state_id",
    "input0_form",
    "input1_form",
    "output_form",
}


class V2CheckError(ValueError):
    """The supplied prerequisite or correspondence is not accepted."""


def _fail(message: str) -> NoReturn:
    raise V2CheckError(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json_bytes(raw: bytes, label: str) -> object:
    try:
        text = raw.decode("utf-8")
        return json.loads(text, object_pairs_hook=_pairs)
    except V2CheckError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        _fail(f"malformed {label}: {exc}")


def _dict(value: object, label: str, keys: set[str] | None = None) -> dict:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    if keys is not None and set(value) != keys:
        _fail(f"{label} keys mismatch")
    return value


def _list(value: object, label: str) -> list:
    if type(value) is not list:
        _fail(f"{label} must be an array")
    return value


def _str(value: object, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} must be a string")
    return value


def _int(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        _fail(f"{label} is below its minimum")
    return value


def _nullable_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _int(value, label)


def _nullable_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _str(value, label)


def _sha(value: object, label: str) -> str:
    result = _str(value, label)
    if HEX256.fullmatch(result) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return result


def _storage(value: object, label: str) -> dict:
    result = _dict(value, label, STORAGE_KEYS)
    _str(result["space"], f"{label}.space")
    _str(result["name"], f"{label}.name")
    _int(result["byte_offset"], f"{label}.byte_offset")
    _int(result["width"], f"{label}.width", minimum=1)
    return result


def _raw(value: object, width: int, label: str) -> str:
    text = _str(value, label)
    if re.fullmatch(rf"0x[0-9a-f]{{{2 * width}}}", text) is None:
        _fail(f"{label} has invalid raw width or spelling")
    return text


def _lane_bits(value: dict, offset: int) -> str:
    width = value["width"]
    if type(offset) is not int or offset < 0 or offset + 8 > width:
        _fail(f"invalid 8-byte lane {value['value_id']}:{offset}")
    bits = (int(value["raw_bits"], 16) >> (8 * offset)) & ((1 << 64) - 1)
    import struct

    if not math.isfinite(struct.unpack(">d", bits.to_bytes(8, "big"))[0]):
        _fail(f"nonfinite scalar lane {value['value_id']}:{offset}")
    return f"0x{bits:016x}"


def _form_document(form: object, k: int) -> dict:
    try:
        coefficients = list(form.coef)
        box = form.box
    except (AttributeError, TypeError) as exc:
        _fail(f"frozen V2 returned invalid Form: {exc}")
    if len(coefficients) != k:
        _fail("frozen V2 returned the wrong Form coefficient count")
    values = [*coefficients, box]
    if any(type(item) is not float or not math.isfinite(item) for item in values):
        _fail("frozen V2 returned a nonfinite or non-float Form")
    return {"coef": [item.hex() for item in coefficients], "box": box.hex()}


def _validate_form(value: object, label: str, k: int) -> dict:
    result = _dict(value, label, {"coef", "box"})
    coef = _list(result["coef"], f"{label}.coef")
    if len(coef) != k:
        _fail(f"{label}.coef must have exactly {k} entries")
    for index, encoded in enumerate([*coef, result["box"]]):
        encoded = _str(encoded, f"{label}[{index}]")
        try:
            number = float.fromhex(encoded)
        except (ValueError, OverflowError):
            _fail(f"{label} contains an invalid form hex string")
        if not math.isfinite(number) or number.hex() != encoded:
            _fail(f"{label} contains a noncanonical or nonfinite form value")
    return result


def _load_pins() -> tuple[dict, str]:
    path = Path(__file__).with_name("audited_inputs.json")
    pins = _dict(_parse_json_bytes(path.read_bytes(), "audit pins"), "audit pins")
    if set(pins) != {"schema", "numeric_ir", "frozen_v2_lf_sha256"}:
        _fail("audit pin keys mismatch")
    if pins["schema"] != PINS_SCHEMA:
        _fail("audit pin schema mismatch")
    accepted = _dict(pins["numeric_ir"], "audit pins.numeric_ir")
    for digest, record in accepted.items():
        _sha(digest, "audit input digest")
        record = _dict(record, f"audit pin {digest}", {"label", "normalized_numeric_sha256"})
        _str(record["label"], f"audit pin {digest}.label")
        _sha(record["normalized_numeric_sha256"], f"audit pin {digest}.normalized")
    return accepted, _sha(pins["frozen_v2_lf_sha256"], "frozen V2 pin")


def _validate_ir(ir: object, expected_normalized: str) -> tuple[dict[str, dict], dict[str, int], dict[int, dict]]:
    ir = _dict(ir, "Numeric IR", IR_TOP_KEYS)
    if ir["schema"] != IR_SCHEMA:
        _fail("Numeric IR schema mismatch")
    source = _dict(ir["source"], "Numeric IR source", IR_SOURCE_KEYS)
    _str(source["capture_schema"], "Numeric IR source.capture_schema")
    _sha(source["trace_sha256"], "Numeric IR source.trace_sha256")
    _sha(source["final_chain"], "Numeric IR source.final_chain")
    _int(source["record_count"], "Numeric IR source.record_count", minimum=0)
    _int(source["scalar_fp_count"], "Numeric IR source.scalar_fp_count", minimum=0)
    modules = _list(source["module_sha256s"], "Numeric IR source.module_sha256s")
    if modules != sorted(set(modules)):
        _fail("Numeric IR source module hashes are not unique and sorted")
    for index, module in enumerate(modules):
        _sha(module, f"Numeric IR source.module_sha256s[{index}]")
    regions = _list(source["regions"], "Numeric IR source.regions")
    for index, region in enumerate(regions):
        region = _dict(
            region,
            f"Numeric IR source.regions[{index}]",
            {"phase", "start_seq", "end_seq", "start_state", "end_state", "mxcsr"},
        )
        _str(region["phase"], f"region {index}.phase")
        _int(region["start_seq"], f"region {index}.start_seq", minimum=0)
        _int(region["end_seq"], f"region {index}.end_seq", minimum=0)
        _int(region["mxcsr"], f"region {index}.mxcsr", minimum=0)
        for endpoint in ("start_state", "end_state"):
            state = _dict(region[endpoint], f"region {index}.{endpoint}")
            for key, raw in state.items():
                _str(key, f"region {index}.{endpoint} key")
                _str(raw, f"region {index}.{endpoint}.{key}")
    if source["normalized_numeric_sha256"] != expected_normalized:
        _fail("Numeric IR source normalized identity is not audited")
    diagnostic = _dict(
        source["diagnostic"],
        "Numeric IR source.diagnostic",
        {"source_path", "runtime_addresses_excluded_from_normalization"},
    )
    _str(diagnostic["source_path"], "Numeric IR source.diagnostic.source_path")
    if type(diagnostic["runtime_addresses_excluded_from_normalization"]) is not bool:
        _fail("Numeric IR diagnostic flag must be boolean")

    values = _list(ir["values"], "Numeric IR values")
    by_id: dict[str, dict] = {}
    positions: dict[str, int] = {}
    for index, item in enumerate(values):
        value = _dict(item, f"Numeric IR values[{index}]", VALUE_KEYS)
        value_id = _str(value["value_id"], f"value {index}.value_id")
        if value_id in by_id:
            _fail(f"duplicate value ID: {value_id}")
        kind = _str(value["producer_kind"], f"value {value_id}.producer_kind")
        if kind not in VALUE_KINDS:
            _fail(f"unsupported value producer kind: {kind}")
        width = _int(value["width"], f"value {value_id}.width", minimum=1)
        _raw(value["raw_bits"], width, f"value {value_id}.raw_bits")
        producer = _dict(value["producer"], f"value {value_id}.producer")
        role = _str(producer.get("role"), f"value {value_id}.producer.role")
        common = {"role", "trace_sequence", "operand_index", "phase"}
        expected_keys = set(common)
        if role == "boundary":
            expected_keys.add("boundary")
        if kind == "CONST_BITS":
            expected_keys.update({"module_sha256", "file_offset"})
        if kind == "ARITHMETIC_RESULT":
            expected_keys.add("operation_kind")
        if set(producer) != expected_keys:
            _fail(f"value {value_id}.producer keys mismatch")
        _nullable_int(producer["trace_sequence"], f"value {value_id}.trace_sequence")
        _nullable_int(producer["operand_index"], f"value {value_id}.operand_index")
        phase = _str(producer["phase"], f"value {value_id}.phase")
        if phase not in {"init", "step"}:
            _fail(f"value {value_id} has unsupported phase")
        if role == "boundary":
            _str(producer["boundary"], f"value {value_id}.boundary")
            if producer["trace_sequence"] is not None or producer["operand_index"] is not None:
                _fail(f"boundary {value_id} must retain null trace identity")
        if kind == "CONST_BITS":
            _sha(producer["module_sha256"], f"value {value_id}.module_sha256")
            _int(producer["file_offset"], f"value {value_id}.file_offset", minimum=0)
        if kind == "ARITHMETIC_RESULT" and producer["operation_kind"] not in ARITHMETIC_MAP:
            _fail(f"arithmetic result {value_id} has unsupported operation")
        _storage(value["storage"], f"value {value_id}.storage")
        slices = _list(value["source_slices"], f"value {value_id}.source_slices")
        if kind == "COPY_BITS" and not slices:
            _fail(f"COPY value {value_id} has no provenance slices")
        if kind != "COPY_BITS" and slices:
            _fail(f"non-COPY value {value_id} has provenance slices")
        by_id[value_id] = value
        positions[value_id] = index

    for value_id, value in by_id.items():
        occupied: set[int] = set()
        for index, item in enumerate(value["source_slices"]):
            edge = _dict(item, f"value {value_id}.source_slices[{index}]", SLICE_KEYS)
            source_id = _str(edge["value_id"], f"slice {value_id}[{index}].value_id")
            if source_id not in by_id:
                _fail(f"dangling COPY source {source_id}")
            if positions[source_id] >= positions[value_id]:
                _fail(f"temporal-forward COPY edge {source_id} -> {value_id}")
            source_offset = _int(edge["source_offset"], f"slice {value_id}[{index}].source_offset", minimum=0)
            destination_offset = _int(
                edge["destination_offset"], f"slice {value_id}[{index}].destination_offset", minimum=0
            )
            width = _int(edge["width"], f"slice {value_id}[{index}].width", minimum=1)
            if source_offset + width > by_id[source_id]["width"] or destination_offset + width > value["width"]:
                _fail(f"COPY slice {value_id}[{index}] is out of bounds")
            span = set(range(destination_offset, destination_offset + width))
            if occupied.intersection(span):
                _fail(f"overlapping COPY destination slices in {value_id}")
            occupied.update(span)
            _nullable_int(edge["trace_sequence"], f"slice {value_id}[{index}].trace_sequence")
            _nullable_int(edge["source_operand_index"], f"slice {value_id}[{index}].source_operand_index")
            _storage(edge["source_storage"], f"slice {value_id}[{index}].source_storage")
            _storage(edge["destination_storage"], f"slice {value_id}[{index}].destination_storage")
            source_bits = (int(by_id[source_id]["raw_bits"], 16) >> (8 * source_offset)) & (
                (1 << (8 * width)) - 1
            )
            destination_bits = (int(value["raw_bits"], 16) >> (8 * destination_offset)) & (
                (1 << (8 * width)) - 1
            )
            if source_bits != destination_bits:
                _fail(f"COPY slice byte mismatch in {value_id}")

    operations = _list(ir["operations"], "Numeric IR operations")
    if len(operations) != source["scalar_fp_count"]:
        _fail("Numeric IR scalar count does not match operations")
    trace_ids: set[int] = set()
    result_by_sequence: dict[int, dict] = {}
    used_results: set[str] = set()
    last_trace = -1
    for index, item in enumerate(operations):
        operation = _dict(item, f"Numeric IR operations[{index}]", IR_OPERATION_KEYS)
        if _int(operation["ir_sequence"], f"operation {index}.ir_sequence", minimum=0) != index:
            _fail("Numeric IR operation sequence is not dense")
        trace = _int(operation["trace_sequence"], f"operation {index}.trace_sequence", minimum=0)
        if trace in trace_ids or trace <= last_trace:
            _fail("Numeric IR operation trace order is duplicate or reordered")
        trace_ids.add(trace)
        last_trace = trace
        _sha(operation["module_sha256"], f"operation {index}.module_sha256")
        _int(operation["elf_address"], f"operation {index}.elf_address", minimum=0)
        _str(operation["instruction_bytes"], f"operation {index}.instruction_bytes")
        _str(operation["opcode"], f"operation {index}.opcode")
        kind = _str(operation["operation_kind"], f"operation {index}.operation_kind")
        if kind not in ARITHMETIC_MAP:
            _fail(f"unsupported Numeric IR operation kind: {kind}")
        for operand in ("input0", "input1", "output"):
            value_id = _str(operation[f"{operand}_value_id"], f"operation {index}.{operand}_value_id")
            if value_id not in by_id:
                _fail(f"operation {index} has missing {operand} value")
            value = by_id[value_id]
            if value["width"] != 8:
                _fail(f"operation {index} has non-scalar {operand} value")
            expected_bits = _lane_bits(value, 0)
            if operation[f"{operand}_raw_bits"] != expected_bits:
                _fail(f"operation {index} {operand} raw bits mismatch")
        for operand, role, operand_index in (
            ("input0", "arithmetic_destination_pre_read", 1),
            ("input1", "arithmetic_source_read", 0),
        ):
            value = by_id[operation[f"{operand}_value_id"]]
            producer = value["producer"]
            copy_occurrence = value["producer_kind"] == "COPY_BITS" and producer["role"] == role
            constant_occurrence = (
                operand == "input1"
                and value["producer_kind"] == "CONST_BITS"
                and producer["role"] == "constant_read"
            )
            if not (copy_occurrence or constant_occurrence) or (
                producer["trace_sequence"] != trace or producer["operand_index"] != operand_index
            ):
                _fail(f"operation {index} {operand} occurrence identity mismatch")
        output = by_id[operation["output_value_id"]]
        producer = output["producer"]
        if (
            output["producer_kind"] != "ARITHMETIC_RESULT"
            or producer["role"] != "arithmetic_result"
            or producer["trace_sequence"] != trace
            or producer["operand_index"] != 1
            or producer["operation_kind"] != kind
        ):
            _fail(f"operation {index} output producer mismatch")
        if operation["output_value_id"] in used_results:
            _fail("arithmetic result is produced more than once")
        used_results.add(operation["output_value_id"])
        phase = _str(operation["phase"], f"operation {index}.phase")
        if phase != producer["phase"]:
            _fail(f"operation {index} phase mismatch")
        _int(operation["step"], f"operation {index}.step", minimum=0)
        _int(operation["mxcsr"], f"operation {index}.mxcsr", minimum=0)
        result_by_sequence[index] = output
    all_results = {value_id for value_id, value in by_id.items() if value["producer_kind"] == "ARITHMETIC_RESULT"}
    if used_results != all_results:
        _fail("Numeric IR arithmetic result coverage mismatch")
    semantic = {"schema": ir["schema"], "operations": operations, "values": values}
    digest = hashlib.sha256(_canonical(semantic)).hexdigest()
    if digest != expected_normalized or digest != source["normalized_numeric_sha256"]:
        _fail("Numeric IR normalized semantic identity mismatch")
    return by_id, positions, result_by_sequence


def _lf_sha(path: Path, label: str) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read {label}: {exc}")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _frozen_protocol(root: Path | None, expected_hash: str):
    import lab.v2_bound as v2

    imported_path = Path(v2.__file__).resolve()
    requested_root = Path(root).resolve() if root is not None else imported_path.parents[1]
    requested_path = requested_root / "lab" / "v2_bound.py"
    imported_hash = _lf_sha(imported_path, "imported frozen V2")
    requested_hash = _lf_sha(requested_path, "requested frozen V2")
    if imported_hash != expected_hash or requested_hash != expected_hash:
        _fail("frozen V2 source identity mismatch")
    if type(v2.K) is not int or v2.K != 4:
        _fail("frozen V2 K interface mismatch")
    if not callable(v2.Form) or not callable(v2.step_forms):
        _fail("frozen V2 callable interface mismatch")
    protocol = {
        "module": FROZEN_MODULE,
        "operator": FROZEN_OPERATOR,
        "k": v2.K,
        "lf_sha256": expected_hash,
        "imported_lf_sha256": imported_hash,
        "requested_lf_sha256": requested_hash,
    }
    return v2, protocol


def _state_id(value_id: str, offset: int) -> str:
    return f"state:{value_id}:byte:{offset}"


def _first_difference(expected: object, actual: object, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if type(expected) is dict:
        if set(expected) != set(actual):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            return f"{path}: object keys differ; missing={missing}, extra={extra}"
        for key in sorted(expected):
            found = _first_difference(expected[key], actual[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if type(expected) is list:
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} items, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = _first_difference(left, right, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if expected != actual:
        return f"{path}: expected {expected!r}, got {actual!r}"
    return None


def _validate_output_shape(output: object, k: int) -> dict:
    output = _dict(output, "correspondence", OUTPUT_TOP_KEYS)
    if output["schema"] != SCHEMA:
        _fail("correspondence schema mismatch")
    source = _dict(output["source"], "correspondence.source", OUTPUT_SOURCE_KEYS)
    _str(source["audited_input_label"], "correspondence.source.audited_input_label")
    _sha(source["numeric_ir_sha256"], "correspondence.source.numeric_ir_sha256")
    _sha(source["normalized_numeric_sha256"], "correspondence.source.normalized_numeric_sha256")
    _str(source["numeric_ir_schema"], "correspondence.source.numeric_ir_schema")
    _dict(source["numeric_ir_source"], "correspondence.source.numeric_ir_source")
    frozen = _dict(source["frozen_v2"], "correspondence.source.frozen_v2", FROZEN_KEYS)
    _str(frozen["module"], "frozen_v2.module")
    _str(frozen["operator"], "frozen_v2.operator")
    _int(frozen["k"], "frozen_v2.k", minimum=1)
    for key in ("lf_sha256", "imported_lf_sha256", "requested_lf_sha256"):
        _sha(frozen[key], f"frozen_v2.{key}")
    _list(output["values"], "correspondence.values")
    for index, state in enumerate(_list(output["state_bindings"], "correspondence.state_bindings")):
        state = _dict(state, f"state_bindings[{index}]", STATE_KEYS)
        _str(state["state_id"], f"state_bindings[{index}].state_id")
        _str(state["value_id"], f"state_bindings[{index}].value_id")
        _int(state["byte_offset"], f"state_bindings[{index}].byte_offset", minimum=0)
        _int(state["width"], f"state_bindings[{index}].width", minimum=1)
        raw = _str(state["raw_center_bits"], f"state_bindings[{index}].raw_center_bits")
        if HEX64.fullmatch(raw) is None:
            _fail(f"state_bindings[{index}].raw_center_bits is malformed")
        _validate_form(state["form"], f"state_bindings[{index}].form", k)
        _str(state["binding_kind"], f"state_bindings[{index}].binding_kind")
        _nullable_str(state["source_state_id"], f"state_bindings[{index}].source_state_id")
        _nullable_int(state["producer_ir_sequence"], f"state_bindings[{index}].producer_ir_sequence")
        _str(state["phase"], f"state_bindings[{index}].phase")
        _nullable_int(state["trace_sequence"], f"state_bindings[{index}].trace_sequence")
    for index, boundary in enumerate(_list(output["boundaries"], "correspondence.boundaries")):
        boundary = _dict(boundary, f"boundaries[{index}]", BOUNDARY_KEYS)
        for key in ("value_id", "phase", "boundary", "producer_kind", "classification"):
            _str(boundary[key], f"boundaries[{index}].{key}")
        _nullable_int(boundary["trace_sequence"], f"boundaries[{index}].trace_sequence")
        for item in _list(boundary["state_ids"], f"boundaries[{index}].state_ids"):
            _str(item, f"boundaries[{index}].state_ids item")
    for index, operation in enumerate(_list(output["operations"], "correspondence.operations")):
        operation = _dict(
            operation,
            f"operations[{index}]",
            IR_OPERATION_KEYS | ADAPTER_OPERATION_KEYS,
        )
        for key in ("ir_sequence", "trace_sequence", "elf_address", "mxcsr", "step", "v2_sequence"):
            _int(operation[key], f"operations[{index}].{key}", minimum=0)
        for key in (
            "module_sha256",
            "instruction_bytes",
            "opcode",
            "operation_kind",
            "input0_value_id",
            "input1_value_id",
            "output_value_id",
            "input0_raw_bits",
            "input1_raw_bits",
            "output_raw_bits",
            "phase",
            "v2_operation_kind",
            "input0_state_id",
            "input1_state_id",
            "output_state_id",
        ):
            _str(operation[key], f"operations[{index}].{key}")
        for key in ("input0_form", "input1_form", "output_form"):
            _validate_form(operation[key], f"operations[{index}].{key}", k)
    return output


def _reconstruct(ir: dict, by_id: dict[str, dict], v2: object, protocol: dict) -> dict:
    operations = ir["operations"]
    selected: set[tuple[str, int]] = set()
    copy_source: dict[tuple[str, int], tuple[str, int]] = {}
    visiting: set[tuple[str, int]] = set()

    def select(value_id: str, offset: int) -> None:
        key = (value_id, offset)
        if key in selected:
            return
        if key in visiting:
            _fail(f"COPY provenance cycle at {value_id}:{offset}")
        value = by_id[value_id]
        _lane_bits(value, offset)
        visiting.add(key)
        if value["producer_kind"] == "COPY_BITS":
            covering = [
                edge
                for edge in value["source_slices"]
                if edge["destination_offset"] <= offset
                and edge["destination_offset"] + edge["width"] >= offset + 8
            ]
            if len(covering) != 1:
                _fail(f"COPY lane {value_id}:{offset} is mixed or incomplete")
            edge = covering[0]
            source_offset = edge["source_offset"] + offset - edge["destination_offset"]
            source_key = (edge["value_id"], source_offset)
            if _lane_bits(by_id[source_key[0]], source_key[1]) != _lane_bits(value, offset):
                _fail(f"COPY lane bits mismatch at {value_id}:{offset}")
            copy_source[key] = source_key
            select(*source_key)
        visiting.remove(key)
        selected.add(key)

    for operation in operations:
        select(operation["input0_value_id"], 0)
        select(operation["input1_value_id"], 0)
        select(operation["output_value_id"], 0)
    boundary_values = [value for value in ir["values"] if value["producer"].get("role") == "boundary"]
    for value in boundary_values:
        if value["width"] % 8:
            _fail(f"boundary {value['value_id']} has an incomplete scalar lane")
        for offset in range(0, value["width"], 8):
            select(value["value_id"], offset)

    result_sequence = {operation["output_value_id"]: index for index, operation in enumerate(operations)}
    state_metadata: dict[tuple[str, int], dict] = {}
    for value_id, offset in selected:
        value = by_id[value_id]
        producer = value["producer"]
        key = (value_id, offset)
        state_metadata[key] = {
            "state_id": _state_id(value_id, offset),
            "value_id": value_id,
            "byte_offset": offset,
            "width": 8,
            "raw_center_bits": _lane_bits(value, offset),
            "binding_kind": STATE_KIND[value["producer_kind"]],
            "source_state_id": _state_id(*copy_source[key]) if key in copy_source else None,
            "producer_ir_sequence": result_sequence.get(value_id),
            "phase": producer["phase"],
            "trace_sequence": producer["trace_sequence"],
        }
    forms: dict[tuple[str, int], object] = {}

    def resolve_form(key: tuple[str, int]):
        if key in forms:
            return forms[key]
        value = by_id[key[0]]
        kind = value["producer_kind"]
        if kind in {"LOAD_BITS", "CONST_BITS", "ZERO_BITS"}:
            form = v2.Form([0.0] * v2.K, 0.0)
        elif kind == "COPY_BITS":
            form = resolve_form(copy_source[key])
        else:
            _fail(f"arithmetic state {key[0]} requested before its producer")
        forms[key] = form
        return form

    expected_operations: list[dict] = []
    for index, operation in enumerate(operations):
        input0_key = (operation["input0_value_id"], 0)
        input1_key = (operation["input1_value_id"], 0)
        output_key = (operation["output_value_id"], 0)
        input0 = resolve_form(input0_key)
        input1 = resolve_form(input1_key)
        input0_state = _state_id(*input0_key)
        input1_state = _state_id(*input1_key)
        output_state = _state_id(*output_key)
        v2_kind = ARITHMETIC_MAP[operation["operation_kind"]]
        structure = [(v2_kind, output_state, [input0_state, input1_state], None)]
        regs = {
            input0_state: int(operation["input0_raw_bits"], 16),
            input1_state: int(operation["input1_raw_bits"], 16),
            output_state: int(operation["output_raw_bits"], 16),
        }
        try:
            executed = v2.step_forms(
                structure,
                regs,
                {input0_state: input0, input1_state: input1},
            )
        except Exception as exc:
            _fail(f"frozen V2 refused operation {index}: {exc}")
        if type(executed) is not dict or output_state not in executed:
            _fail(f"frozen V2 did not return operation {index} output")
        output_form = executed[output_state]
        _form_document(output_form, v2.K)
        forms[output_key] = output_form
        expected_operations.append(
            {
                **operation,
                "v2_sequence": index,
                "v2_operation_kind": v2_kind,
                "input0_state_id": input0_state,
                "input1_state_id": input1_state,
                "output_state_id": output_state,
                "input0_form": _form_document(input0, v2.K),
                "input1_form": _form_document(input1, v2.K),
                "output_form": _form_document(output_form, v2.K),
            }
        )

    expected_states: list[dict] = []
    for key in sorted(selected):
        form = resolve_form(key)
        expected_states.append({**state_metadata[key], "form": _form_document(form, v2.K)})

    boundaries: list[dict] = []
    for value in boundary_values:
        producer = value["producer"]
        if producer["trace_sequence"] is not None or producer["operand_index"] is not None:
            _fail(f"boundary {value['value_id']} lost null trace identity")
        if value["producer_kind"] == "LOAD_BITS":
            classification = "CAPTURED_INPUT_ROOT"
        elif value["producer_kind"] == "COPY_BITS" and producer["phase"] == "step":
            classification = "CAPTURED_STATE_HANDOFF"
            for edge in value["source_slices"]:
                if edge["trace_sequence"] is not None or edge["source_operand_index"] is not None:
                    _fail(f"boundary handoff {value['value_id']} claims an instruction trace")
        else:
            _fail(f"unsupported boundary producer {value['value_id']}")
        boundaries.append(
            {
                "value_id": value["value_id"],
                "phase": producer["phase"],
                "boundary": producer["boundary"],
                "producer_kind": value["producer_kind"],
                "classification": classification,
                "trace_sequence": None,
                "state_ids": [
                    _state_id(value["value_id"], offset) for offset in range(0, value["width"], 8)
                ],
            }
        )
    return {
        "schema": SCHEMA,
        "source": None,
        "values": ir["values"],
        "boundaries": boundaries,
        "state_bindings": expected_states,
        "operations": expected_operations,
    }


def check(output: dict, ir_path: Path, root: Path | None = None) -> dict:
    """Independently validate one correspondence against an accepted Numeric IR."""

    ir_path = Path(ir_path)
    try:
        ir_raw = ir_path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read Numeric IR: {exc}")
    ir_digest = hashlib.sha256(ir_raw).hexdigest()
    accepted, frozen_hash = _load_pins()
    if ir_digest not in accepted:
        _fail("Numeric IR byte identity is not an audited input")
    pin = accepted[ir_digest]
    ir = _parse_json_bytes(ir_raw, "Numeric IR")
    by_id, _, _ = _validate_ir(ir, pin["normalized_numeric_sha256"])
    v2, protocol = _frozen_protocol(root, frozen_hash)
    output = _validate_output_shape(output, v2.K)
    expected = _reconstruct(ir, by_id, v2, protocol)
    expected["source"] = {
        "audited_input_label": pin["label"],
        "numeric_ir_sha256": ir_digest,
        "normalized_numeric_sha256": pin["normalized_numeric_sha256"],
        "numeric_ir_schema": ir["schema"],
        "numeric_ir_source": ir["source"],
        "frozen_v2": protocol,
    }
    difference = _first_difference(expected, output)
    if difference is not None:
        _fail(f"correspondence mismatch at {difference}")
    kind_counts = {kind: 0 for kind in sorted(ARITHMETIC_MAP.values())}
    for operation in expected["operations"]:
        kind_counts[operation["v2_operation_kind"]] += 1
    return {
        "schema": REPORT_SCHEMA,
        "verdict": "PASS",
        "correspondence_sha256": hashlib.sha256(_canonical(output)).hexdigest(),
        "source_numeric_ir_sha256": ir_digest,
        "source_normalized_numeric_sha256": pin["normalized_numeric_sha256"],
        "operation_count": len(expected["operations"]),
        "state_binding_count": len(expected["state_bindings"]),
        "boundary_count": len(expected["boundaries"]),
        "operation_kind_counts": kind_counts,
        "ir_to_v2_missing": 0,
        "ir_to_v2_duplicate": 0,
        "ir_to_v2_extra": 0,
        "ir_to_v2_reorder": 0,
    }


def _validate_completion(completion: object, raw_correspondence: bytes, output: dict) -> None:
    expected_keys = {
        "schema",
        "verdict",
        "correspondence_sha256",
        "source_numeric_ir_sha256",
        "source_normalized_numeric_sha256",
        "operation_count",
        "state_binding_count",
        "boundary_count",
    }
    completion = _dict(completion, "completion report", expected_keys)
    if completion["schema"] != COMPLETION_SCHEMA or completion["verdict"] != "ADAPTED":
        _fail("completion report status mismatch")
    output = _dict(output, "correspondence", OUTPUT_TOP_KEYS)
    source = _dict(output["source"], "correspondence.source", OUTPUT_SOURCE_KEYS)
    operations = _list(output["operations"], "correspondence.operations")
    states = _list(output["state_bindings"], "correspondence.state_bindings")
    boundaries = _list(output["boundaries"], "correspondence.boundaries")
    expected = {
        "correspondence_sha256": hashlib.sha256(raw_correspondence).hexdigest(),
        "source_numeric_ir_sha256": source["numeric_ir_sha256"],
        "source_normalized_numeric_sha256": source["normalized_numeric_sha256"],
        "operation_count": len(operations),
        "state_binding_count": len(states),
        "boundary_count": len(boundaries),
    }
    for key, value in expected.items():
        if key.endswith("count"):
            _int(completion[key], f"completion report.{key}", minimum=0)
        else:
            _sha(completion[key], f"completion report.{key}")
        if type(completion[key]) is not type(value) or completion[key] != value:
            _fail(f"completion report {key} mismatch")


def _write_new(path: Path, value: dict) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(_canonical(value))
    except FileExistsError:
        raise


def _failure_report(reason: str) -> dict:
    return {"schema": REPORT_SCHEMA, "verdict": "FAIL", "reason": reason}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correspondence", required=True, type=Path)
    parser.add_argument("--ir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    if args.report.exists():
        print(json.dumps(_failure_report("report path already exists"), sort_keys=True), file=sys.stderr)
        return 2
    try:
        raw = args.correspondence.read_bytes()
        output = _parse_json_bytes(raw, "correspondence")
        if _canonical(output) != raw:
            _fail("correspondence is not canonical JSON")
        completion_path = args.correspondence.parent / "completion_report.json"
        completion = _parse_json_bytes(completion_path.read_bytes(), "completion report")
        if _canonical(completion) != completion_path.read_bytes():
            _fail("completion report is not canonical JSON")
        _validate_completion(completion, raw, output)
        report = check(output, args.ir, root=args.root)
        _write_new(args.report, report)
    except (V2CheckError, OSError, FileExistsError) as exc:
        failure = _failure_report(str(exc))
        try:
            _write_new(args.report, failure)
        except (OSError, FileExistsError):
            pass
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"verdict": "PASS", "report": str(args.report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
