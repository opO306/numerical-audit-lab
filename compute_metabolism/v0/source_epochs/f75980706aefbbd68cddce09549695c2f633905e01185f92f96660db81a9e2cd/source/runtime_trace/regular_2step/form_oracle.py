"""Definition-only reuse of the received independent rational/Form audit.

No producer, acquisition, adapter or frozen evaluator imports. The old audit
script's executable top-level case loop is never executed. IEEE result checking
below additionally handles RN-even ties, subnormal/overflow and signed zero.
"""
import ast
import hashlib
import struct
import types
import zipfile
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

ARCHIVE = 'current/numeric_ir_v2_independent_audit_evidence_2026-10-03.zip'
ARCHIVE_SHA = '6fd330347662c535fd80f7b6c9cc80df0532740883e50ea7c88290a1d39419dc'
MEMBER = 'numeric_ir_v2_independent_audit_evidence_2026-10-03/ir_v2_independent_audit.py'
SOURCE_SHA = '92ce8a17bf69edc79086151d12b9fb25b2070a48f14d0afcdeefd5a6548c3be1'


def oracle(root):
    raw = (Path(root) / ARCHIVE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA:
        raise ValueError('independent audit archive identity')
    with zipfile.ZipFile(Path(root) / ARCHIVE) as archive:
        source = archive.read(MEMBER)
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('independent audit source identity')
    return _definitions(source)


@lru_cache(maxsize=1)
def _definitions(source):
    tree = ast.parse(source)
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'results' for t in node.targets):
            break
        body.append(node)
    module = types.ModuleType('regular2step_received_independent_form_audit')
    exec(compile(ast.Module(body=body, type_ignores=[]), MEMBER, 'exec'), module.__dict__)
    return module


def check_ieee(kind, xbits, ybits, zbits):
    """Exact rational arithmetic with binary64 RN-even result comparison."""
    def value(bits):
        u = int(bits, 16)
        exponent, mantissa = (u >> 52) & 2047, u & ((1 << 52) - 1)
        if exponent == 2047:
            raise ValueError('nonfinite raw arithmetic')
        power = -1074 if exponent == 0 else exponent - 1075
        mantissa += (1 << 52) if exponent else 0
        q = Fraction(mantissa) * (Fraction(2) ** power)
        return -q if u >> 63 else q
    x, y = value(xbits), value(ybits)
    if kind == 'ADD_BINARY64':
        q = x + y
    elif kind == 'SUB_BINARY64':
        q = x - y
    elif kind == 'MUL_BINARY64':
        q = x * y
    else:
        raise ValueError('unknown arithmetic kind')
    rounded = float(q)  # CPython Fraction -> binary64 uses round-to-nearest/even.
    expected = int.from_bytes(struct.pack('<d', rounded), 'little')
    if q == 0:
        sx, sy = int(xbits, 16) >> 63, int(ybits, 16) >> 63
        negative = (sx ^ sy) if kind == 'MUL_BINARY64' else (x == y == 0 and sx and (sy ^ (kind == 'SUB_BINARY64')))
        expected = int(bool(negative)) << 63
    if expected != int(zbits, 16):
        raise ValueError('exact IEEE-754 result mismatch')
