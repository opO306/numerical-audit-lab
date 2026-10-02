"""Canonical serialization helpers for Numeric IR v1."""

import json


SCHEMA = "runtime-trace-numeric-ir-regular-1step-v1"


def canonical_json(value: object) -> bytes:
    """Serialize with the byte form used by the schema hash contract."""

    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalized_document(document: dict) -> dict:
    """Return the address-independent numerical portion of a document."""

    return {
        "schema": document["schema"],
        "operations": document["operations"],
        "values": document["values"],
    }
