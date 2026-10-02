"""Canonical serialization for Numeric IR to frozen V2 correspondence v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
REPORT_SCHEMA = "numeric-ir-frozen-v2-adapter-report-v1"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def write_canonical(path: Path, value: object) -> None:
    path.write_bytes(canonical_json(value))


def form_document(form: object) -> dict:
    return {
        "coef": [float(coefficient).hex() for coefficient in form.coef],
        "box": float(form.box).hex(),
    }
