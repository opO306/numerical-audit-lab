"""Translate either byte-pinned audited Numeric IR into frozen V2 calls.

The IR supplies every represented center.  This module propagates ``Form``
objects with the unchanged frozen operator; it does not independently compute
or certify those centers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import sys
from pathlib import Path
from typing import NoReturn

from lab import v2_bound

from .schema import REPORT_SCHEMA, SCHEMA, canonical_json, form_document, write_canonical


IR_SCHEMA = "runtime-trace-numeric-ir-regular-1step-v1"
PIN_SCHEMA = "numeric-ir-frozen-v2-audited-input-pins-v1"
IR_OPERATION_KEYS = {
    "ir_sequence", "trace_sequence", "module_sha256", "elf_address",
    "instruction_bytes", "opcode", "operation_kind", "input0_value_id",
    "input1_value_id", "output_value_id", "input0_raw_bits",
    "input1_raw_bits", "output_raw_bits", "mxcsr", "phase", "step",
}
IR_VALUE_KEYS = {
    "value_id", "producer_kind", "raw_bits", "width", "producer",
    "storage", "source_slices",
}
SLICE_KEYS = {
    "value_id", "source_offset", "destination_offset", "width",
    "trace_sequence", "source_operand_index", "source_storage",
    "destination_storage",
}
STORAGE_KEYS = {"space", "name", "byte_offset", "width"}
SOURCE_KEYS = {
    "capture_schema", "trace_sha256", "final_chain", "record_count",
    "scalar_fp_count", "module_sha256s", "regions",
    "normalized_numeric_sha256", "diagnostic",
}
REGION_KEYS = {"phase", "start_seq", "end_seq", "start_state", "end_state", "mxcsr"}
STATE_KEYS = {"q", "full_v", "latent", "gradient"}
KIND_MAP = {
    "ADD_BINARY64": "ADD",
    "SUB_BINARY64": "SUB",
    "MUL_BINARY64": "MUL",
}
ROOT_KINDS = {"LOAD_BITS", "CONST_BITS", "ZERO_BITS"}
VALUE_KINDS = ROOT_KINDS | {"COPY_BITS", "ARITHMETIC_RESULT"}
BOUNDARIES = {"q", "full_v", "latent", "gradient", "xmm0", "xmm1"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class AdapterRefused(ValueError):
    """The input or frozen prerequisite does not satisfy the adapter contract."""


def _refuse(reason: str) -> NoReturn:
    raise AdapterRefused(reason)


def _exact_object(value: object, keys: set[str], where: str) -> dict:
    if type(value) is not dict:
        _refuse(f"{where} must be an object")
    if set(value) != keys:
        _refuse(f"{where} keys are malformed")
    return value


def _exact_list(value: object, where: str) -> list:
    if type(value) is not list:
        _refuse(f"{where} must be an array")
    return value


def _string(value: object, where: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        _refuse(f"{where} must be a string")
    return value


def _integer(value: object, where: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        _refuse(f"{where} must be an integer")
    return value


def _nullable_integer(value: object, where: str) -> int | None:
    if value is None:
        return None
    return _integer(value, where, minimum=0)


def _sha(value: object, where: str) -> str:
    text = _string(value, where)
    if HEX64.fullmatch(text) is None:
        _refuse(f"{where} must be a lowercase SHA-256")
    return text


def _raw(value: object, width: int, where: str) -> str:
    text = _string(value, where)
    if re.fullmatch(rf"0x[0-9a-f]{{{2 * width}}}", text) is None:
        _refuse(f"{where} is not an exact {width}-byte raw value")
    return text


def _raw_bytes(raw_bits: str, width: int) -> bytes:
    return int(raw_bits, 16).to_bytes(width, "little")


def _lane_bits(value: dict, offset: int) -> str:
    if type(offset) is not int or offset < 0 or offset + 8 > value["width"]:
        _refuse(f"invalid 8-byte lane {value['value_id']}+{offset}")
    lane = _raw_bytes(value["raw_bits"], value["width"])[offset:offset + 8]
    bits = int.from_bytes(lane, "little")
    if not math.isfinite(struct.unpack("<d", lane)[0]):
        _refuse(f"nonfinite binary64 lane {value['value_id']}+{offset}")
    return f"0x{bits:016x}"


def _state_id(value_id: str, offset: int) -> str:
    return f"state:{value_id}:byte:{offset}"


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            _refuse(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _refuse(f"cannot read Numeric IR: {exc}")
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs)
    except AdapterRefused:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _refuse(f"malformed Numeric IR JSON: {exc}")
    if type(value) is not dict:
        _refuse("Numeric IR top level must be an object")
    return value, raw


def _load_pins() -> dict:
    pin_path = Path(__file__).with_name("audited_inputs.json")
    try:
        pins = json.loads(pin_path.read_bytes(), object_pairs_hook=_strict_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _refuse(f"cannot load audit pins: {exc}")
    _exact_object(pins, {"schema", "numeric_ir", "frozen_v2_lf_sha256"}, "audit pins")
    if pins["schema"] != PIN_SCHEMA or type(pins["numeric_ir"]) is not dict:
        _refuse("audit pins are malformed")
    _sha(pins["frozen_v2_lf_sha256"], "audit pins frozen V2 hash")
    return pins


def _lf_sha(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _refuse(f"cannot read frozen V2 prerequisite: {exc}")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _verify_frozen(root: Path | None, expected: str) -> dict:
    imported_path = Path(v2_bound.__file__).resolve()
    requested_root = Path(root).resolve() if root is not None else imported_path.parent.parent
    requested_path = requested_root / "lab/v2_bound.py"
    imported_hash = _lf_sha(imported_path)
    requested_hash = _lf_sha(requested_path)
    if imported_hash != expected or requested_hash != expected:
        _refuse("frozen V2 prerequisite byte identity mismatch")
    if type(v2_bound.K) is not int or v2_bound.K != 4 or not callable(v2_bound.step_forms):
        _refuse("frozen V2 interface mismatch")
    return {
        "module": "lab.v2_bound",
        "operator": "step_forms",
        "k": v2_bound.K,
        "lf_sha256": expected,
        "imported_lf_sha256": imported_hash,
        "requested_lf_sha256": requested_hash,
    }


def _validate_storage(storage: object, where: str) -> dict:
    item = _exact_object(storage, STORAGE_KEYS, where)
    if item["space"] not in {
        "buffer", "register", "stack", "elf", "memory-occurrence",
        "instruction", "control",
    }:
        _refuse(f"{where}.space is unsupported")
    _string(item["name"], f"{where}.name")
    _integer(item["byte_offset"], f"{where}.byte_offset")
    _integer(item["width"], f"{where}.width", minimum=1)
    return item


def _validate_producer(value: dict, where: str) -> dict:
    producer = value["producer"]
    if type(producer) is not dict:
        _refuse(f"{where}.producer must be an object")
    role = _string(producer.get("role"), f"{where}.producer.role")
    common = {"role", "trace_sequence", "operand_index", "phase"}
    if role == "boundary":
        _exact_object(producer, common | {"boundary"}, f"{where}.producer")
        if producer["boundary"] not in BOUNDARIES or producer["trace_sequence"] is not None or producer["operand_index"] is not None:
            _refuse(f"{where} boundary producer is malformed")
    elif role == "constant_read":
        _exact_object(producer, common | {"module_sha256", "file_offset"}, f"{where}.producer")
        _sha(producer["module_sha256"], f"{where}.producer.module_sha256")
        _integer(producer["file_offset"], f"{where}.producer.file_offset", minimum=0)
    elif role == "arithmetic_result":
        _exact_object(producer, common | {"operation_kind"}, f"{where}.producer")
        if producer["operation_kind"] not in KIND_MAP:
            _refuse(f"{where} arithmetic producer kind is unsupported")
    else:
        _exact_object(producer, common, f"{where}.producer")
    if producer["phase"] not in {"init", "step"}:
        _refuse(f"{where}.producer.phase is invalid")
    if role != "boundary":
        _integer(producer["trace_sequence"], f"{where}.producer.trace_sequence", minimum=0)
        _integer(producer["operand_index"], f"{where}.producer.operand_index", minimum=0)
    return producer


def _validate_source(source: object, operations: list, values: list) -> dict:
    item = _exact_object(source, SOURCE_KEYS, "source")
    if item["capture_schema"] != "gala-regular-1step-runtime-trace-v1":
        _refuse("source capture schema is unsupported")
    _sha(item["trace_sha256"], "source.trace_sha256")
    _sha(item["final_chain"], "source.final_chain")
    _integer(item["record_count"], "source.record_count", minimum=1)
    scalar_count = _integer(item["scalar_fp_count"], "source.scalar_fp_count", minimum=0)
    if scalar_count != len(operations):
        _refuse("source scalar count does not match derived operation count")
    modules = _exact_list(item["module_sha256s"], "source.module_sha256s")
    if modules != sorted(set(modules)):
        _refuse("source module identities are not sorted and unique")
    for index, module in enumerate(modules):
        _sha(module, f"source.module_sha256s[{index}]")
    regions = _exact_list(item["regions"], "source.regions")
    if [region.get("phase") if type(region) is dict else None for region in regions] != ["init", "step"]:
        _refuse("source regions must be init then step")
    for index, region_value in enumerate(regions):
        region = _exact_object(region_value, REGION_KEYS, f"source.regions[{index}]")
        start = _integer(region["start_seq"], f"source.regions[{index}].start_seq", minimum=0)
        end = _integer(region["end_seq"], f"source.regions[{index}].end_seq", minimum=0)
        if end <= start:
            _refuse("source region is empty or reversed")
        _integer(region["mxcsr"], f"source.regions[{index}].mxcsr", minimum=0)
        for state_name in ("start_state", "end_state"):
            state = _exact_object(region[state_name], STATE_KEYS, f"source.regions[{index}].{state_name}")
            for name, raw_bits in state.items():
                _raw(raw_bits, 16, f"source.regions[{index}].{state_name}.{name}")
    diagnostic = _exact_object(
        item["diagnostic"],
        {"source_path", "runtime_addresses_excluded_from_normalization"},
        "source.diagnostic",
    )
    _string(diagnostic["source_path"], "source.diagnostic.source_path")
    if diagnostic["runtime_addresses_excluded_from_normalization"] is not True:
        _refuse("source diagnostic normalization marker is invalid")
    _sha(item["normalized_numeric_sha256"], "source.normalized_numeric_sha256")
    normalized = {"schema": IR_SCHEMA, "operations": operations, "values": values}
    if hashlib.sha256(canonical_json(normalized)).hexdigest() != item["normalized_numeric_sha256"]:
        _refuse("Numeric IR semantic identity mismatch")
    return item


def _validate_document(document: dict) -> tuple[list, list, dict[str, dict]]:
    _exact_object(document, {"schema", "source", "operations", "values"}, "Numeric IR")
    if document["schema"] != IR_SCHEMA:
        _refuse("Numeric IR schema is unsupported")
    operations = _exact_list(document["operations"], "operations")
    values = _exact_list(document["values"], "values")

    by_id: dict[str, dict] = {}
    for index, value_object in enumerate(values):
        where = f"values[{index}]"
        value = _exact_object(value_object, IR_VALUE_KEYS, where)
        value_id = _string(value["value_id"], f"{where}.value_id")
        if value_id in by_id:
            _refuse(f"duplicate value ID: {value_id}")
        width = _integer(value["width"], f"{where}.width", minimum=1)
        _raw(value["raw_bits"], width, f"{where}.raw_bits")
        if value["producer_kind"] not in VALUE_KINDS:
            _refuse(f"{where}.producer_kind is unsupported")
        producer = _validate_producer(value, where)
        _validate_storage(value["storage"], f"{where}.storage")
        slices = _exact_list(value["source_slices"], f"{where}.source_slices")
        if value["producer_kind"] == "COPY_BITS" and not slices:
            _refuse(f"{where} COPY_BITS has no provenance slices")
        if value["producer_kind"] != "COPY_BITS" and slices:
            _refuse(f"{where} non-copy value has provenance slices")
        if value["producer_kind"] == "LOAD_BITS" and producer["role"] != "boundary":
            _refuse(f"{where} LOAD_BITS is not a declared boundary")
        if value["producer_kind"] == "CONST_BITS" and producer["role"] != "constant_read":
            _refuse(f"{where} CONST_BITS producer is invalid")
        if value["producer_kind"] == "ARITHMETIC_RESULT" and producer["role"] != "arithmetic_result":
            _refuse(f"{where} arithmetic result producer is invalid")
        by_id[value_id] = value

    for index, value in enumerate(values):
        occupied: list[tuple[int, int]] = []
        for slice_index, slice_object in enumerate(value["source_slices"]):
            where = f"values[{index}].source_slices[{slice_index}]"
            edge = _exact_object(slice_object, SLICE_KEYS, where)
            source_id = _string(edge["value_id"], f"{where}.value_id")
            if source_id not in by_id:
                _refuse(f"dangling provenance edge: {source_id}")
            source_offset = _integer(edge["source_offset"], f"{where}.source_offset", minimum=0)
            destination_offset = _integer(edge["destination_offset"], f"{where}.destination_offset", minimum=0)
            width = _integer(edge["width"], f"{where}.width", minimum=1)
            source = by_id[source_id]
            if source_offset + width > source["width"] or destination_offset + width > value["width"]:
                _refuse(f"{where} exceeds value width")
            for start, end in occupied:
                if destination_offset < end and start < destination_offset + width:
                    _refuse(f"{where} overlaps another destination slice")
            occupied.append((destination_offset, destination_offset + width))
            trace_sequence = _nullable_integer(edge["trace_sequence"], f"{where}.trace_sequence")
            source_operand = edge["source_operand_index"]
            if source_operand is not None:
                _integer(source_operand, f"{where}.source_operand_index", minimum=0)
            _validate_storage(edge["source_storage"], f"{where}.source_storage")
            _validate_storage(edge["destination_storage"], f"{where}.destination_storage")
            producer = value["producer"]
            if producer["role"] == "boundary":
                if producer["phase"] != "step" or trace_sequence is not None or source_operand is not None:
                    _refuse("boundary handoff provenance must retain null trace identity")
            elif trace_sequence != producer["trace_sequence"]:
                _refuse(f"{where} does not identify its consuming occurrence")
            source_trace = source["producer"]["trace_sequence"]
            if type(source_trace) is int and type(trace_sequence) is int and source_trace > trace_sequence:
                _refuse(f"{where} is a temporal forward edge")
            source_bytes = _raw_bytes(source["raw_bits"], source["width"])[source_offset:source_offset + width]
            destination_bytes = _raw_bytes(value["raw_bits"], value["width"])[destination_offset:destination_offset + width]
            if source_bytes != destination_bytes:
                _refuse(f"{where} raw bytes disagree")

    source = _validate_source(document["source"], operations, values)
    seen_trace: set[int] = set()
    output_ids: set[str] = set()
    previous_trace = -1
    for index, operation_object in enumerate(operations):
        where = f"operations[{index}]"
        operation = _exact_object(operation_object, IR_OPERATION_KEYS, where)
        if _integer(operation["ir_sequence"], f"{where}.ir_sequence", minimum=0) != index:
            _refuse("IR operation sequence is not dense and ordered")
        trace = _integer(operation["trace_sequence"], f"{where}.trace_sequence", minimum=0)
        if trace in seen_trace or trace <= previous_trace:
            _refuse("IR operation trace order is duplicated or reordered")
        seen_trace.add(trace)
        previous_trace = trace
        if operation["operation_kind"] not in KIND_MAP:
            _refuse(f"{where}.operation_kind is unsupported")
        for name in ("input0_value_id", "input1_value_id", "output_value_id"):
            value_id = _string(operation[name], f"{where}.{name}")
            if value_id not in by_id:
                _refuse(f"{where} references missing value {value_id}")
        for side in ("input0", "input1", "output"):
            value = by_id[operation[f"{side}_value_id"]]
            if value["width"] != 8 or operation[f"{side}_raw_bits"] != value["raw_bits"]:
                _refuse(f"{where}.{side} raw bits or width mismatch")
            _lane_bits(value, 0)
        output = by_id[operation["output_value_id"]]
        producer = output["producer"]
        if output["producer_kind"] != "ARITHMETIC_RESULT" or producer["trace_sequence"] != trace or producer["operation_kind"] != operation["operation_kind"]:
            _refuse(f"{where} output producer identity mismatch")
        if operation["output_value_id"] in output_ids:
            _refuse(f"{where} duplicates an arithmetic output")
        output_ids.add(operation["output_value_id"])
        for side in ("input0", "input1"):
            input_value = by_id[operation[f"{side}_value_id"]]
            input_producer = input_value["producer"]
            if input_producer["role"] not in {"constant_read", "arithmetic_destination_pre_read", "arithmetic_source_read"}:
                _refuse(f"{where}.{side} occurrence identity is invalid")
            if input_producer["trace_sequence"] != trace:
                _refuse(f"{where}.{side} occurrence does not match the operation")
        _sha(operation["module_sha256"], f"{where}.module_sha256")
        if operation["module_sha256"] not in source["module_sha256s"]:
            _refuse(f"{where} module is absent from source identities")
        _integer(operation["elf_address"], f"{where}.elf_address", minimum=0)
        instruction = _string(operation["instruction_bytes"], f"{where}.instruction_bytes")
        if re.fullmatch(r"[0-9a-f]+", instruction) is None or len(instruction) % 2:
            _refuse(f"{where}.instruction_bytes is malformed")
        _string(operation["opcode"], f"{where}.opcode")
        _integer(operation["mxcsr"], f"{where}.mxcsr", minimum=0)
        if operation["phase"] not in {"init", "step"}:
            _refuse(f"{where}.phase is invalid")
        expected_step = 0 if operation["phase"] == "init" else 1
        if _integer(operation["step"], f"{where}.step", minimum=0) != expected_step:
            _refuse(f"{where}.step is invalid")
    arithmetic_values = {value["value_id"] for value in values if value["producer_kind"] == "ARITHMETIC_RESULT"}
    if arithmetic_values != output_ids:
        _refuse("arithmetic result coverage does not match operations")
    return operations, values, by_id


class _Execution:
    def __init__(self, values: dict[str, dict], operation_index: dict[str, int]):
        self.values = values
        self.operation_index = operation_index
        self.forms: dict[str, object] = {}
        self.bindings: dict[str, dict] = {}
        self.order: list[str] = []
        self.resolving: set[str] = set()

    def bind(self, value_id: str, offset: int, before_operation: int | None = None) -> str:
        state_id = _state_id(value_id, offset)
        if state_id in self.bindings:
            return state_id
        if state_id in self.resolving:
            _refuse(f"cyclic state provenance at {state_id}")
        value = self.values[value_id]
        raw_bits = _lane_bits(value, offset)
        producer_kind = value["producer_kind"]
        self.resolving.add(state_id)
        try:
            source_state_id = None
            producer_ir_sequence = None
            if producer_kind in ROOT_KINDS:
                form = v2_bound.Form([0.0] * v2_bound.K, 0.0)
                binding_kind = producer_kind.removesuffix("_BITS")
            elif producer_kind == "COPY_BITS":
                matching = []
                for edge in value["source_slices"]:
                    start = edge["destination_offset"]
                    end = start + edge["width"]
                    if start <= offset and offset + 8 <= end:
                        matching.append(edge)
                    elif offset < end and start < offset + 8:
                        _refuse(f"mixed or incomplete scalar lane {state_id}")
                if len(matching) != 1:
                    _refuse(f"scalar lane {state_id} does not resolve to one 8-byte source")
                edge = matching[0]
                source_offset = edge["source_offset"] + offset - edge["destination_offset"]
                source_state_id = self.bind(edge["value_id"], source_offset, before_operation)
                if self.bindings[source_state_id]["raw_center_bits"] != raw_bits:
                    _refuse(f"copy state center mismatch at {state_id}")
                form = self.forms[source_state_id]
                binding_kind = "COPY"
            elif producer_kind == "ARITHMETIC_RESULT":
                producer_ir_sequence = self.operation_index.get(value_id)
                if state_id not in self.forms:
                    _refuse(f"arithmetic result is used before execution: {state_id}")
                if before_operation is not None and producer_ir_sequence is not None and producer_ir_sequence >= before_operation:
                    _refuse(f"arithmetic result is a forward dependency: {state_id}")
                form = self.forms[state_id]
                binding_kind = "ARITHMETIC_RESULT"
            else:
                _refuse(f"unsupported state producer {producer_kind}")
            self.forms[state_id] = form
            self.bindings[state_id] = {
                "state_id": state_id,
                "value_id": value_id,
                "byte_offset": offset,
                "width": 8,
                "raw_center_bits": raw_bits,
                "form": form_document(form),
                "binding_kind": binding_kind,
                "source_state_id": source_state_id,
                "producer_ir_sequence": producer_ir_sequence,
                "phase": value["producer"]["phase"],
                "trace_sequence": value["producer"]["trace_sequence"],
            }
            self.order.append(state_id)
            return state_id
        finally:
            self.resolving.remove(state_id)

    def record_result(self, value_id: str, form: object, operation_index: int) -> str:
        state_id = _state_id(value_id, 0)
        if state_id in self.bindings:
            _refuse(f"arithmetic output state already exists: {state_id}")
        value = self.values[value_id]
        self.forms[state_id] = form
        self.bindings[state_id] = {
            "state_id": state_id,
            "value_id": value_id,
            "byte_offset": 0,
            "width": 8,
            "raw_center_bits": _lane_bits(value, 0),
            "form": form_document(form),
            "binding_kind": "ARITHMETIC_RESULT",
            "source_state_id": None,
            "producer_ir_sequence": operation_index,
            "phase": value["producer"]["phase"],
            "trace_sequence": value["producer"]["trace_sequence"],
        }
        self.order.append(state_id)
        return state_id

    def serialized(self) -> list[dict]:
        return sorted(
            self.bindings.values(),
            key=lambda item: (item["value_id"], item["byte_offset"]),
        )


def adapt(ir_path: Path, root: Path | None = None) -> dict:
    """Adapt one accepted Numeric IR document in memory without publishing files."""

    ir_path = Path(ir_path)
    document, raw_source = _read_json(ir_path)
    operations, values, by_id = _validate_document(document)
    pins = _load_pins()
    source_sha = hashlib.sha256(raw_source).hexdigest()
    accepted = pins["numeric_ir"].get(source_sha)
    if type(accepted) is not dict:
        _refuse("audited Numeric IR byte identity is not accepted")
    _exact_object(accepted, {"label", "normalized_numeric_sha256"}, "accepted Numeric IR pin")
    label = _string(accepted["label"], "accepted Numeric IR label")
    semantic_sha = _sha(accepted["normalized_numeric_sha256"], "accepted Numeric IR semantic hash")
    if document["source"]["normalized_numeric_sha256"] != semantic_sha:
        _refuse("audited Numeric IR semantic identity is not accepted")
    frozen = _verify_frozen(root, pins["frozen_v2_lf_sha256"])

    operation_index = {operation["output_value_id"]: index for index, operation in enumerate(operations)}
    execution = _Execution(by_id, operation_index)
    adapted_operations: list[dict] = []
    for index, operation in enumerate(operations):
        input0_state = execution.bind(operation["input0_value_id"], 0, index)
        input1_state = execution.bind(operation["input1_value_id"], 0, index)
        output_state = _state_id(operation["output_value_id"], 0)
        structure = [(
            KIND_MAP[operation["operation_kind"]],
            output_state,
            [input0_state, input1_state],
            None,
        )]
        regs = {
            input0_state: int(operation["input0_raw_bits"], 16),
            input1_state: int(operation["input1_raw_bits"], 16),
            output_state: int(operation["output_raw_bits"], 16),
        }
        inputs = {
            input0_state: execution.forms[input0_state],
            input1_state: execution.forms[input1_state],
        }
        try:
            result = v2_bound.step_forms(structure, regs, inputs)
        except Exception as exc:
            _refuse(f"frozen V2 operation refused at IR sequence {index}: {exc}")
        if type(result) is not dict or output_state not in result:
            _refuse(f"frozen V2 output linkage missing at IR sequence {index}")
        output_form = result[output_state]
        if (
            type(output_form) is not v2_bound.Form
            or type(output_form.coef) is not list
            or len(output_form.coef) != v2_bound.K
            or any(type(item) is not float or not math.isfinite(item) for item in output_form.coef)
            or type(output_form.box) is not float
            or not math.isfinite(output_form.box)
        ):
            _refuse(f"frozen V2 produced an invalid Form at IR sequence {index}")
        execution.record_result(operation["output_value_id"], output_form, index)
        adapted_operations.append({
            **operation,
            "v2_sequence": index,
            "v2_operation_kind": KIND_MAP[operation["operation_kind"]],
            "input0_state_id": input0_state,
            "input1_state_id": input1_state,
            "output_state_id": output_state,
            "input0_form": form_document(inputs[input0_state]),
            "input1_form": form_document(inputs[input1_state]),
            "output_form": form_document(output_form),
        })

    boundaries: list[dict] = []
    for value in values:
        producer = value["producer"]
        if producer["role"] != "boundary":
            continue
        state_ids = [execution.bind(value["value_id"], offset) for offset in range(0, value["width"], 8)]
        if value["width"] % 8:
            _refuse(f"boundary {value['value_id']} has an incomplete scalar lane")
        classification = "CAPTURED_STATE_HANDOFF" if value["producer_kind"] == "COPY_BITS" else "CAPTURED_INPUT_ROOT"
        boundaries.append({
            "value_id": value["value_id"],
            "phase": producer["phase"],
            "boundary": producer["boundary"],
            "producer_kind": value["producer_kind"],
            "classification": classification,
            "trace_sequence": producer["trace_sequence"],
            "state_ids": state_ids,
        })

    return {
        "schema": SCHEMA,
        "source": {
            "audited_input_label": label,
            "numeric_ir_sha256": source_sha,
            "normalized_numeric_sha256": semantic_sha,
            "numeric_ir_schema": document["schema"],
            "numeric_ir_source": document["source"],
            "frozen_v2": frozen,
        },
        "values": values,
        "boundaries": boundaries,
        "state_bindings": execution.serialized(),
        "operations": adapted_operations,
    }


def adapt_to_directory(ir_path: Path, out: Path, root: Path | None = None) -> dict:
    """Adapt first, then exclusively publish correspondence and completion marker."""

    output = adapt(ir_path, root=root)
    out = Path(out)
    out.mkdir(parents=False, exist_ok=False)
    try:
        correspondence_path = out / "correspondence.json"
        write_canonical(correspondence_path, output)
        correspondence_sha = hashlib.sha256(correspondence_path.read_bytes()).hexdigest()
        report = {
            "schema": REPORT_SCHEMA,
            "verdict": "ADAPTED",
            "correspondence_sha256": correspondence_sha,
            "source_numeric_ir_sha256": output["source"]["numeric_ir_sha256"],
            "source_normalized_numeric_sha256": output["source"]["normalized_numeric_sha256"],
            "operation_count": len(output["operations"]),
            "state_binding_count": len(output["state_bindings"]),
            "boundary_count": len(output["boundaries"]),
        }
        write_canonical(out / "completion_report.json", report)
    except Exception:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return output


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    try:
        output = adapt_to_directory(args.ir, args.out, root=args.root)
    except AdapterRefused as exc:
        print(json.dumps({"verdict": "REFUSED", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "verdict": "ADAPTED",
        "operation_count": len(output["operations"]),
        "output": str(args.out),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
