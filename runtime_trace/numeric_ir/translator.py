"""Mechanical Runtime Trace to Numeric IR translation for regular one-step.

The converter consumes only the raw trace, its capture manifest, and packaged
ELF images. It deliberately has no correspondence mapping or V2 dependency.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable

from runtime_trace import correspondence
from runtime_trace.semantics import Refused as DecodeRefused
from runtime_trace.semantics import decode

from .schema import SCHEMA, canonical_json, normalized_document


ARITHMETIC_KINDS = {"ADD", "SUB", "MUL"}
IR_KINDS = {
    "ADD": "ADD_BINARY64",
    "SUB": "SUB_BINARY64",
    "MUL": "MUL_BINARY64",
}
CAPTURE_SCHEMA = "gala-regular-1step-runtime-trace-v1"


class ConversionRefused(ValueError):
    """The source cannot be converted under the regular one-step contract."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ConversionRefused(reason)


def _raw(text: str, width: int) -> bytes:
    _require(
        isinstance(text, str) and re.fullmatch(r"0x[0-9a-f]+", text) is not None,
        "non-canonical raw bits",
    )
    _require(len(text) == 2 + width * 2, "raw bits width mismatch")
    return int(text, 16).to_bytes(width, "little")


def _hx(data: bytes) -> str:
    return f"0x{int.from_bytes(data, 'little'):0{len(data) * 2}x}"


def _finite(text: str) -> bool:
    return (
        isinstance(text, str)
        and re.fullmatch(r"0x[0-9a-f]{16}", text) is not None
        and ((int(text, 16) >> 52) & 0x7FF) != 0x7FF
    )


def _check_mxcsr(value: object) -> None:
    _require(isinstance(value, int), "MXCSR is not an integer")
    _require(
        value & ((3 << 13) | (1 << 15) | (1 << 6)) == 0,
        f"unsupported MXCSR control bits: {value:#x}",
    )
    _require(value & 0x1F80 == 0x1F80, "unsupported MXCSR exception masks")


def _integer_in_range(value: object, minimum: int, maximum: int, reason: str) -> int:
    _require(type(value) is int and minimum <= value <= maximum, reason)
    return value


def _hex_digest(value: object, reason: str) -> str:
    _require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        reason,
    )
    return value


def _object(value: object, reason: str) -> dict:
    _require(isinstance(value, dict), reason)
    return value


def _required_keys(value: dict, keys: set[str], reason: str) -> None:
    missing = sorted(keys - value.keys())
    _require(not missing, f"{reason}: missing {','.join(missing)}")


def _validate_context_shape(context: object, row_index: int, label: str) -> None:
    context = _object(context, f"trace row {row_index} {label} must be an object")
    _required_keys(
        context,
        {"gpr", "xmm", "extra_vectors", "mxcsr", "eflags"},
        f"trace row {row_index} {label}",
    )
    gpr = _object(context["gpr"], f"trace row {row_index} {label}.gpr must be an object")
    xmm = _object(context["xmm"], f"trace row {row_index} {label}.xmm must be an object")
    extra = _object(
        context["extra_vectors"],
        f"trace row {row_index} {label}.extra_vectors must be an object",
    )
    _require("rip" in gpr, f"trace row {row_index} {label}.gpr missing rip")
    for name, raw_bits in gpr.items():
        _require(
            isinstance(name, str)
            and isinstance(raw_bits, str)
            and re.fullmatch(r"0x[0-9a-f]{16}", raw_bits) is not None,
            f"trace row {row_index} {label}.gpr shape",
        )
    for collection_name, registers in (("xmm", xmm), ("extra_vectors", extra)):
        for name, raw_bits in registers.items():
            _require(
                isinstance(name, str)
                and isinstance(raw_bits, str)
                and re.fullmatch(r"0x[0-9a-f]+", raw_bits) is not None
                and (len(raw_bits) - 2) % 2 == 0,
                f"trace row {row_index} {label}.{collection_name} shape",
            )
    _integer_in_range(
        context["mxcsr"], 0, (1 << 32) - 1, f"trace row {row_index} MXCSR range"
    )
    _integer_in_range(
        context["eflags"], 0, (1 << 64) - 1, f"trace row {row_index} eflags range"
    )


def _canonical_gpr_name(register: str) -> str:
    if re.fullmatch(r"r\d+[dwb]", register):
        return register[:-1]
    if register.startswith("e"):
        return "r" + register[1:]
    if register in {"al", "bl", "cl", "dl"}:
        return "r" + register[0] + "x"
    if register in {"sil", "dil", "bpl", "spl"}:
        return "r" + register[:-1]
    if register.startswith("r"):
        return register
    return "r" + register


def _validate_context_register(
    context: dict, register: str, width: int, label: str
) -> None:
    vector = re.fullmatch(r"(xmm|ymm|zmm)\d+", register)
    if vector is not None:
        capacity = {"xmm": 16, "ymm": 32, "zmm": 64}[vector.group(1)]
        _require(width <= capacity, f"{label} vector register {register} width")
        raw_bits = context["xmm"].get(register)
        if raw_bits is None:
            raw_bits = context["extra_vectors"].get(register)
        _require(raw_bits is not None, f"{label} missing vector register {register}")
        _require(
            len(raw_bits) == 2 + 2 * capacity,
            f"{label} vector register {register} width",
        )
        return
    _require(width <= 8, f"{label} GPR {register} width")
    canonical = _canonical_gpr_name(register)
    _require(
        canonical in context["gpr"],
        f"{label} missing canonical register {canonical}",
    )


