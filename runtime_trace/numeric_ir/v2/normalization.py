"""Full-document normalization for independently checked V2 correspondences."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import NoReturn


SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
COMPARISON_SCHEMA = "numeric-ir-frozen-v2-normalized-comparison-v1"
TOP_KEYS = {"schema", "source", "values", "boundaries", "state_bindings", "operations"}
SOURCE_KEYS = {
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
INSTANCE_IR_SOURCE_KEYS = {"trace_sha256", "final_chain", "diagnostic"}


class NormalizationError(ValueError):
    """A correspondence cannot be normalized without ambiguity."""


class NormalizedMismatch(ValueError):
    """Two normalized correspondence documents are not exactly equal."""


def _fail(message: str) -> NoReturn:
    raise NormalizationError(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an integer")
    return value


def _json_domain(value: object, label: str) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is float:
        _fail(f"{label} contains a float instead of serialized exact data")
    if type(value) is list:
        for index, item in enumerate(value):
            _json_domain(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string key")
            _json_domain(item, f"{label}.{key}")
        return
    _fail(f"{label} contains a non-JSON value")


def _form(value: object, label: str, k: int) -> None:
    value = _dict(value, label, {"coef", "box"})
    coefficients = _list(value["coef"], f"{label}.coef")
    if len(coefficients) != k:
        _fail(f"{label}.coef length mismatch")
    for encoded in [*coefficients, value["box"]]:
        encoded = _string(encoded, label)
        try:
            number = float.fromhex(encoded)
        except (ValueError, OverflowError):
            _fail(f"{label} has invalid form encoding")
        if not math.isfinite(number) or number.hex() != encoded:
            _fail(f"{label} has noncanonical form encoding")


def _validate(document: object) -> dict:
    _json_domain(document, "correspondence")
    document = _dict(document, "correspondence", TOP_KEYS)
    if document["schema"] != SCHEMA:
        _fail("correspondence schema mismatch")
    source = _dict(document["source"], "source", SOURCE_KEYS)
    for key in ("audited_input_label", "numeric_ir_sha256", "normalized_numeric_sha256", "numeric_ir_schema"):
        _string(source[key], f"source.{key}")
    numeric_source = _dict(source["numeric_ir_source"], "source.numeric_ir_source")
    if not INSTANCE_IR_SOURCE_KEYS.issubset(numeric_source):
        _fail("numeric IR source instance metadata is incomplete")
    frozen = _dict(source["frozen_v2"], "source.frozen_v2", FROZEN_KEYS)
    for key in FROZEN_KEYS - {"k"}:
        _string(frozen[key], f"source.frozen_v2.{key}")
    k = _integer(frozen["k"], "source.frozen_v2.k")
    if k <= 0:
        _fail("source.frozen_v2.k must be positive")
    _list(document["values"], "values")
    _list(document["boundaries"], "boundaries")
    states = _list(document["state_bindings"], "state_bindings")
    operations = _list(document["operations"], "operations")
    for index, state in enumerate(states):
        state = _dict(state, f"state_bindings[{index}]")
        for key in ("byte_offset", "width"):
            _integer(state.get(key), f"state_bindings[{index}].{key}")
        for key in ("producer_ir_sequence", "trace_sequence"):
            if state.get(key) is not None:
                _integer(state[key], f"state_bindings[{index}].{key}")
        _form(state.get("form"), f"state_bindings[{index}].form", k)
    for index, operation in enumerate(operations):
        operation = _dict(operation, f"operations[{index}]")
        for key in ("ir_sequence", "trace_sequence", "elf_address", "mxcsr", "step", "v2_sequence"):
            _integer(operation.get(key), f"operations[{index}].{key}")
        for key in ("input0_form", "input1_form", "output_form"):
            _form(operation.get(key), f"operations[{index}].{key}", k)
    for index, boundary in enumerate(document["boundaries"]):
        boundary = _dict(boundary, f"boundaries[{index}]")
        if boundary.get("trace_sequence") is not None:
            _integer(boundary["trace_sequence"], f"boundaries[{index}].trace_sequence")
    return document


def normalize(output: dict) -> dict:
    """Remove only capture-instance identity while retaining the full protocol graph."""

    source = _validate(output)["source"]
    normalized_source = copy.deepcopy(source)
    del normalized_source["audited_input_label"]
    del normalized_source["numeric_ir_sha256"]
    for key in INSTANCE_IR_SOURCE_KEYS:
        del normalized_source["numeric_ir_source"][key]
    return {
        "schema": output["schema"],
        "source": normalized_source,
        "values": copy.deepcopy(output["values"]),
        "boundaries": copy.deepcopy(output["boundaries"]),
        "state_bindings": copy.deepcopy(output["state_bindings"]),
        "operations": copy.deepcopy(output["operations"]),
    }


def _first_difference(left: object, right: object, path: str = "$") -> str | None:
    if type(left) is not type(right):
        return path
    if type(left) is dict:
        if set(left) != set(right):
            return path
        for key in sorted(left):
            found = _first_difference(left[key], right[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if type(left) is list:
        if len(left) != len(right):
            return path
        for index, (a, b) in enumerate(zip(left, right)):
            found = _first_difference(a, b, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    return None if left == right else path


def compare_normalized(old: dict, fresh: dict) -> dict:
    """Return an equality report or raise at the first retained mismatch."""

    normalized_old = normalize(old)
    normalized_fresh = normalize(fresh)
    difference = _first_difference(normalized_old, normalized_fresh)
    if difference is not None:
        raise NormalizedMismatch(f"normalized correspondence mismatch at {difference}")
    digest = hashlib.sha256(_canonical(normalized_old)).hexdigest()
    return {
        "schema": COMPARISON_SCHEMA,
        "verdict": "EQUAL",
        "normalized_sha256": digest,
    }
