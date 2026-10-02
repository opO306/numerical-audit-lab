"""Independent raw-evidence checker for Numeric IR regular one-step v1.

This module intentionally does not import the Numeric IR producer.  It rebuilds
the value graph from captured machine state and independently decoded packaged
ELF bytes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from runtime_trace.correspondence import (
    AuditError,
    disassembly_for_rows,
    verify_flow,
    verify_linkage,
)
from runtime_trace.numeric_ir.normalization import normalize
from runtime_trace.numeric_ir.schema import SCHEMA, canonical_json
from runtime_trace.semantics import GPRS, Refused, decode


class IRCheckError(ValueError):
    """The raw source cannot independently justify the supplied Numeric IR."""


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
SOURCE_KEYS = {
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
ARITHMETIC_KINDS = {
    "addsd": "ADD_BINARY64",
    "subsd": "SUB_BINARY64",
    "mulsd": "MUL_BINARY64",
}
BOUNDARIES = ("q", "full_v", "latent", "gradient")
LINKED_BOUNDARIES = ("q", "full_v", "latent")
FULL_GPRS = {full for _, full in GPRS.values()}


def _fail(reason: str) -> None:
    raise IRCheckError(reason)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        _fail(reason)


def _mapping(value: object, reason: str) -> dict:
    if not isinstance(value, dict):
        _fail(reason)
    return value


def _sequence(value: object, reason: str) -> list:
    if not isinstance(value, list):
        _fail(reason)
    return value


def _integer(value: object, reason: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(reason)
    if minimum is not None and value < minimum:
        _fail(reason)
    return value


def _text(value: object, reason: str) -> str:
    if not isinstance(value, str):
        _fail(reason)
    return value


def _raw_bytes(value: object, width: int, reason: str) -> bytes:
    text = _text(value, reason)
    if not re.fullmatch(r"0x[0-9a-f]+", text) or len(text) != 2 + 2 * width:
        _fail(reason)
    return int(text, 16).to_bytes(width, "little")


def _nullable_integer(
    value: object, reason: str, *, minimum: int | None = None
) -> int | None:
    if value is None:
        return None
    return _integer(value, reason, minimum=minimum)


def _sha256_text(value: object, reason: str) -> str:
    text = _text(value, reason)
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", text)), reason)
    return text


def _source_paths(source: Path) -> tuple[Path, Path]:
    path = Path(source)
    if path.is_dir():
        trace = path / "trace.jsonl"
        capture = path / "capture.json"
    elif path.name == "trace.jsonl":
        trace, capture = path, path.with_name("capture.json")
    elif path.name == "capture.json":
        trace, capture = path.with_name("trace.jsonl"), path
    else:
        _fail("source must be an artifact directory, trace.jsonl, or capture.json")
    _require(trace.is_file(), "trace.jsonl missing")
    _require(capture.is_file(), "capture.json missing")
    return trace.resolve(), capture.resolve()


def _discover_root(trace: Path, root: Path | None) -> Path:
    if root is not None:
        candidate = Path(root).resolve()
        _require(
            (candidate / "runtime_trace/frozen_binaries/manifest.json").is_file(),
            "packaged module manifest missing",
        )
        return candidate
    for candidate in (trace.parent, *trace.parents):
        if (candidate / "runtime_trace/frozen_binaries/manifest.json").is_file():
            return candidate
    installed = Path(__file__).resolve().parents[2]
    _require(
        (installed / "runtime_trace/frozen_binaries/manifest.json").is_file(),
        "packaged module manifest missing",
    )
    return installed


def _load_raw(source: Path) -> tuple[Path, dict, list[dict], bytes]:
    trace_path, capture_path = _source_paths(source)
    try:
        capture_value = json.loads(capture_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"capture JSON invalid: {exc}")
    capture = _mapping(capture_value, "capture JSON object required")
    try:
        stream = trace_path.read_bytes()
    except OSError as exc:
        _fail(f"trace read failed: {exc}")
    rows: list[dict] = []
    for index, line in enumerate(stream.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            _fail(f"trace row {index} JSON invalid: {exc}")
        rows.append(_mapping(value, f"trace row {index} must be an object"))
    return trace_path, capture, rows, stream


def _validate_storage(storage: object, where: str) -> dict:
    result = _mapping(storage, f"{where} storage object")
    _require(set(result) == STORAGE_KEYS, f"{where} storage fields")
    _require(
        result.get("space")
        in {"buffer", "register", "stack", "elf", "memory-occurrence", "instruction", "control"},
        f"{where} storage space",
    )
    _text(result.get("name"), f"{where} storage name")
    _integer(result.get("byte_offset"), f"{where} storage byte offset")
    _integer(result.get("width"), f"{where} storage width", minimum=1)
    return result


def _validate_source_metadata(source: dict) -> None:
    _text(source.get("capture_schema"), "source capture schema")
    _sha256_text(source.get("trace_sha256"), "source trace SHA-256")
    _sha256_text(source.get("final_chain"), "source final chain")
    _integer(source.get("record_count"), "source record count integer", minimum=0)
    _integer(source.get("scalar_fp_count"), "source scalar count integer", minimum=0)
    module_sha256s = _sequence(source.get("module_sha256s"), "source module SHA-256 array")
    for index, digest in enumerate(module_sha256s):
        _sha256_text(digest, f"source module SHA-256 {index}")
    regions = _sequence(source.get("regions"), "source regions array")
    region_keys = {"phase", "start_seq", "end_seq", "start_state", "end_state", "mxcsr"}
    for index, region_value in enumerate(regions):
        region = _mapping(region_value, f"source region {index} object")
        _require(set(region) == region_keys, f"source region {index} fields")
        _require(region.get("phase") in {"init", "step"}, f"source region {index} phase")
        start = _integer(
            region.get("start_seq"), f"source region {index} start sequence integer", minimum=0
        )
        end = _integer(
            region.get("end_seq"), f"source region {index} end sequence integer", minimum=0
        )
        _require(start < end, f"source region {index} sequence range")
        _integer(region.get("mxcsr"), f"source region {index} MXCSR integer", minimum=0)
        for state_name in ("start_state", "end_state"):
            state = _mapping(region.get(state_name), f"source region {index} {state_name}")
            _require(set(state) == set(BOUNDARIES), f"source region {index} {state_name} fields")
            for name in BOUNDARIES:
                _raw_bytes(state[name], 16, f"source region {index} {state_name} {name}")
    _sha256_text(
        source.get("normalized_numeric_sha256"), "source normalized Numeric IR SHA-256"
    )
    diagnostic = _mapping(source.get("diagnostic"), "source diagnostic object")
    _require(
        set(diagnostic) == {"source_path", "runtime_addresses_excluded_from_normalization"},
        "source diagnostic fields",
    )
    _text(diagnostic.get("source_path"), "source diagnostic path")
    _require(
        diagnostic.get("runtime_addresses_excluded_from_normalization") is True,
        "runtime address normalization declaration",
    )


def _validate_producer(value_id: str, producer_kind: object, producer_value: object) -> dict:
    producer = _mapping(producer_value, f"value {value_id} producer object")
    role = _text(producer.get("role"), f"value {value_id} producer role")
    common = {"role", "trace_sequence", "operand_index", "phase"}
    if role == "boundary":
        _require(
            set(producer) == common | {"boundary"},
            f"value {value_id} boundary producer fields",
        )
        _require(
            producer_kind in {"LOAD_BITS", "COPY_BITS"},
            f"value {value_id} boundary producer kind",
        )
        _require(producer.get("phase") in {"init", "step"}, f"value {value_id} producer phase")
        _require(
            producer.get("boundary") in {*BOUNDARIES, "xmm0", "xmm1"},
            f"value {value_id} boundary name",
        )
        _require(producer.get("trace_sequence") is None, f"value {value_id} boundary trace null")
        _require(producer.get("operand_index") is None, f"value {value_id} boundary operand null")
        return producer
    if role == "constant_read":
        _require(
            set(producer) == common | {"module_sha256", "file_offset"},
            f"value {value_id} constant producer fields",
        )
        _require(producer_kind == "CONST_BITS", f"value {value_id} constant producer kind")
        _sha256_text(producer.get("module_sha256"), f"value {value_id} constant module SHA-256")
        _integer(producer.get("file_offset"), f"value {value_id} constant file offset", minimum=0)
    elif role == "arithmetic_result":
        _require(
            set(producer) == common | {"operation_kind"},
            f"value {value_id} arithmetic producer fields",
        )
        _require(
            producer_kind == "ARITHMETIC_RESULT",
            f"value {value_id} arithmetic producer kind",
        )
        _require(
            producer.get("operation_kind") in set(ARITHMETIC_KINDS.values()),
            f"value {value_id} arithmetic operation kind",
        )
    elif role in {
        "copy_result",
        "arithmetic_destination_pre_read",
        "arithmetic_source_read",
    }:
        _require(set(producer) == common, f"value {value_id} copy producer fields")
        _require(producer_kind == "COPY_BITS", f"value {value_id} copy producer kind")
    elif role in {
        "zero_extend",
        "zero_upper",
        "integer_zero",
        "zero_result",
        "instruction_zero",
    }:
        _require(set(producer) == common, f"value {value_id} zero producer fields")
        _require(producer_kind == "ZERO_BITS", f"value {value_id} zero producer kind")
    else:
        _fail(f"value {value_id} producer role")
    _require(producer.get("phase") in {"init", "step"}, f"value {value_id} producer phase")
    _integer(
        producer.get("trace_sequence"), f"value {value_id} producer trace sequence integer", minimum=0
    )
    _integer(
        producer.get("operand_index"), f"value {value_id} producer operand index integer", minimum=0
    )
    return producer


def _validate_ir_shape(ir: object) -> dict:
    document = _mapping(ir, "Numeric IR document must be an object")
    _require(
        set(document) == {"schema", "source", "operations", "values"},
        "Numeric IR top-level fields",
    )
    _require(document.get("schema") == SCHEMA, "Numeric IR schema")
    source = _mapping(document.get("source"), "Numeric IR source object")
    _require(set(source) == SOURCE_KEYS, "Numeric IR source fields")
    _validate_source_metadata(source)
    operations = _sequence(document.get("operations"), "Numeric IR operations array")
    values = _sequence(document.get("values"), "Numeric IR values array")
    for index, operation_value in enumerate(operations):
        operation = _mapping(operation_value, f"operation {index} object")
        _require(set(operation) == OPERATION_KEYS, f"operation {index} fields")
        _integer(operation.get("ir_sequence"), f"operation {index} IR sequence integer", minimum=0)
        _integer(
            operation.get("trace_sequence"),
            f"operation {index} trace sequence integer",
            minimum=0,
        )
        _sha256_text(operation.get("module_sha256"), f"operation {index} module SHA-256")
        elf_address = _integer(
            operation.get("elf_address"), f"operation {index} ELF address integer", minimum=0
        )
        _require(elf_address < 1 << 64, f"operation {index} ELF address range")
        instruction_bytes = _text(
            operation.get("instruction_bytes"), f"operation {index} instruction bytes"
        )
        _require(
            bool(re.fullmatch(r"[0-9a-f]{2,30}", instruction_bytes))
            and len(instruction_bytes) % 2 == 0,
            f"operation {index} instruction bytes",
        )
        _text(operation.get("opcode"), f"operation {index} opcode")
        _require(
            operation.get("operation_kind") in set(ARITHMETIC_KINDS.values()),
            f"operation {index} kind",
        )
        for field in ("input0_value_id", "input1_value_id", "output_value_id"):
            _text(operation.get(field), f"operation {index} {field}")
        for field in ("input0_raw_bits", "input1_raw_bits", "output_raw_bits"):
            _raw_bytes(operation.get(field), 8, f"operation {index} {field}")
        _integer(operation.get("mxcsr"), f"operation {index} MXCSR integer", minimum=0)
        _require(operation.get("phase") in {"init", "step"}, f"operation {index} phase")
        _integer(operation.get("step"), f"operation {index} step integer", minimum=0)
    seen_ids: set[str] = set()
    seen_producers: set[bytes] = set()
    value_by_id: dict[str, dict] = {}
    for index, value_value in enumerate(values):
        value = _mapping(value_value, f"value {index} object")
        _require(set(value) == VALUE_KEYS, f"value {index} fields")
        value_id = _text(value.get("value_id"), f"value {index} ID")
        _require(value_id not in seen_ids, f"duplicate value ID: {value_id}")
        seen_ids.add(value_id)
        producer = _validate_producer(value_id, value.get("producer_kind"), value.get("producer"))
        producer_identity = canonical_json(producer)
        _require(
            producer_identity not in seen_producers,
            f"duplicate producer identity: {value_id}",
        )
        seen_producers.add(producer_identity)
        width = _integer(value.get("width"), f"value {value_id} width", minimum=1)
        _raw_bytes(value.get("raw_bits"), width, f"value {value_id} raw bits")
        storage = _validate_storage(value.get("storage"), f"value {value_id}")
        _require(storage["width"] == width, f"value {value_id} storage width")
        slices = _sequence(value.get("source_slices"), f"value {value_id} source slices")
        if value.get("producer_kind") == "COPY_BITS":
            _require(bool(slices), f"COPY_BITS value {value_id} has no provenance edge")
        elif value.get("producer_kind") in {
            "LOAD_BITS",
            "CONST_BITS",
            "ZERO_BITS",
            "ARITHMETIC_RESULT",
        }:
            _require(not slices, f"non-copy value {value_id} has source slices")
        else:
            _fail(f"value {value_id} producer kind")
        for slice_index, slice_value in enumerate(slices):
            part = _mapping(slice_value, f"value {value_id} slice {slice_index} object")
            _require(set(part) == SLICE_KEYS, f"value {value_id} slice {slice_index} fields")
            _text(part.get("value_id"), f"value {value_id} slice source ID")
            source_offset = _integer(
                part.get("source_offset"), f"value {value_id} slice source offset", minimum=0
            )
            destination_offset = _integer(
                part.get("destination_offset"),
                f"value {value_id} slice destination offset",
                minimum=0,
            )
            part_width = _integer(
                part.get("width"), f"value {value_id} slice width", minimum=1
            )
            slice_trace = _nullable_integer(
                part.get("trace_sequence"),
                f"value {value_id} slice trace sequence integer or null",
                minimum=0,
            )
            slice_operand = _nullable_integer(
                part.get("source_operand_index"),
                f"value {value_id} slice operand index integer or null",
                minimum=0,
            )
            _require(
                (slice_trace is None) == (slice_operand is None),
                f"value {value_id} slice occurrence null pairing",
            )
            _require(
                destination_offset + part_width <= width,
                f"value {value_id} slice destination range",
            )
            source_storage = _validate_storage(
                part.get("source_storage"), f"value {value_id} slice source"
            )
            destination_storage = _validate_storage(
                part.get("destination_storage"), f"value {value_id} slice destination"
            )
            _require(source_storage["width"] == part_width, f"value {value_id} slice source width")
            _require(
                destination_storage["width"] == part_width,
                f"value {value_id} slice destination width",
            )
            _require(source_offset >= 0, f"value {value_id} slice source range")
        value_by_id[value_id] = value

    # Validate the submitted graph before comparing it with reconstruction so
    # dangling, cyclic, and byte-lane attacks have dedicated failure reasons.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(value_id: str) -> None:
        if value_id in visiting:
            _fail(f"provenance cycle at {value_id}")
        if value_id in visited:
            return
        visiting.add(value_id)
        value = value_by_id[value_id]
        destination_bytes = _raw_bytes(value["raw_bits"], value["width"], "value raw bits")
        covered: set[int] = set()
        for part in value["source_slices"]:
            source_id = part["value_id"]
            _require(source_id in value_by_id, f"dangling provenance edge: {source_id}")
            source = value_by_id[source_id]
            source_offset = part["source_offset"]
            destination_offset = part["destination_offset"]
            width = part["width"]
            _require(
                source_offset + width <= source["width"],
                f"provenance source byte range: {value_id}",
            )
            lanes = set(range(destination_offset, destination_offset + width))
            _require(not covered.intersection(lanes), f"overlapping provenance slices: {value_id}")
            covered.update(lanes)
            source_bytes = _raw_bytes(source["raw_bits"], source["width"], "source raw bits")
            _require(
                destination_bytes[destination_offset : destination_offset + width]
                == source_bytes[source_offset : source_offset + width],
                f"provenance byte mismatch: {value_id}",
            )
            visit(source_id)
        visiting.remove(value_id)
        visited.add(value_id)

    for value_id in value_by_id:
        visit(value_id)

    used_ids: set[str] = set()
    for index, operation in enumerate(operations):
        for field in ("input0_value_id", "input1_value_id", "output_value_id"):
            value_id = _text(operation.get(field), f"operation {index} {field}")
            _require(value_id in value_by_id, f"operation {index} dangling value ID: {value_id}")
            used_ids.add(value_id)
    return document


def _validate_capture_and_rows(capture: dict, rows: list[dict], stream: bytes) -> None:
    _require(capture.get("schema") == "gala-regular-1step-runtime-trace-v1", "capture schema")
    _require(capture.get("verdict") == "CAPTURED", "capture is not complete")
    record_count = _integer(capture.get("record_count"), "capture record count", minimum=0)
    _require(len(rows) == record_count, "record count / missing occurrence")
    _require(
        hashlib.sha256(stream).hexdigest() == capture.get("trace_sha256"),
        "trace raw hash mismatch",
    )
    chain = "0" * 64
    for index, row in enumerate(rows):
        required = {
            "seq",
            "phase",
            "step",
            "ptid",
            "module_path",
            "module_sha256",
            "module_load_base",
            "runtime_pc",
            "elf_address",
            "elf_file_offset",
            "mapping",
            "bytes",
            "instruction",
            "opcode",
            "kind",
            "operands",
            "pre",
            "post",
            "post_pc",
            "chain",
        }
        _require(required.issubset(row), f"trace row {index} missing fields")
        _integer(row.get("seq"), f"trace row {index} sequence", minimum=0)
        _text(row.get("phase"), f"trace row {index} phase")
        _integer(row.get("step"), f"trace row {index} step", minimum=0)
        for field in ("module_load_base", "runtime_pc", "elf_address", "elf_file_offset", "post_pc"):
            number = _integer(row.get(field), f"trace row {index} {field}", minimum=0)
            _require(number < 1 << 64, f"trace row {index} {field} range")
        _text(row.get("module_path"), f"trace row {index} module path")
        _require(
            bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("module_sha256", "")))),
            f"trace row {index} module SHA-256",
        )
        encoded_bytes = _text(row.get("bytes"), f"trace row {index} instruction bytes")
        _require(
            bool(re.fullmatch(r"[0-9a-f]{2,30}", encoded_bytes)) and len(encoded_bytes) % 2 == 0,
            f"trace row {index} instruction bytes",
        )
        _text(row.get("instruction"), f"trace row {index} instruction")
        _text(row.get("opcode"), f"trace row {index} opcode")
        _text(row.get("kind"), f"trace row {index} kind")
        for context_name in ("pre", "post"):
            context = _mapping(row.get(context_name), f"trace row {index} {context_name} context")
            gpr = _mapping(context.get("gpr"), f"trace row {index} {context_name} GPR context")
            missing = sorted(FULL_GPRS.difference(gpr))
            _require(
                not missing,
                f"trace row {index} {context_name} missing captured canonical GPRs: {','.join(missing)}",
            )
            for name in FULL_GPRS:
                _raw_bytes(gpr[name], 8, f"trace row {index} {context_name} GPR {name}")
            xmm = _mapping(context.get("xmm"), f"trace row {index} {context_name} XMM context")
            _mapping(
                context.get("extra_vectors"),
                f"trace row {index} {context_name} extra vector context",
            )
            _integer(context.get("mxcsr"), f"trace row {index} {context_name} MXCSR", minimum=0)
            _integer(context.get("eflags"), f"trace row {index} {context_name} flags", minimum=0)
            for name, text in xmm.items():
                _require(bool(re.fullmatch(r"xmm\d+", name)), f"trace row {index} XMM name")
                _raw_bytes(text, 16, f"trace row {index} {context_name} vector {name}")
        operands = _sequence(row.get("operands"), f"trace row {index} operands")
        for operand_index, operand_value in enumerate(operands):
            operand = _mapping(operand_value, f"trace row {index} operand {operand_index}")
            kind = operand.get("kind")
            _require(
                kind in {"register", "memory", "immediate", "control", "code_address"},
                f"trace row {index} operand kind",
            )
            width = _integer(
                operand.get("width"), f"trace row {index} operand {operand_index} width", minimum=1
            )
            _require(width <= 64, f"trace row {index} operand {operand_index} width range")
            _raw_bytes(
                operand.get("raw_bits"), width, f"trace row {index} operand {operand_index} raw bits"
            )
            if kind == "register":
                register = _text(
                    operand.get("register"), f"trace row {index} operand {operand_index} register"
                )
                if register in GPRS:
                    full = GPRS[register][1]
                    for context_name in ("pre", "post"):
                        _require(
                            full in row[context_name]["gpr"],
                            f"trace row {index} {context_name} missing canonical register {full}",
                        )
                else:
                    match = re.fullmatch(r"(xmm|ymm|zmm)(\d+)", register)
                    _require(match is not None, f"trace row {index} unknown register {register}")
                    for context_name in ("pre", "post"):
                        context = row[context_name]
                        _require(
                            register in context["xmm"] or register in context["extra_vectors"],
                            f"trace row {index} {context_name} missing vector register {register}",
                        )
            elif kind == "memory":
                address = _integer(
                    operand.get("address"), f"trace row {index} operand {operand_index} address", minimum=0
                )
                _require(address + width <= 1 << 64, f"trace row {index} memory range")
        unsigned = {key: value for key, value in row.items() if key != "chain"}
        encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        chain = hashlib.sha256(bytes.fromhex(chain) + encoded).hexdigest()
        _require(row.get("chain") == chain, f"trace hash chain mismatch at row {index}")
    _require(capture.get("final_chain") == chain, "capture final chain mismatch")
    scalar_count = sum(row["kind"] in {"ADD", "SUB", "MUL"} for row in rows)
    captured_scalar_count = _integer(
        capture.get("scalar_fp_count"), "capture scalar count integer", minimum=0
    )
    _require(captured_scalar_count == scalar_count, "capture scalar count metadata")
    histogram = _mapping(capture.get("opcode_histogram"), "capture opcode histogram object")
    for opcode, count in histogram.items():
        _text(opcode, "capture opcode histogram key")
        _integer(count, f"capture opcode histogram count for {opcode}", minimum=0)
    _require(
        canonical_json(histogram)
        == canonical_json(dict(Counter(row["opcode"] for row in rows))),
        "capture opcode histogram metadata",
    )

    regions = _sequence(capture.get("regions"), "capture regions array")
    _require(len(regions) == 2, "capture requires exactly two regions")
    for index, region_value in enumerate(regions):
        region = _mapping(region_value, f"region {index} object")
        _require(region.get("phase") in {"init", "step"}, f"region {index} phase")
        start = _integer(region.get("start_seq"), f"region {index} start sequence")
        end = _integer(region.get("end_seq"), f"region {index} end sequence")
        _require(start < end <= len(rows), f"region {index} sequence range")
        pointers = _mapping(region.get("pointers"), f"region {index} pointers")
        _require(set(pointers) == set(BOUNDARIES), f"region {index} boundary pointers")
        intervals = []
        for name in BOUNDARIES:
            pointer = _integer(pointers[name], f"region {index} boundary pointer range", minimum=0)
            _require(pointer + 16 <= 1 << 64, f"region {index} boundary pointer range")
            intervals.append((pointer, pointer + 16, name))
        for left_index, left in enumerate(intervals):
            for right in intervals[left_index + 1 :]:
                _require(
                    left[1] <= right[0] or right[1] <= left[0],
                    f"region {index} ambiguous boundary memory alias: {left[2]}/{right[2]}",
                )
        for state_name in ("start_state", "end_state"):
            state = _mapping(region.get(state_name), f"region {index} {state_name}")
            _require(set(state) == set(BOUNDARIES), f"region {index} {state_name} fields")
            for name in BOUNDARIES:
                _raw_bytes(state[name], 16, f"region {index} {state_name} {name}")
        region_mxcsr = _integer(region.get("mxcsr"), f"region {index} MXCSR", minimum=0)
        first = rows[start]
        _require(first["pre"]["mxcsr"] == region_mxcsr, f"region {index} MXCSR linkage")
        for register in ("rcx", "r8", "r9", "rsp"):
            _require(
                register in first["pre"]["gpr"],
                f"region {region['phase']} entry missing ABI register {register}",
            )
        for register in ("xmm0", "xmm1"):
            _require(
                register in first["pre"]["xmm"],
                f"region {region['phase']} entry missing XMM boundary {register}",
            )


def _canonical_register(name: str) -> str:
    if name in GPRS:
        return GPRS[name][1]
    match = re.fullmatch(r"(?:xmm|ymm|zmm)(\d+)", name)
    if match:
        return f"v{match.group(1)}"
    _fail(f"unknown register in reconstruction: {name}")


def _operand_keys(operand: dict) -> list[tuple]:
    if operand["kind"] == "memory":
        return [("m", operand["address"] + offset) for offset in range(operand["width"])]
    if operand["kind"] == "register":
        name = _canonical_register(operand["register"])
        return [("r", name, offset) for offset in range(operand["width"])]
    return []


def _buffer_match(region: dict, address: int, width: int) -> tuple[str, int] | None:
    requested = range(address, address + width)
    intersections: list[tuple[str, int, bool]] = []
    for name, base in region["pointers"].items():
        intersects = max(address, base) < min(address + width, base + 16)
        if intersects:
            intersections.append((name, address - base, set(requested).issubset(range(base, base + 16))))
    if not intersections:
        return None
    _require(
        len(intersections) == 1 and intersections[0][2],
        "ambiguous boundary memory alias",
    )
    return intersections[0][0], intersections[0][1]


def _storage_for_operand(
    operand: dict,
    region: dict,
    sequence: int,
    operand_index: int,
    stack_bytes: set[int],
) -> dict:
    width = operand["width"]
    if operand["kind"] == "register":
        return {
            "space": "register",
            "name": _canonical_register(operand["register"]),
            "byte_offset": 0,
            "width": width,
        }
    if operand["kind"] == "memory":
        address = operand["address"]
        boundary = _buffer_match(region, address, width)
        if boundary is not None:
            return {
                "space": "buffer",
                "name": boundary[0],
                "byte_offset": boundary[1],
                "width": width,
            }
        if all(address + offset in stack_bytes for offset in range(width)):
            entry_rsp = int(region["_entry_rsp"], 16)
            return {
                "space": "stack",
                "name": region["phase"],
                "byte_offset": address - entry_rsp,
                "width": width,
            }
        return {
            "space": "memory-occurrence",
            "name": f"{region['phase']}:r{sequence}:o{operand_index}",
            "byte_offset": 0,
            "width": width,
        }
    if operand["kind"] == "immediate":
        return {
            "space": "instruction",
            "name": f"r{sequence}:o{operand_index}",
            "byte_offset": 0,
            "width": width,
        }
    return {
        "space": "control",
        "name": f"r{sequence}:o{operand_index}",
        "byte_offset": 0,
        "width": width,
    }


def _substorage(storage: dict, offset: int, width: int) -> dict:
    return {
        "space": storage["space"],
        "name": storage["name"],
        "byte_offset": storage["byte_offset"] + offset,
        "width": width,
    }


def _zero_bits(width: int) -> str:
    return "0x" + "00" * width


class _Reconstruction:
    def __init__(self, rows: list[dict], capture: dict, decoded: dict):
        self.rows = rows
        self.capture = capture
        self.decoded = decoded
        self.values: list[dict] = []
        self.value_by_id: dict[str, dict] = {}
        self.operations: list[dict] = []
        self.state: dict[tuple, tuple[str, int]] = {}
        self.init_endpoint: dict[tuple, tuple[str, int]] = {}

    def add_value(self, value: dict) -> None:
        value_id = value["value_id"]
        _require(value_id not in self.value_by_id, f"reconstruction duplicate value: {value_id}")
        self.values.append(value)
        self.value_by_id[value_id] = value

    def refs_for(self, operand: dict) -> list[tuple[str, int] | None]:
        return [self.state.get(key) for key in _operand_keys(operand)]

    def slices_for(
        self,
        refs: list[tuple[str, int] | None],
        destination_storage: dict,
        sequence: int | None,
        operand_index: int | None,
    ) -> list[dict]:
        result: list[dict] = []
        index = 0
        while index < len(refs):
            ref = refs[index]
            if ref is None:
                index += 1
                continue
            value_id, source_offset = ref
            end = index + 1
            while (
                end < len(refs)
                and refs[end] is not None
                and refs[end][0] == value_id
                and refs[end][1] == source_offset + end - index
            ):
                end += 1
            width = end - index
            source_value = self.value_by_id[value_id]
            result.append(
                {
                    "value_id": value_id,
                    "source_offset": source_offset,
                    "destination_offset": index,
                    "width": width,
                    "trace_sequence": sequence,
                    "source_operand_index": operand_index,
                    "source_storage": _substorage(source_value["storage"], source_offset, width),
                    "destination_storage": _substorage(destination_storage, index, width),
                }
            )
            index = end
        return result

    def assign(self, operand: dict, value_id: str, known_offsets: Iterable[int]) -> None:
        keys = _operand_keys(operand)
        known = set(known_offsets)
        for offset, key in enumerate(keys):
            if offset in known:
                self.state[key] = (value_id, offset)
            else:
                self.state.pop(key, None)

    def boundary_value(self, region: dict, name: str, kind: str, refs=None) -> None:
        phase = region["phase"]
        value_id = f"v:boundary:{phase}:{name}"
        width = 8 if name in {"xmm0", "xmm1"} else 16
        if name.startswith("xmm"):
            raw_bits = region["_first"]["pre"]["xmm"][name]
            raw_bits = "0x" + raw_bits[-16:]
            storage = {
                "space": "register",
                "name": f"v{name[3:]}",
                "byte_offset": 0,
                "width": width,
            }
            keys = [("r", f"v{name[3:]}", offset) for offset in range(width)]
        else:
            raw_bits = region["start_state"][name]
            storage = {"space": "buffer", "name": name, "byte_offset": 0, "width": width}
            base = region["pointers"][name]
            keys = [("m", base + offset) for offset in range(width)]
        slices = self.slices_for(refs, storage, None, None) if refs is not None else []
        value = {
            "value_id": value_id,
            "producer_kind": kind,
            "raw_bits": raw_bits,
            "width": width,
            "producer": {
                "role": "boundary",
                "phase": phase,
                "boundary": name,
                "trace_sequence": None,
                "operand_index": None,
            },
            "storage": storage,
            "source_slices": slices,
        }
        self.add_value(value)
        for offset, key in enumerate(keys):
            self.state[key] = (value_id, offset)

    def stack_bytes(self, subset: list[dict]) -> set[int]:
        result: set[int] = set()
        for row in subset:
            reference = self.decoded[row["module_path"], row["elf_address"]]
            uses_rsp = "%rsp" in reference or row["kind"] == "STACK"
            if not uses_rsp:
                continue
            for operand in row["operands"]:
                if operand["kind"] == "memory":
                    result.update(range(operand["address"], operand["address"] + operand["width"]))
        return result

    def add_copy(
        self,
        row: dict,
        region: dict,
        stack_bytes: set[int],
        source: dict,
        destination: dict,
        source_index: int,
        destination_index: int,
    ) -> None:
        seq = row["seq"]
        destination_storage = _storage_for_operand(
            destination, region, seq, destination_index, stack_bytes
        )
        refs: list[tuple[str, int] | None]
        if source["kind"] == "immediate":
            _require(int(source["raw_bits"], 16) == 0, f"unsupported nonzero immediate at row {seq}")
            literal_id = f"v:r{seq}:o{source_index}:literal-zero"
            literal_storage = _storage_for_operand(source, region, seq, source_index, stack_bytes)
            self.add_value(
                {
                    "value_id": literal_id,
                    "producer_kind": "ZERO_BITS",
                    "raw_bits": source["raw_bits"],
                    "width": source["width"],
                    "producer": {
                        "role": "instruction_zero",
                        "trace_sequence": seq,
                        "operand_index": source_index,
                        "phase": row["phase"],
                    },
                    "storage": literal_storage,
                    "source_slices": [],
                }
            )
            refs = [(literal_id, offset) for offset in range(source["width"])]
        elif source.get("constant_origin") is not None:
            constant = self.add_constant(row, source, source_index)
            refs = [(constant, offset) for offset in range(source["width"])]
        else:
            refs = self.refs_for(source)
        slices = self.slices_for(refs, destination_storage, seq, source_index)
        known_offsets: list[int] = []
        if slices:
            value_id = f"v:r{seq}:copy"
            self.add_value(
                {
                    "value_id": value_id,
                    "producer_kind": "COPY_BITS",
                    "raw_bits": row["result_bits"],
                    "width": destination["width"],
                    "producer": {
                        "role": "copy_result",
                        "trace_sequence": seq,
                        "operand_index": destination_index,
                        "phase": row["phase"],
                    },
                    "storage": destination_storage,
                    "source_slices": slices,
                }
            )
            for part in slices:
                known_offsets.extend(
                    range(part["destination_offset"], part["destination_offset"] + part["width"])
                )
            self.assign(destination, value_id, known_offsets)
        else:
            for key in _operand_keys(destination):
                self.state.pop(key, None)

    def add_constant(self, row: dict, operand: dict, operand_index: int) -> str:
        origin = _mapping(operand.get("constant_origin"), f"row {row['seq']} constant origin")
        digest = _text(origin.get("module_sha256"), f"row {row['seq']} constant module")
        offset = _integer(origin.get("file_offset"), f"row {row['seq']} constant offset", minimum=0)
        value_id = f"v:r{row['seq']}:o{operand_index}:const"
        self.add_value(
            {
                "value_id": value_id,
                "producer_kind": "CONST_BITS",
                "raw_bits": operand["raw_bits"],
                "width": operand["width"],
                "producer": {
                    "role": "constant_read",
                    "trace_sequence": row["seq"],
                    "operand_index": operand_index,
                    "phase": row["phase"],
                    "module_sha256": digest,
                    "file_offset": offset,
                },
                "storage": {
                    "space": "elf",
                    "name": digest,
                    "byte_offset": offset,
                    "width": operand["width"],
                },
                "source_slices": [],
            }
        )
        return value_id

    def add_zero_extend(self, row: dict, destination: dict, destination_index: int) -> None:
        if destination["kind"] != "register" or destination["width"] != 4:
            return
        name = _canonical_register(destination["register"])
        if name.startswith("v"):
            return
        value_id = f"v:r{row['seq']}:zero-extend"
        self.add_value(
            {
                "value_id": value_id,
                "producer_kind": "ZERO_BITS",
                "raw_bits": _zero_bits(4),
                "width": 4,
                "producer": {
                    "role": "zero_extend",
                    "trace_sequence": row["seq"],
                    "operand_index": destination_index,
                    "phase": row["phase"],
                },
                "storage": {
                    "space": "register",
                    "name": name,
                    "byte_offset": 4,
                    "width": 4,
                },
                "source_slices": [],
            }
        )
        for offset in range(4):
            self.state[("r", name, 4 + offset)] = (value_id, offset)

    def add_zero_upper(self, row: dict, destination: dict, destination_index: int, opcode: str) -> None:
        if destination["kind"] != "register":
            return
        name = _canonical_register(destination["register"])
        if not name.startswith("v"):
            return
        source = row["operands"][0]
        should_zero = opcode in {"movq", "vmovd"} or (
            opcode == "movsd" and source["kind"] == "memory"
        )
        if not should_zero or destination["width"] >= 16:
            return
        width = 16 - destination["width"]
        value_id = f"v:r{row['seq']}:zero-upper"
        self.add_value(
            {
                "value_id": value_id,
                "producer_kind": "ZERO_BITS",
                "raw_bits": _zero_bits(width),
                "width": width,
                "producer": {
                    "role": "zero_upper",
                    "trace_sequence": row["seq"],
                    "operand_index": destination_index,
                    "phase": row["phase"],
                },
                "storage": {
                    "space": "register",
                    "name": name,
                    "byte_offset": destination["width"],
                    "width": width,
                },
                "source_slices": [],
            }
        )
        for offset in range(width):
            self.state[("r", name, destination["width"] + offset)] = (value_id, offset)

    def add_integer_zero(self, row: dict, destination: dict, destination_index: int) -> None:
        name = _canonical_register(destination["register"])
        width = destination["width"]
        value_id = f"v:r{row['seq']}:integer-zero"
        self.add_value(
            {
                "value_id": value_id,
                "producer_kind": "ZERO_BITS",
                "raw_bits": _zero_bits(width),
                "width": width,
                "producer": {
                    "role": "integer_zero",
                    "trace_sequence": row["seq"],
                    "operand_index": destination_index,
                    "phase": row["phase"],
                },
                "storage": {"space": "register", "name": name, "byte_offset": 0, "width": width},
                "source_slices": [],
            }
        )
        for offset in range(8):
            self.state.pop(("r", name, offset), None)
        for offset in range(width):
            self.state[("r", name, offset)] = (value_id, offset)

    def add_vector_zero(self, row: dict, destination: dict, destination_index: int) -> None:
        name = _canonical_register(destination["register"])
        width = destination["width"]
        value_id = f"v:r{row['seq']}:zero"
        self.add_value(
            {
                "value_id": value_id,
                "producer_kind": "ZERO_BITS",
                "raw_bits": row["result_bits"],
                "width": width,
                "producer": {
                    "role": "zero_result",
                    "trace_sequence": row["seq"],
                    "operand_index": destination_index,
                    "phase": row["phase"],
                },
                "storage": {"space": "register", "name": name, "byte_offset": 0, "width": width},
                "source_slices": [],
            }
        )
        self.assign(destination, value_id, range(width))

    def add_arithmetic(self, row: dict, region: dict, stack_bytes: set[int], opcode: str) -> None:
        source, destination = row["operands"]
        _require(source["width"] == destination["width"] == 8, f"row {row['seq']} scalar width")
        operation_kind = ARITHMETIC_KINDS[opcode]
        input_ids: list[str] = []
        for operand_index, (operand, role, suffix) in enumerate(
            (
                (destination, "arithmetic_destination_pre_read", "arithmetic-destination-pre-read"),
                (source, "arithmetic_source_read", "arithmetic-source-read"),
            )
        ):
            actual_index = 1 if operand is destination else 0
            if operand.get("constant_origin") is not None:
                value_id = self.add_constant(row, operand, actual_index)
            else:
                refs = self.refs_for(operand)
                _require(
                    refs and all(ref is not None for ref in refs),
                    f"row {row['seq']} missing numerical provenance",
                )
                storage = _storage_for_operand(operand, region, row["seq"], actual_index, stack_bytes)
                value_id = f"v:r{row['seq']}:{suffix}"
                slices = self.slices_for(refs, storage, row["seq"], actual_index)
                self.add_value(
                    {
                        "value_id": value_id,
                        "producer_kind": "COPY_BITS",
                        "raw_bits": operand["raw_bits"],
                        "width": 8,
                        "producer": {
                            "role": role,
                            "trace_sequence": row["seq"],
                            "operand_index": actual_index,
                            "phase": row["phase"],
                        },
                        "storage": storage,
                        "source_slices": slices,
                    }
                )
            input_ids.append(value_id)
        output_id = f"v:r{row['seq']}:result"
        output_storage = _storage_for_operand(destination, region, row["seq"], 1, stack_bytes)
        self.add_value(
            {
                "value_id": output_id,
                "producer_kind": "ARITHMETIC_RESULT",
                "raw_bits": row["result_bits"],
                "width": 8,
                "producer": {
                    "role": "arithmetic_result",
                    "trace_sequence": row["seq"],
                    "operand_index": 1,
                    "phase": row["phase"],
                    "operation_kind": operation_kind,
                },
                "storage": output_storage,
                "source_slices": [],
            }
        )
        self.assign(destination, output_id, range(8))
        self.operations.append(
            {
                "ir_sequence": len(self.operations),
                "trace_sequence": row["seq"],
                "module_sha256": row["module_sha256"],
                "elf_address": row["elf_address"],
                "instruction_bytes": row["bytes"],
                "opcode": opcode,
                "operation_kind": operation_kind,
                "input0_value_id": input_ids[0],
                "input1_value_id": input_ids[1],
                "output_value_id": output_id,
                "input0_raw_bits": destination["raw_bits"],
                "input1_raw_bits": source["raw_bits"],
                "output_raw_bits": row["result_bits"],
                "mxcsr": row["pre"]["mxcsr"],
                "phase": row["phase"],
                "step": row["step"],
            }
        )

    def invalidate_unhandled_changes(self, row: dict, handled: set[tuple]) -> None:
        for name in FULL_GPRS:
            if row["pre"]["gpr"][name] != row["post"]["gpr"][name] and not any(
                ("r", name, offset) in handled for offset in range(8)
            ):
                for offset in range(8):
                    self.state.pop(("r", name, offset), None)
        vector_names = set(row["pre"]["xmm"]).intersection(row["post"]["xmm"])
        for xmm in vector_names:
            name = _canonical_register(xmm)
            if row["pre"]["xmm"][xmm] != row["post"]["xmm"][xmm] and not any(
                ("r", name, offset) in handled for offset in range(16)
            ):
                for offset in range(16):
                    self.state.pop(("r", name, offset), None)

    def run(self) -> tuple[list[dict], list[dict]]:
        for region_index, original_region in enumerate(self.capture["regions"]):
            region = dict(original_region)
            subset = self.rows[region["start_seq"] : region["end_seq"]]
            region["_first"] = subset[0]
            region["_entry_rsp"] = subset[0]["pre"]["gpr"]["rsp"]
            stack_bytes = self.stack_bytes(subset)
            self.state = {}
            if region_index == 0:
                for name in BOUNDARIES:
                    self.boundary_value(region, name, "LOAD_BITS")
            else:
                _require(bool(self.init_endpoint), "missing init endpoint provenance")
                for name in LINKED_BOUNDARIES:
                    base = original_region["pointers"][name]
                    refs = [self.init_endpoint.get(("m", base + offset)) for offset in range(16)]
                    _require(all(ref is not None for ref in refs), f"missing init endpoint for {name}")
                    self.boundary_value(region, name, "COPY_BITS", refs)
                self.boundary_value(region, "gradient", "LOAD_BITS")
            for name in ("xmm0", "xmm1"):
                self.boundary_value(region, name, "LOAD_BITS")

            for row in subset:
                reference = self.decoded[row["module_path"], row["elf_address"]]
                try:
                    opcode, decoded_kind, _args, _width = decode(reference)
                except Refused as exc:
                    _fail(f"row {row['seq']} independent decode refused: {exc}")
                _require(
                    row["kind"] == decoded_kind,
                    f"row {row['seq']} recorded kind disagrees with decoded kind",
                )
                handled: set[tuple] = set()
                if decoded_kind in {"ADD", "SUB", "MUL"}:
                    _require(opcode in ARITHMETIC_KINDS, f"row {row['seq']} unsupported scalar opcode")
                    self.add_arithmetic(row, region, stack_bytes, opcode)
                    handled.update(_operand_keys(row["operands"][1]))
                elif decoded_kind in {"MOVE", "STACK"}:
                    _require(len(row["operands"]) == 2, f"row {row['seq']} copy operand count")
                    source, destination = row["operands"]
                    self.add_copy(row, region, stack_bytes, source, destination, 0, 1)
                    self.add_zero_extend(row, destination, 1)
                    self.add_zero_upper(row, destination, 1, opcode)
                    handled.update(_operand_keys(destination))
                    if destination["kind"] == "register" and destination["width"] == 4:
                        name = _canonical_register(destination["register"])
                        handled.update(("r", name, offset) for offset in range(4, 8))
                    if destination["kind"] == "register" and _canonical_register(
                        destination["register"]
                    ).startswith("v"):
                        handled.update(("r", _canonical_register(destination["register"]), offset) for offset in range(16))
                elif decoded_kind in {"ZERO", "ZERO_FILL"}:
                    destination = row["operands"][-1]
                    self.add_vector_zero(row, destination, len(row["operands"]) - 1)
                    handled.update(_operand_keys(destination))
                elif opcode == "xor" and len(row["operands"]) == 2:
                    first, destination = row["operands"]
                    if (
                        first["kind"] == destination["kind"] == "register"
                        and first["register"] == destination["register"]
                    ):
                        self.add_integer_zero(row, destination, 1)
                        handled.update(_operand_keys(destination))
                self.invalidate_unhandled_changes(row, handled)

            if region_index == 0:
                self.init_endpoint = dict(self.state)
            for name, base in original_region["pointers"].items():
                expected = _raw_bytes(original_region["end_state"][name], 16, "region endpoint")
                for offset, byte in enumerate(expected):
                    ref = self.state.get(("m", base + offset))
                    _require(ref is not None, f"buffer endpoint provenance missing: {region['phase']} {name}")
                    producer = self.value_by_id[ref[0]]
                    actual = _raw_bytes(producer["raw_bits"], producer["width"], "producer bits")[
                        ref[1]
                    ]
                    _require(actual == byte, f"buffer endpoint bits mismatch: {region['phase']} {name}")
        return self.operations, self.values


def _expected_source(capture: dict, rows: list[dict], stream: bytes, document: dict) -> dict:
    regions = []
    for region in capture["regions"]:
        regions.append(
            {
                "phase": region["phase"],
                "start_seq": region["start_seq"],
                "end_seq": region["end_seq"],
                "start_state": region["start_state"],
                "end_state": region["end_state"],
                "mxcsr": region["mxcsr"],
            }
        )
    return {
        "capture_schema": capture["schema"],
        "trace_sha256": hashlib.sha256(stream).hexdigest(),
        "final_chain": capture["final_chain"],
        "record_count": len(rows),
        "scalar_fp_count": sum(row["kind"] in {"ADD", "SUB", "MUL"} for row in rows),
        "module_sha256s": sorted({row["module_sha256"] for row in rows}),
        "regions": regions,
        "normalized_numeric_sha256": hashlib.sha256(canonical_json(normalize(document))).hexdigest(),
    }


def check(ir: dict, source: Path, root: Path | None = None) -> dict:
    """Independently validate *ir* against an immutable raw capture."""

    document = _validate_ir_shape(ir)
    trace_path, capture, rows, stream = _load_raw(Path(source))
    _validate_capture_and_rows(capture, rows, stream)
    repo_root = _discover_root(trace_path, root)
    try:
        verify_linkage(rows, capture["regions"], capture["record_count"])
        decoded = disassembly_for_rows(rows, capture["modules"], root=repo_root)
        verify_flow(rows, capture, decoded, root=repo_root)
    except (AuditError, Refused, OSError, KeyError, TypeError, ValueError) as exc:
        _fail(f"raw evidence validation failed: {exc}")

    reconstruction = _Reconstruction(rows, capture, decoded)
    operations, values = reconstruction.run()
    _require(
        canonical_json(document["operations"]) == canonical_json(operations),
        "operation reconstruction mismatch (coverage/order/identity/kind/bits/value IDs)",
    )
    expected_ids = {value["value_id"] for value in values}
    actual_ids = {value["value_id"] for value in document["values"]}
    extra = sorted(actual_ids - expected_ids)
    missing = sorted(expected_ids - actual_ids)
    _require(not extra, f"unregistered extra value: {extra[0] if extra else ''}")
    _require(not missing, f"missing reconstructed value: {missing[0] if missing else ''}")
    _require(
        canonical_json(document["values"]) == canonical_json(values),
        "value/provenance reconstruction mismatch (producer/storage/byte lanes/edges)",
    )

    expected_source = _expected_source(capture, rows, stream, document)
    source_metadata = document["source"]
    for field, expected in expected_source.items():
        _require(
            canonical_json(source_metadata.get(field)) == canonical_json(expected),
            f"source metadata mismatch: {field}",
        )
    diagnostic = _mapping(source_metadata.get("diagnostic"), "source diagnostic object")
    _require(
        set(diagnostic) == {"source_path", "runtime_addresses_excluded_from_normalization"},
        "source diagnostic fields",
    )
    _text(diagnostic.get("source_path"), "source diagnostic path")
    _require(
        diagnostic.get("runtime_addresses_excluded_from_normalization") is True,
        "runtime address normalization declaration",
    )
    return {
        "schema": "runtime-trace-numeric-ir-check-report-v1",
        "verdict": "PASS",
        "source_trace_sha256": expected_source["trace_sha256"],
        "normalized_numeric_sha256": expected_source["normalized_numeric_sha256"],
        "operation_count": len(operations),
        "value_count": len(values),
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.report.exists():
            raise IRCheckError("report path already exists")
        try:
            ir = json.loads(args.ir.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IRCheckError(f"Numeric IR JSON invalid: {exc}") from None
        report = check(ir, args.source, root=args.root)
        exit_code = 0
    except IRCheckError as exc:
        report = {
            "schema": "runtime-trace-numeric-ir-check-report-v1",
            "verdict": "FAIL",
            "reason": str(exc),
        }
        exit_code = 2
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
    except FileExistsError:
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_main())