def _validate_operand_shape(operand: object, row_index: int, operand_index: int) -> None:
    label = f"trace row {row_index} operand {operand_index}"
    operand = _object(operand, f"{label} must be an object")
    _required_keys(
        operand, {"kind", "width", "access", "raw_bits", "origins"}, label
    )
    _require(
        operand["kind"] in {"register", "memory", "immediate", "code_address"},
        f"{label} kind",
    )
    width = _integer_in_range(operand["width"], 1, 64, f"{label} width range")
    _require(
        operand["access"] in {"read", "write", "read_write", "control"},
        f"{label} access",
    )
    _raw(operand["raw_bits"], width)
    _require(
        isinstance(operand["origins"], list) and len(operand["origins"]) == width,
        f"{label} origins shape",
    )
    _require(
        all(origin is None or isinstance(origin, str) for origin in operand["origins"]),
        f"{label} origins type",
    )
    if operand["kind"] == "register":
        _require(isinstance(operand.get("register"), str), f"{label} register name")
    if operand["kind"] == "memory":
        address = _integer_in_range(
            operand.get("address"), 0, (1 << 64) - 1, f"{label} address range"
        )
        _require(address + width <= 1 << 64, f"{label} address range")
    if "constant_origin" in operand:
        origin = _object(operand["constant_origin"], f"{label} constant origin object")
        _required_keys(origin, {"module_sha256", "file_offset"}, f"{label} constant origin")
        _hex_digest(origin["module_sha256"], f"{label} constant module SHA-256")
        _integer_in_range(
            origin["file_offset"], 0, (1 << 64) - 1, f"{label} constant offset range"
        )


def _validate_row_shape(row: object, row_index: int, row_count: int) -> None:
    row = _object(row, f"trace row {row_index} must be an object")
    required = {
        "seq", "pid", "ptid", "phase", "step", "symbol", "module_path",
        "module_sha256", "module_load_base", "runtime_pc", "elf_address",
        "elf_file_offset", "mapping", "bytes", "instruction", "opcode", "kind",
        "operands", "pre", "post", "post_pc", "changed_gpr_results", "chain",
    }
    _required_keys(row, required, f"trace row {row_index}")
    _integer_in_range(row["seq"], 0, max(0, row_count - 1), f"trace row {row_index} seq range")
    _integer_in_range(row["pid"], 1, (1 << 63) - 1, f"trace row {row_index} pid range")
    _require(
        isinstance(row["ptid"], list)
        and len(row["ptid"]) == 3
        and all(type(item) is int and 0 <= item < 1 << 63 for item in row["ptid"]),
        f"trace row {row_index} ptid shape",
    )
    _require(row["phase"] in {"init", "step"}, f"trace row {row_index} phase")
    _integer_in_range(row["step"], 0, 1, f"trace row {row_index} step range")
    for field in ("symbol", "module_path", "instruction", "opcode", "kind"):
        _require(isinstance(row[field], str), f"trace row {row_index} {field} type")
    _hex_digest(row["module_sha256"], f"trace row {row_index} module SHA-256")
    _hex_digest(row["chain"], f"trace row {row_index} chain shape")
    for field in (
        "module_load_base", "runtime_pc", "elf_address", "elf_file_offset", "post_pc"
    ):
        _integer_in_range(
            row[field], 0, (1 << 64) - 1, f"trace row {row_index} {field} range"
        )
    _require(
        isinstance(row["bytes"], str)
        and re.fullmatch(r"[0-9a-f]{2,30}", row["bytes"]) is not None
        and len(row["bytes"]) % 2 == 0,
        f"trace row {row_index} instruction bytes shape",
    )
    mapping = _object(row["mapping"], f"trace row {row_index} mapping object")
    _required_keys(
        mapping, {"start", "end", "perms", "file_offset", "path"},
        f"trace row {row_index} mapping",
    )
    start = _integer_in_range(
        mapping["start"], 0, (1 << 64) - 1, f"trace row {row_index} mapping start"
    )
    end = _integer_in_range(
        mapping["end"], 1, 1 << 64, f"trace row {row_index} mapping end"
    )
    _require(start < end, f"trace row {row_index} mapping range")
    _integer_in_range(
        mapping["file_offset"], 0, (1 << 64) - 1,
        f"trace row {row_index} mapping file offset",
    )
    _require(
        isinstance(mapping["perms"], str) and isinstance(mapping["path"], str),
        f"trace row {row_index} mapping strings",
    )
    _require(isinstance(row["operands"], list), f"trace row {row_index} operands list")
    for operand_index, operand in enumerate(row["operands"]):
        _validate_operand_shape(operand, row_index, operand_index)
    if row["kind"] in ARITHMETIC_KINDS | {"MOVE", "STACK", "ZERO", "ZERO_FILL"}:
        _require(bool(row["operands"]), f"trace row {row_index} destination operand")
        _require("result_bits" in row, f"trace row {row_index} missing result_bits")
        _raw(row["result_bits"], row["operands"][-1]["width"])
    _validate_context_shape(row["pre"], row_index, "pre")
    _validate_context_shape(row["post"], row_index, "post")
    for operand in row["operands"]:
        if operand["kind"] != "register":
            continue
        _validate_context_register(
            row["pre"], operand["register"], operand["width"],
            f"trace row {row_index} pre",
        )
        _validate_context_register(
            row["post"], operand["register"], operand["width"],
            f"trace row {row_index} post",
        )
    _object(
        row["changed_gpr_results"],
        f"trace row {row_index} changed_gpr_results must be an object",
    )


def _validate_module_shape(modules: object) -> None:
    modules = _object(modules, "capture modules must be an object")
    _require(bool(modules), "capture modules must not be empty")
    for module_path, module_value in modules.items():
        _require(isinstance(module_path, str), "capture module path type")
        module = _object(module_value, f"capture module {module_path} must be an object")
        _required_keys(
            module, {"path", "sha256", "load_base", "segments", "wheel_member"},
            f"capture module {module_path}",
        )
        _require(module["path"] == module_path, f"capture module path identity: {module_path}")
        _hex_digest(module["sha256"], f"capture module SHA-256: {module_path}")
        _integer_in_range(
            module["load_base"], 0, (1 << 64) - 1,
            f"capture module load base: {module_path}",
        )
        _require(isinstance(module["segments"], list), f"capture module segments: {module_path}")
        for segment_index, segment_value in enumerate(module["segments"]):
            segment = _object(
                segment_value,
                f"capture module segment {segment_index}: {module_path}",
            )
            _required_keys(
                segment, {"file_offset", "vaddr", "filesz", "memsz", "flags"},
                f"capture module segment {segment_index}: {module_path}",
            )
            for field in ("file_offset", "vaddr", "filesz", "memsz", "flags"):
                _integer_in_range(
                    segment[field], 0, (1 << 64) - 1,
                    f"capture module segment {field} range: {module_path}",
                )
            _require(
                segment["filesz"] <= segment["memsz"],
                f"capture module segment file/memory size: {module_path}",
            )
        _require(
            module["wheel_member"] is None or isinstance(module["wheel_member"], str),
            f"capture module wheel member: {module_path}",
        )


