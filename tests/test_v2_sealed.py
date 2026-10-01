"""V2 prototype is frozen for independent audit (docs/V2_AUDIT_CHARTER.md).
Defects found by the audit go into a separate version (V2.1); these files never change."""
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEALED = {
    "docs/V2_ERROR_BOUND_PLAN.md": "03067ff693fcc887833d08940a98516052f76085715a6052b1708a505ac7ef84",
    "docs/V2_RESULT.md": "336c9161561df4181cde762c6cdd00f4567b3b1b50ea7ac07635d7022e6d9d56",
    "docs/V2_AUDIT_CHARTER.md": "53375183d8e01bf6ebded9e2aef6373ed480eb717d3a2711283cfe6911b0c598",
    "lab/v2_bound.py": "48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780",
    "run_v2.py": "0e7ab8522da11e67e335c85ef202d80849bd9b8d17555eb0603e0a41148d9cbe",
    "tests/test_v2.py": "80ca7b81ef376ce5adc5344e2d92ae24d0887803a7fc5f235bcf1f3e61eaa5d4",
    "reports/cloud-container-2026-10-01/v2_report.json": "493585a312ae271fa65e24e2c4e3c0d9bb32eaad9f32bf58935962d263b59c6e",
}


@pytest.mark.parametrize("path", sorted(SEALED))
def test_v2_file_is_unchanged(path):
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == SEALED[path], f"{path} changed while V2 is frozen for audit"
