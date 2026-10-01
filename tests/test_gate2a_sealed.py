"""Gate 2A is CLOSED / PARTIAL and sealed: its plan, result, report and code must not change.
Later work (V2, Gate 2B) may import these modules but never edit them."""
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEALED = {
    "docs/GATE2A_PLAN.md": "b17095764e9f0c18b7aca4a8f70d137c7ae735516cfcf0a7584fb0f9cd4aceea",
    "docs/GATE2A_RESULT.md": "29bcb089ff2904eb27208632a6fbd2f925eb0adfb52e1c4deec4b2c25de95690",
    "reports/cloud-container-2026-10-01/gate2a_report.json": "38955dc7e66bc2e2fda399470ce0a67fca783e0585020d27821e4cca61f94c79",
    "reports/cloud-container-2026-10-01/GATE2A_REPORT.md": "e51bfaaabff87fbe3675804a4615f48083d0034e518c6c45fa57a8e54f528a85",
    "run_gate2a.py": "9801158304846b87fa475e9f84361e1cb4ce37cc6ad487c176e6eb5c6f7f395e",
    "lab/gate2a_audit.py": "c6afb8fba0294a2a6d04502113baf50ad20cedf3ecd0ec8a884224ec9e69ea98",
    "lab/gate2a_hostfloat.py": "30cdde68b8901df1487d1758454454a944eac9c2493f799ed461caa5e970d7c0",
    "benchmarks/gate2a/henon_heiles.py": "1e1d690f049bc92ad26caad32517db603902eae8d7cdf252e4a5cc1fb0042a7d",
    "tools/render_gate2a.py": "c77b33be3390ce5b53e76107e7d16d7775837d6bda1a7c093dec172c060804c2",
}


@pytest.mark.parametrize("path", sorted(SEALED))
def test_gate2a_file_is_unchanged(path):
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == SEALED[path], f"{path} changed after Gate 2A was sealed"