def _validate_region_shape(region_value: object, region_index: int, row_count: int) -> None:
    region = _object(region_value, f"region {region_index} must be an object")
    _required_keys(
        region,
        {
            "phase", "entry_pc", "return_pc", "start_seq", "end_seq", "pointers",
            "start_state", "end_state", "mxcsr",
        },
        f"region {region_index}",
    )
    _require(region["phase"] in {"init", "step"}, f"region {region_index} phase")
    start_seq = _integer_in_range(
        region["start_seq"], 0, row_count, f"region {region_index} sequence range"
    )
    end_seq = _integer_in_range(
        region["end_seq"], 0, row_count, f"region {region_index} sequence range"
    )
    _require(start_seq < end_seq, f"region {region_index} sequence range")
    _integer_in_range(
        region["entry_pc"], 0, (1 << 64) - 1, f"region {region_index} entry PC range"
    )
    _integer_in_range(
        region["return_pc"], 0, (1 << 64) - 1, f"region {region_index} return PC range"
    )
    pointers = _object(region["pointers"], f"region {region_index} pointers object")
    state_names = {"q", "full_v", "latent", "gradient"}
    _require(set(pointers) == state_names, f"region {region_index} boundary pointer names")
    for name, pointer in pointers.items():
        pointer = _integer_in_range(
            pointer, 0, (1 << 64) - 1, "boundary pointer range"
        )
        _require(pointer + 16 <= 1 << 64, "boundary pointer range")
    for state_field in ("start_state", "end_state"):
        state = _object(region[state_field], f"region {region_index} {state_field} object")
        _require(set(state) == state_names, f"region {region_index} {state_field} names")
        for raw_bits in state.values():
            _raw(raw_bits, 16)
    _integer_in_range(
        region["mxcsr"], 0, (1 << 32) - 1, f"region {region_index} MXCSR range"
    )


def _validate_decoded_shape(capture: dict, rows: list[dict]) -> None:
    _required_keys(
        capture,
        {
            "schema", "verdict", "record_count", "scalar_fp_count",
            "opcode_histogram", "regions", "modules", "trace_sha256", "final_chain",
            "pending_uncompleted_instruction", "machine_mapping_read_by_tracer",
        },
        "capture",
    )
    _integer_in_range(
        capture["record_count"], 0, (1 << 63) - 1, "capture record count range"
    )
    _integer_in_range(
        capture["scalar_fp_count"], 0, capture["record_count"],
        "capture scalar count range",
    )
    _require(isinstance(capture["opcode_histogram"], dict), "capture opcode histogram object")
    for opcode, count in capture["opcode_histogram"].items():
        _require(isinstance(opcode, str), "capture opcode histogram key")
        _integer_in_range(count, 0, capture["record_count"], "capture opcode count range")
    _hex_digest(capture["trace_sha256"], "capture trace SHA-256 shape")
    _hex_digest(capture["final_chain"], "capture final chain shape")
    _require(
        type(capture["machine_mapping_read_by_tracer"]) is bool,
        "capture mapping-read flag type",
    )
    _require(isinstance(capture["regions"], list), "capture regions must be a list")
    _validate_module_shape(capture["modules"])
    for row_index, row in enumerate(rows):
        _validate_row_shape(row, row_index, len(rows))
        module = capture["modules"].get(row["module_path"])
        _require(module is not None, f"trace row {row_index} unknown module path")
        _require(
            row["module_sha256"] == module["sha256"],
            f"trace row {row_index} module SHA-256 identity",
        )
        _require(
            row["module_load_base"] == module["load_base"],
            f"trace row {row_index} module load base identity",
        )
    for region_index, region in enumerate(capture["regions"]):
        _validate_region_shape(region, region_index, len(rows))


def _source_paths(source: Path) -> tuple[Path, Path]:
    source = Path(source)
    if source.is_dir():
        return source / "trace.jsonl", source / "capture.json"
    if source.name == "trace.jsonl":
        return source, source.with_name("capture.json")
    if source.name == "capture.json":
        return source.with_name("trace.jsonl"), source
    raise ConversionRefused(
        "source must be an artifact directory, trace.jsonl, or capture.json"
    )


def _infer_root(source: Path) -> Path:
    start = source if source.is_dir() else source.parent
    for candidate in (start, *start.parents):
        if (candidate / "runtime_trace/frozen_binaries/manifest.json").is_file():
            return candidate
    raise ConversionRefused(
        "repository root with packaged module manifest was not found"
    )


