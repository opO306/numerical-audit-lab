"""The independent V2 audit report is preserved byte for byte (docs/V2_PROVENANCE.md)."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = "audit/v2_independent/V2_INDEPENDENT_AUDIT_REPORT.md"
SHA256 = "8746d58cfbcf013550c0226f0cf9db9d657e268ddb1e14d10bc21382180a130d"


def test_audit_report_is_unchanged():
    raw = (ROOT / REPORT).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == SHA256
