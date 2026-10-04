import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from independent_checker.c1b1.contracts import Grid, Ratio, DriftInput, SPEC_SHA256, LabRefusal
from independent_checker.c1b1 import exact_slow, exact_fast

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "independent_checker/c1b1"


def test_manifest_pinned_bytes_and_semantics():
    manifest = PACKAGE / "semantic_manifest_v1.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == SPEC_SHA256
    assert (PACKAGE / "semantic_manifest_v1.sha256").read_text().split()[0] == SPEC_SHA256
    spec = json.loads(manifest.read_text())
    assert spec["owner"] == "numerical-audit-lab" and spec["default_path"] == "exact_slow"
    assert spec["canonical_candidate_binding"]["physical_domain_verified"] is False
    assert spec["specification_provenance"]["implementation_fingerprint_reused"] is False


def test_no_arithmetic_dependency_on_other_path_or_numeric_core():
    for filename, forbidden in (("exact_slow.py", {"exact_fast", "numeric_core"}),
                                ("exact_fast.py", {"exact_slow", "numeric_core", "fractions"})):
        tree = ast.parse((PACKAGE / filename).read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not forbidden.intersection(imports)
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id in {"eval", "exec", "__import__"} for n in ast.walk(tree))


def test_fresh_runtime_no_original_or_numeric_core_access(tmp_path):
    script = r'''
import sys
forbidden = {'a_numeric','a_reference','c1b1_replay','numeric_core','engine','audit','a_physics_native'}
def hook(event,args):
    if event == 'import' and args[0].split('.')[0] in forbidden:
        raise AssertionError('forbidden runtime import')
    if event == 'open' and isinstance(args[0], (str,bytes)):
        name = str(args[0]).lower()
        if 'success-is-mother-of-failure' in name or '성공은 실패의 어머니' in name:
            raise AssertionError('original runtime file access')
sys.addaudithook(hook)
try:
    open('C:/Users/zun24/성공은 실패의 어머니/unread-original.py')
except AssertionError:
    pass
else:
    raise AssertionError('file-access guard did not fire')
try:
    __import__('numeric_core')
except AssertionError:
    pass
else:
    raise AssertionError('import guard did not fire')
from independent_checker.c1b1 import contracts,exact_slow,exact_fast,exact_geometry,compare,claim_adapter
c=contracts
r=c.DriftInput(c.Grid(8,0),c.Grid(8,0),(2,0,0),(0,0,0),(0,0,0),(0,0,0),c.Ratio(1,1),c.Ratio(1,1),c.Ratio(0,1))
assert compare.compare_drift(r,c.Ratio(1,1)).match
k=c.KickInput(c.Grid(8,0),c.Grid(8,0),(0,0,0),(0,0,0),(1,0,0))
assert compare.compare_kick(k).match
assert not any(x.split('.')[0] in forbidden for x in sys.modules)
print('PASS')
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "PASS"


def test_manifest_tamper_fails_in_isolated_copy(tmp_path):
    target = tmp_path / "isolated"
    target.mkdir()
    (target / "contracts.py").write_bytes((PACKAGE / "contracts.py").read_bytes())
    (target / "semantic_manifest_v1.json").write_bytes((PACKAGE / "semantic_manifest_v1.json").read_bytes() + b" ")
    result = subprocess.run([sys.executable, "-c", "import contracts"], cwd=target, capture_output=True, text=True)
    assert result.returncode != 0 and "manifest byte hash mismatch" in result.stderr


def test_grid_metadata_lookalike_rejected():
    class Lookalike:
        def __eq__(self, other):
            return True
    req = DriftInput(Grid(8, 0), Grid(8, 0), (0, 0, 0), (0, 0, 0),
                     (0, 0, 0), (0, 0, 0), Ratio(1, 1), Ratio(1, 1), Ratio(0, 1))
    for module in (exact_slow, exact_fast):
        with pytest.raises(LabRefusal) as caught:
            module.drift(replace(req, position_grid=Grid(8, 0, kind=Lookalike())))
        assert caught.value.failure.code == "PROFILE_UNSUPPORTED"