def _read_source(source: Path) -> tuple[Path, bytes, dict, list[dict]]:
    trace_path, capture_path = _source_paths(source)
    try:
        stream = trace_path.read_bytes()
        capture = json.loads(capture_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConversionRefused(f"raw trace/capture read failed: {exc}") from exc
    _require(isinstance(capture, dict), "capture JSON object required")
    _hex_digest(capture.get("trace_sha256"), "capture trace SHA-256 shape")
    _require(
        hashlib.sha256(stream).hexdigest() == capture.get("trace_sha256"),
        "trace raw hash mismatch",
    )
    try:
        rows = [json.loads(line) for line in stream.splitlines()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConversionRefused(
            f"trace JSON decoding failed after hash verification: {exc}"
        ) from exc
    _validate_decoded_shape(capture, rows)
    return trace_path, stream, capture, rows


def _validate_capture_and_chain(stream: bytes, capture: dict, rows: list[dict]) -> None:
    _require(capture.get("schema") == CAPTURE_SCHEMA, "capture schema mismatch")
    _require(capture.get("verdict") == "CAPTURED", "capture is REFUSED or incomplete")
    _require(
        capture.get("pending_uncompleted_instruction") is None,
        "capture has a pending uncompleted instruction",
    )
    _require(
        capture.get("machine_mapping_read_by_tracer") is False,
        "capture reports forbidden mapping use",
    )
    _require(capture.get("record_count") == len(rows), "record count mismatch")
    _require(
        capture.get("scalar_fp_count")
        == sum(row.get("kind") in ARITHMETIC_KINDS for row in rows),
        "scalar occurrence count mismatch",
    )
    _require(
        capture.get("opcode_histogram")
        == dict(Counter(row.get("opcode") for row in rows)),
        "opcode histogram mismatch",
    )

    chain = "0" * 64
    for record in rows:
        unsigned = {key: value for key, value in record.items() if key != "chain"}
        encoded = json.dumps(
            unsigned, sort_keys=True, separators=(",", ":")
        ).encode()
        chain = hashlib.sha256(bytes.fromhex(chain) + encoded).hexdigest()
        _require(record.get("chain") == chain, "record hash chain mismatch")
    _require(capture.get("final_chain") == chain, "record hash chain endpoint mismatch")
    _require(
        hashlib.sha256(stream).hexdigest() == capture["trace_sha256"],
        "trace raw hash mismatch",
    )


def _validate_early_record_contract(rows: list[dict]) -> None:
    _require(
        [row.get("seq") for row in rows] == list(range(len(rows))),
        "trace sequence gap, duplicate, or reorder",
    )
    for record in rows:
        for context_name in ("pre", "post"):
            context = record.get(context_name)
            _require(
                isinstance(context, dict),
                f"record {record['seq']} missing {context_name} state",
            )
            _check_mxcsr(context.get("mxcsr"))
        try:
            recorded_opcode, recorded_kind, _, recorded_width = decode(
                record["instruction"]
            )
        except (KeyError, DecodeRefused) as exc:
            raise ConversionRefused(
                f"unsupported recorded instruction at {record.get('seq')}: {exc}"
            ) from exc
        _require(
            record.get("opcode") == recorded_opcode,
            f"opcode label disagrees with instruction at record {record['seq']}",
        )
        _require(
            record.get("kind") == recorded_kind,
            f"kind label disagrees with instruction at record {record['seq']}",
        )
        if recorded_kind in ARITHMETIC_KINDS:
            operands = record.get("operands")
            _require(
                isinstance(operands, list) and len(operands) == 2,
                "scalar arithmetic operand count",
            )
            _require(
                recorded_width == 8 and all(op.get("width") == 8 for op in operands),
                "scalar arithmetic width mismatch",
            )
            for operand in operands:
                _require(_finite(operand.get("raw_bits")), "nonfinite scalar input")
            _require(_finite(record.get("result_bits")), "nonfinite scalar result")


def _independent_raw_checks(rows: list[dict], capture: dict, root: Path) -> dict:
    try:
        correspondence.verify_linkage(rows, capture["regions"], capture["record_count"])
        decoded = correspondence.disassembly_for_rows(rows, capture["modules"], root)
        for record in rows:
            decode_key = (record["module_path"], record["elf_address"])
            _require(
                decode_key in decoded,
                f"independent disassembly missing instruction at record {record['seq']}",
            )
            reference = decoded[decode_key]
            try:
                opcode, kind, _, width = decode(reference)
            except DecodeRefused as exc:
                raise ConversionRefused(
                    f"unsupported independently decoded instruction at {record['seq']}: {exc}"
                ) from exc
            _require(
                opcode == record["opcode"],
                f"independent opcode mismatch at record {record['seq']}",
            )
            _require(
                kind == record["kind"],
                f"independent kind mismatch at record {record['seq']}",
            )
            if kind in ARITHMETIC_KINDS:
                _require(width == 8, "independent scalar width mismatch")
        correspondence.verify_flow(rows, capture, decoded, root)
        return decoded
    except ConversionRefused:
        raise
    except (OSError, subprocess.SubprocessError, correspondence.AuditError) as exc:
        message = str(exc)
        if "executed instruction byte correspondence" in message:
            message = "module instruction bytes mismatch"
        raise ConversionRefused(message or exc.__class__.__name__) from exc


def _validate_regions(capture: dict, rows: list[dict]) -> list[dict]:
    regions = capture.get("regions")
    _require(isinstance(regions, list) and len(regions) == 2, "two regions are required")
    _require(
        [region.get("phase") for region in regions] == ["init", "step"],
        "region phase order mismatch",
    )
    for region in regions:
        pointers = region["pointers"]
        names = sorted(pointers)
        for index, left_name in enumerate(names):
            left = pointers[left_name]
            for right_name in names[index + 1 :]:
                right = pointers[right_name]
                _require(
                    left + 16 <= right or right + 16 <= left,
                    "ambiguous boundary memory alias: "
                    f"{left_name} overlaps {right_name} in {region['phase']}",
                )
        for name in ("q", "full_v", "latent", "gradient"):
            _require(name in region.get("pointers", {}), f"missing {name} boundary pointer")
            _raw(region["start_state"][name], 16)
            _raw(region["end_state"][name], 16)
        _check_mxcsr(region.get("mxcsr"))
        first = rows[region["start_seq"]]
        for register in ("rcx", "r8", "r9", "rsp"):
            _require(
                register in first["pre"]["gpr"],
                f"region {region['phase']} entry missing ABI register {register}",
            )
        for register in ("xmm0", "xmm1"):
            _require(
                register in first["pre"]["xmm"]
                or register in first["pre"]["extra_vectors"],
                f"region {region['phase']} entry missing XMM boundary {register}",
            )
            _validate_context_register(
                first["pre"], register, 8, f"region {region['phase']} entry"
            )
        for name, register in (("q", "rcx"), ("full_v", "r8"), ("latent", "r9")):
            _require(
                region["pointers"][name] == int(first["pre"]["gpr"][register], 16),
                f"{name} boundary pointer disagrees with ABI register",
            )
    for record in rows:
        _require(
            set(record["pre"]["gpr"]) == set(record["post"]["gpr"]),
            f"trace row {record['seq']} pre/post GPR register set mismatch",
        )
    for name in ("q", "full_v", "latent"):
        _require(
            regions[0]["end_state"][name] == regions[1]["start_state"][name],
            f"{name} init-to-step boundary mismatch",
        )
    return regions


def _storage(space: str, name: str, byte_offset: int, width: int) -> dict:
    return {
        "space": space,
        "name": name,
        "byte_offset": byte_offset,
        "width": width,
    }


def _slice_storage(storage: dict, offset: int, width: int) -> dict:
    return _storage(
        storage["space"],
        storage["name"],
        storage["byte_offset"] + offset,
        width,
    )


def _resolve_boundary_storage(
    pointers: dict[str, int], address: int, width: int
) -> dict | None:
    end = address + width
    intersections = [
        (name, base)
        for name, base in pointers.items()
        if address < base + 16 and base < end
    ]
    _require(
        len(intersections) <= 1,
        "ambiguous boundary memory alias during storage resolution",
    )
    if not intersections:
        return None
    name, base = intersections[0]
    _require(
        base <= address and end <= base + 16,
        "ambiguous boundary memory alias: operand partially overlaps boundary",
    )
    return _storage("buffer", name, address - base, width)


@dataclass(frozen=True)
class _ByteRef:
    value_id: str
    offset: int
    origin_tag: str


class _Dataflow:
    def __init__(self, rows: list[dict], capture: dict, root: Path):
        self.rows = rows
        self.capture = capture
        self.root = root
        self.values: list[dict] = []
        self.operations: list[dict] = []
        self.value_by_id: dict[str, dict] = {}
        self.value_bytes: dict[str, bytes] = {}
        self.state: dict[tuple, _ByteRef] = {}
        self.phase = ""
        self.region: dict = {}
        self.entry_rsp = 0
        self.binary_resolver = correspondence.FrozenBinaryResolver(root)

    def add_value(
        self,
        value_id: str,
        producer_kind: str,
        data: bytes,
        producer: dict,
        storage: dict,
        source_slices: list[dict],
    ) -> dict:
        _require(value_id not in self.value_by_id, f"duplicate value identity: {value_id}")
        value = {
            "value_id": value_id,
            "producer_kind": producer_kind,
            "raw_bits": _hx(data),
            "width": len(data),
            "producer": producer,
            "storage": storage,
            "source_slices": source_slices,
        }
        self.values.append(value)
        self.value_by_id[value_id] = value
        self.value_bytes[value_id] = data
        return value

    def byte_value(self, ref: _ByteRef) -> int:
        return self.value_bytes[ref.value_id][ref.offset]

    def operand_keys(self, operand: dict) -> list[tuple]:
        try:
            return correspondence.operand_keys(operand)
        except (KeyError, ValueError) as exc:
            raise ConversionRefused(f"operand storage decode failed: {exc}") from exc

    def operand_storage(self, record: dict, operand: dict, operand_index: int) -> dict:
        width = operand["width"]
        if operand["kind"] == "register":
            keys = self.operand_keys(operand)
            _require(len(keys) == width and keys, "register storage width mismatch")
            return _storage("register", keys[0][1], keys[0][2], width)
        if operand["kind"] == "memory":
            address = operand["address"]
            boundary = _resolve_boundary_storage(
                self.region["pointers"], address, width
            )
            if boundary is not None:
                return boundary
            relative = address - self.entry_rsp
            if abs(relative) <= 1 << 20:
                return _storage("stack", self.phase, relative, width)
            return _storage(
                "memory-occurrence",
                f"{self.phase}:r{record['seq']}:o{operand_index}",
                0,
                width,
            )
        if operand["kind"] == "immediate":
            return _storage(
                "instruction", f"r{record['seq']}:o{operand_index}", 0, width
            )
        if operand["kind"] == "code_address":
            return _storage("control", f"r{record['seq']}:o{operand_index}", 0, width)
        raise ConversionRefused(
            f"unknown operand storage kind: {operand.get('kind')}"
        )

    def refs_for_operand(self, operand: dict) -> list[_ByteRef | None]:
        return [self.state.get(key) for key in self.operand_keys(operand)]

    def check_known_bytes(
        self, operand: dict, refs: list[_ByteRef | None]
    ) -> None:
        data = _raw(operand["raw_bits"], operand["width"])
        origins = operand.get("origins")
        _require(
            isinstance(origins, list) and len(origins) == operand["width"],
            "operand origin width mismatch",
        )
        for index, ref in enumerate(refs):
            if ref is None:
                continue
            _require(
                self.byte_value(ref) == data[index], "provenance raw byte mismatch"
            )
            _require(
                origins[index] == ref.origin_tag,
                "record origin disagrees with derived provenance",
            )

    def slices(
        self,
        refs: list[_ByteRef | None],
        destination_storage: dict,
        trace_sequence: int | None,
        source_operand_index: int | None,
    ) -> list[dict]:
        parts: list[dict] = []
        start = 0
        while start < len(refs):
            ref = refs[start]
            if ref is None:
                start += 1
                continue
            end = start + 1
            while end < len(refs):
                candidate = refs[end]
                if (
                    candidate is None
                    or candidate.value_id != ref.value_id
                    or candidate.offset != ref.offset + (end - start)
                ):
                    break
                end += 1
            width = end - start
            source_value = self.value_by_id[ref.value_id]
            parts.append(
                {
                    "value_id": ref.value_id,
                    "source_offset": ref.offset,
                    "destination_offset": start,
                    "width": width,
                    "trace_sequence": trace_sequence,
                    "source_operand_index": source_operand_index,
                    "source_storage": _slice_storage(
                        source_value["storage"], ref.offset, width
                    ),
                    "destination_storage": _slice_storage(
                        destination_storage, start, width
                    ),
                }
            )
            start = end
        return parts

    def put_refs(
        self,
        operand: dict,
        value_id: str,
        known_offsets: Iterable[int],
        origin_tag: str,
    ) -> None:
        keys = self.operand_keys(operand)
        known = set(known_offsets)
        for index, key in enumerate(keys):
            if index in known:
                self.state[key] = _ByteRef(value_id, index, origin_tag)
            else:
                self.state.pop(key, None)

    def add_boundary(
        self,
        phase: str,
        name: str,
        data: bytes,
        prior: list[_ByteRef] | None,
    ) -> None:
        value_id = f"v:boundary:{phase}:{name}"
        is_register = name.startswith("xmm")
        storage = _storage(
            "register" if is_register else "buffer",
            f"v{name[3:]}" if is_register else name,
            0,
            len(data),
        )
        producer = {
            "role": "boundary",
            "phase": phase,
            "boundary": name,
            "trace_sequence": None,
            "operand_index": None,
        }
        if prior is None:
            kind = "LOAD_BITS"
            source_slices: list[dict] = []
        else:
            kind = "COPY_BITS"
            _require(
                all(
                    self.byte_value(ref) == byte for ref, byte in zip(prior, data)
                ),
                f"{name} cross-region provenance bits mismatch",
            )
            source_slices = self.slices(prior, storage, None, None)
        self.add_value(value_id, kind, data, producer, storage, source_slices)
        tag = f"boundary:{phase}:{name}"
        if is_register:
            for index in range(len(data)):
                self.state[("r", storage["name"], index)] = _ByteRef(
                    value_id, index, tag
                )
        else:
            base = self.region["pointers"][name]
            for index in range(len(data)):
                self.state[("m", base + index)] = _ByteRef(
                    value_id, index, f"{tag}:{index}"
                )

    def start_region(
        self, region: dict, prior_buffers: dict[str, list[_ByteRef]]
    ) -> None:
        self.phase = region["phase"]
        self.region = region
        first = self.rows[region["start_seq"]]
        self.entry_rsp = int(first["pre"]["gpr"]["rsp"], 16)
        self.state = {}
        for name in ("q", "full_v", "latent", "gradient"):
            prior = (
                prior_buffers.get(name)
                if self.phase == "step" and name != "gradient"
                else None
            )
            self.add_boundary(
                self.phase,
                name,
                _raw(region["start_state"][name], 16),
                prior,
            )
        for name in ("xmm0", "xmm1"):
            data = correspondence.register_raw(first["pre"], name, 8)
            self.add_boundary(self.phase, name, data, None)

    def constant_refs(
        self, record: dict, operand: dict, operand_index: int
    ) -> list[_ByteRef] | None:
        origin = operand.get("constant_origin")
        if origin is None:
            if operand["kind"] == "immediate" and not any(
                _raw(operand["raw_bits"], operand["width"])
            ):
                value_id = f"v:r{record['seq']}:o{operand_index}:literal-zero"
                storage = self.operand_storage(record, operand, operand_index)
                self.add_value(
                    value_id,
                    "ZERO_BITS",
                    bytes(operand["width"]),
                    {
                        "role": "instruction_zero",
                        "trace_sequence": record["seq"],
                        "operand_index": operand_index,
                        "phase": record["phase"],
                    },
                    storage,
                    [],
                )
                return [
                    _ByteRef(value_id, index, "instruction_literal")
                    for index in range(operand["width"])
                ]
            return None
        digest = origin.get("module_sha256")
        offset = origin.get("file_offset")
        _require(
            isinstance(digest, str) and isinstance(offset, int),
            "ELF constant origin shape",
        )
        try:
            _, image = self.binary_resolver.resolve(digest)
        except (OSError, correspondence.AuditError) as exc:
            raise ConversionRefused(str(exc)) from exc
        width = operand["width"]
        data = _raw(operand["raw_bits"], width)
        _require(
            image[offset : offset + width] == data, "ELF constant raw bits mismatch"
        )
        expected_origins = [
            f"ELF_CONST:{digest}:{offset + index}" for index in range(width)
        ]
        _require(
            operand.get("origins") == expected_origins,
            "ELF constant origin mismatch",
        )
        value_id = f"v:r{record['seq']}:o{operand_index}:const"
        storage = _storage("elf", digest, offset, width)
        self.add_value(
            value_id,
            "CONST_BITS",
            data,
            {
                "role": "constant_read",
                "trace_sequence": record["seq"],
                "operand_index": operand_index,
                "phase": record["phase"],
                "module_sha256": digest,
                "file_offset": offset,
            },
            storage,
            [],
        )
        return [
            _ByteRef(value_id, index, expected_origins[index])
            for index in range(width)
        ]

    def source_refs(
        self, record: dict, operand: dict, operand_index: int
    ) -> list[_ByteRef | None]:
        constant = self.constant_refs(record, operand, operand_index)
        if constant is not None:
            return constant
        refs = self.refs_for_operand(operand)
        self.check_known_bytes(operand, refs)
        return refs

    def copy_record(self, record: dict) -> None:
        source, destination = record["operands"]
        refs = self.source_refs(record, source, 0)
        _require(record["result_bits"] == source["raw_bits"], "copy raw bits mismatch")
        storage = self.operand_storage(record, destination, 1)
        slices = self.slices(refs, storage, record["seq"], 0)
        keys = self.operand_keys(destination)
        if slices:
            value_id = f"v:r{record['seq']}:copy"
            self.add_value(
                value_id,
                "COPY_BITS",
                _raw(record["result_bits"], destination["width"]),
                {
                    "role": "copy_result",
                    "trace_sequence": record["seq"],
                    "operand_index": 1,
                    "phase": record["phase"],
                },
                storage,
                slices,
            )
            known_offsets = [index for index, ref in enumerate(refs) if ref is not None]
            self.put_refs(
                destination, value_id, known_offsets, f"record:{record['seq']}"
            )
        else:
            for key in keys:
                self.state.pop(key, None)
        self.zero_extensions(record, source, destination)

    def zero_value(
        self,
        record: dict,
        destination: dict,
        role: str,
        offset: int,
        width: int,
        origin_suffix: str,
    ) -> None:
        _require(width > 0, "zero value must have positive width")
        base_storage = self.operand_storage(
            record, destination, len(record["operands"]) - 1
        )
        storage = _slice_storage(base_storage, offset, width)
        value_id = f"v:r{record['seq']}:{role.replace('_', '-')}"
        self.add_value(
            value_id,
            "ZERO_BITS",
            bytes(width),
            {
                "role": role,
                "trace_sequence": record["seq"],
                "operand_index": len(record["operands"]) - 1,
                "phase": record["phase"],
            },
            storage,
            [],
        )
        keys = self.operand_keys(destination)
        for local_index in range(width):
            key_index = offset + local_index
            if key_index < len(keys):
                key = keys[key_index]
            elif destination["kind"] == "register":
                key = ("r", keys[0][1], key_index)
            else:
                raise ConversionRefused("zero extension exceeds non-register storage")
            self.state[key] = _ByteRef(
                value_id,
                local_index,
                f"record:{record['seq']}:{origin_suffix}",
            )

    def zero_extensions(
        self, record: dict, source: dict, destination: dict
    ) -> None:
        if destination["kind"] != "register":
            return
        name = destination["register"]
        width = destination["width"]
        if not name.startswith(("xmm", "ymm", "zmm")) and width == 4:
            self.zero_value(record, destination, "zero_extend", 4, 4, "zero_extend")
        if name.startswith("xmm") and (
            record["opcode"] in {"movq", "vmovd"}
            or record["opcode"] == "movsd" and source["kind"] == "memory"
        ):
            self.zero_value(
                record, destination, "zero_upper", width, 16 - width, "zero_upper"
            )

    def zero_record(self, record: dict) -> None:
        destination = record["operands"][-1]
        result = _raw(record["result_bits"], destination["width"])
        _require(not any(result), "zero generation produced nonzero bits")
        storage = self.operand_storage(
            record, destination, len(record["operands"]) - 1
        )
        value_id = f"v:r{record['seq']}:zero"
        self.add_value(
            value_id,
            "ZERO_BITS",
            result,
            {
                "role": "zero_result",
                "trace_sequence": record["seq"],
                "operand_index": len(record["operands"]) - 1,
                "phase": record["phase"],
            },
            storage,
            [],
        )
        self.put_refs(
            destination,
            value_id,
            range(destination["width"]),
            f"record:{record['seq']}",
        )

    def integer_zero(self, record: dict) -> str | None:
        if record["opcode"] != "xor" or len(record["operands"]) != 2:
            return None
        left, right = record["operands"]
        if left.get("kind") != "register" or right.get("kind") != "register":
            return None
        if left.get("register") != right.get("register"):
            return None
        width = right["width"]
        data = correspondence.register_raw(record["post"], right["register"], width)
        _require(not any(data), "integer xor zero produced nonzero bits")
        storage = self.operand_storage(record, right, 1)
        value_id = f"v:r{record['seq']}:integer-zero"
        self.add_value(
            value_id,
            "ZERO_BITS",
            data,
            {
                "role": "integer_zero",
                "trace_sequence": record["seq"],
                "operand_index": 1,
                "phase": record["phase"],
            },
            storage,
            [],
        )
        self.put_refs(
            right,
            value_id,
            range(width),
            f"record:{record['seq']}:integer_zero",
        )
        return self.operand_keys(right)[0][1]

    def arithmetic_input(self, record: dict, operand_index: int, role: str) -> dict:
        operand = record["operands"][operand_index]
        is_constant = operand.get("constant_origin") is not None
        refs = self.source_refs(record, operand, operand_index)
        _require(
            all(ref is not None for ref in refs),
            "unknown numerical input provenance",
        )
        typed_refs = [ref for ref in refs if ref is not None]
        storage = self.operand_storage(record, operand, operand_index)
        if is_constant:
            return self.value_by_id[typed_refs[0].value_id]
        value_id = f"v:r{record['seq']}:{role.replace('_', '-')}"
        return self.add_value(
            value_id,
            "COPY_BITS",
            _raw(operand["raw_bits"], 8),
            {
                "role": role,
                "trace_sequence": record["seq"],
                "operand_index": operand_index,
                "phase": record["phase"],
            },
            storage,
            self.slices(typed_refs, storage, record["seq"], operand_index),
        )

    def arithmetic_record(self, record: dict) -> None:
        destination_input = self.arithmetic_input(
            record, 1, "arithmetic_destination_pre_read"
        )
        source_input = self.arithmetic_input(record, 0, "arithmetic_source_read")
        destination = record["operands"][1]
        result = _raw(record["result_bits"], 8)
        value_id = f"v:r{record['seq']}:result"
        output = self.add_value(
            value_id,
            "ARITHMETIC_RESULT",
            result,
            {
                "role": "arithmetic_result",
                "trace_sequence": record["seq"],
                "operand_index": 1,
                "phase": record["phase"],
                "operation_kind": IR_KINDS[record["kind"]],
            },
            self.operand_storage(record, destination, 1),
            [],
        )
        self.put_refs(
            destination, value_id, range(8), f"record:{record['seq']}"
        )
        self.operations.append(
            {
                "ir_sequence": len(self.operations),
                "trace_sequence": record["seq"],
                "module_sha256": record["module_sha256"],
                "elf_address": record["elf_address"],
                "instruction_bytes": record["bytes"],
                "opcode": record["opcode"],
                "operation_kind": IR_KINDS[record["kind"]],
                "input0_value_id": destination_input["value_id"],
                "input1_value_id": source_input["value_id"],
                "output_value_id": output["value_id"],
                "input0_raw_bits": destination_input["raw_bits"],
                "input1_raw_bits": source_input["raw_bits"],
                "output_raw_bits": output["raw_bits"],
                "mxcsr": record["pre"]["mxcsr"],
                "phase": record["phase"],
                "step": record["step"],
            }
        )

    def forget_changed_gprs(self, record: dict, exempt: set[str]) -> None:
        before = record["pre"]["gpr"]
        after = record["post"]["gpr"]
        for name in before:
            if name == "rip" or name in exempt or before[name] == after[name]:
                continue
            for index in range(8):
                self.state.pop(("r", name, index), None)

    def process_record(self, record: dict) -> None:
        kind = record["kind"]
        exempt: set[str] = set()
        if kind in ARITHMETIC_KINDS:
            self.arithmetic_record(record)
            destination = record["operands"][1]
            exempt.add(self.operand_keys(destination)[0][1])
        elif kind in {"MOVE", "STACK"}:
            self.copy_record(record)
            destination = record["operands"][1]
            if destination["kind"] == "register":
                exempt.add(self.operand_keys(destination)[0][1])
        elif kind in {"ZERO", "ZERO_FILL"}:
            self.zero_record(record)
            destination = record["operands"][-1]
            if destination["kind"] == "register":
                exempt.add(self.operand_keys(destination)[0][1])
        zero_register = self.integer_zero(record)
        if zero_register is not None:
            exempt.add(zero_register)
        if kind in {"STACK", "CONTROL"}:
            exempt.add("rsp")
        self.forget_changed_gprs(record, exempt)

    def end_region(self, region: dict) -> dict[str, list[_ByteRef]]:
        result: dict[str, list[_ByteRef]] = {}
        for name, base in region["pointers"].items():
            refs = [self.state.get(("m", base + index)) for index in range(16)]
            _require(
                all(ref is not None for ref in refs),
                f"{name} endpoint has unknown numerical provenance",
            )
            typed = [ref for ref in refs if ref is not None]
            data = bytes(self.byte_value(ref) for ref in typed)
            _require(
                data == _raw(region["end_state"][name], 16),
                f"{name} endpoint bits disagree with provenance",
            )
            result[name] = typed
        return result

    def run(self, regions: list[dict]) -> tuple[list[dict], list[dict]]:
        prior: dict[str, list[_ByteRef]] = {}
        for region in regions:
            self.start_region(region, prior)
            for record in self.rows[region["start_seq"] : region["end_seq"]]:
                self.process_record(record)
            prior = self.end_region(region)
        _require(
            len(self.operations) == self.capture["scalar_fp_count"],
            "runtime arithmetic occurrence to IR count mismatch",
        )
        return self.operations, self.values


def translate(source: Path, root: Path | None = None) -> dict:
    """Translate a captured regular one-step trace into in-memory Numeric IR."""

    source = Path(source)
    resolved_root = (
        Path(root).resolve() if root is not None else _infer_root(source).resolve()
    )
    trace_path, stream, capture, rows = _read_source(source)
    _validate_capture_and_chain(stream, capture, rows)
    _validate_early_record_contract(rows)
    regions = _validate_regions(capture, rows)
    _independent_raw_checks(rows, capture, resolved_root)
    operations, values = _Dataflow(rows, capture, resolved_root).run(regions)

    document = {
        "schema": SCHEMA,
        "source": {
            "capture_schema": capture["schema"],
            "trace_sha256": capture["trace_sha256"],
            "final_chain": capture["final_chain"],
            "record_count": capture["record_count"],
            "scalar_fp_count": capture["scalar_fp_count"],
            "module_sha256s": sorted(
                module["sha256"] for module in capture["modules"].values()
            ),
            "regions": [
                {
                    "phase": region["phase"],
                    "start_seq": region["start_seq"],
                    "end_seq": region["end_seq"],
                    "start_state": region["start_state"],
                    "end_state": region["end_state"],
                    "mxcsr": region["mxcsr"],
                }
                for region in regions
            ],
            "normalized_numeric_sha256": "",
            "diagnostic": {
                "source_path": str(trace_path.resolve()),
                "runtime_addresses_excluded_from_normalization": True,
            },
        },
        "operations": operations,
        "values": values,
    }
    document["source"]["normalized_numeric_sha256"] = hashlib.sha256(
        canonical_json(normalized_document(document))
    ).hexdigest()
    return document


def translate_to_directory(
    source: Path, out: Path, root: Path | None = None
) -> dict:
    """Translate, exclusively create a new directory, and publish its report last."""

    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    document = translate(source, root=root)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent)
    )
    try:
        (temporary / "numeric_ir.json").write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n"
        )
        report = {
            "schema": "runtime-trace-numeric-ir-conversion-report-v1",
            "verdict": "CONVERTED",
            "source_trace_sha256": document["source"]["trace_sha256"],
            "normalized_numeric_sha256": document["source"][
                "normalized_numeric_sha256"
            ],
            "operation_count": len(document["operations"]),
            "value_count": len(document["values"]),
        }
        (temporary / "conversion_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        out.mkdir()
        try:
            (temporary / "numeric_ir.json").replace(out / "numeric_ir.json")
            # Completion marker: readers must require this file as well as the IR.
            (temporary / "conversion_report.json").replace(
                out / "conversion_report.json"
            )
            temporary.rmdir()
        except Exception:
            shutil.rmtree(out, ignore_errors=True)
            raise
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return document


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    try:
        document = translate_to_directory(args.source, args.out, args.root)
    except (ConversionRefused, FileExistsError) as exc:
        print(
            json.dumps({"verdict": "REFUSED", "reason": str(exc)}),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "verdict": "CONVERTED",
                "operation_count": len(document["operations"]),
                "value_count": len(document["values"]),
                "out": str(args.out),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
