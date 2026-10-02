"""Address-independent normalization for Numeric IR v1."""

from __future__ import annotations

import hashlib

from runtime_trace.numeric_ir.schema import canonical_json


class NormalizationMismatch(ValueError):
    """Raised when two Numeric IR documents have different numeric graphs."""


def normalize(ir: dict) -> dict:
    """Return exactly the process-address-independent contract fields."""

    if not isinstance(ir, dict):
        raise ValueError("Numeric IR document must be an object")
    try:
        return {
            "schema": ir["schema"],
            "operations": ir["operations"],
            "values": ir["values"],
        }
    except KeyError as exc:
        raise ValueError(f"Numeric IR missing field: {exc.args[0]}") from None


def compare_normalized(old: dict, fresh: dict) -> dict:
    """Require exact normalized equality and summarize the shared form."""

    old_normalized = normalize(old)
    fresh_normalized = normalize(fresh)
    old_bytes = canonical_json(old_normalized)
    fresh_bytes = canonical_json(fresh_normalized)
    if old_bytes != fresh_bytes:
        raise NormalizationMismatch("normalized Numeric IR mismatch")
    digest = hashlib.sha256(old_bytes).hexdigest()
    return {
        "verdict": "PASS",
        "normalized_numeric_sha256": digest,
        "operation_count": len(old_normalized["operations"]),
        "value_count": len(old_normalized["values"]),
    }
