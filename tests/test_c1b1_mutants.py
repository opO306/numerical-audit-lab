"""Execute real mutated source copies; agreement alone cannot test shared geometry."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import types
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "independent_checker/c1b1"


def load_copy(directory, name, file=None, edits=()):
    directory.mkdir()
    for item in SOURCE.iterdir():
        if item.suffix in (".py", ".json", ".sha256"):
            shutil.copyfile(item, directory / item.name)
    changed_hash = None
    if file:
        target = directory / file
        text = target.read_text(encoding="utf-8")
        for old, new in edits:
            assert text.count(old) == 1, (file, old)
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")
        compile(text, str(target), "exec")
        changed_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    package = types.ModuleType(name)
    package.__path__ = [str(directory)]
    sys.modules[name] = package
    return {key: importlib.import_module(name + "." + key)
            for key in ("contracts", "exact_fast", "exact_slow", "compare", "exact_geometry")}, changed_hash


def req(modules, **changes):
    from dataclasses import replace
    c = modules["contracts"]
    return replace(c.DriftInput(c.Grid(16, 0), c.Grid(16, 0), (1, 0, 0), (0, 0, 0),
        (1, 0, 0), (0, 0, 0), c.Ratio(1, 1), c.Ratio(1, 1), c.Ratio(1, 2)), **changes)


def scenario(modules, ident):
    c, f, comparator, geometry = (modules[k] for k in ("contracts", "exact_fast", "compare", "exact_geometry"))
    request = req(modules)
    if ident in ("2", "4", "5"):
        request = req(modules, mass_i=c.Ratio(3, 2), dt=c.Ratio(7, 4))
    if ident == "3":
        request = req(modules, momentum_grid=c.Grid(16, 3), p_i=(8, 0, 0), dt=c.Ratio(1, 1))
    if ident in ("1", "2", "3", "4", "5", "6"):
        assert comparator.compare_drift(request).match
    elif ident == "7":
        request = req(modules, p_i=(-1, 0, 0), dt=c.Ratio(1, 4))
        try:
            f.guarded_drift(request, c.Ratio(81, 100))
        except c.LabRefusal as exc:
            assert exc.failure.code == "SEGMENT_INTRUSION"
        else:
            raise AssertionError("rounded endpoint hid intrusion")
    elif ident in ("8", "12"):
        impulse_grid = c.Grid(16, 1) if ident == "12" else c.Grid(16, 0)
        kick = c.KickInput(c.Grid(16, 0), impulse_grid, (2, -3, 1), (5, 4, 0), (1, -1, 0))
        assert comparator.compare_kick(kick).match
    elif ident == "9":
        # Separate delta, position and momentum limits all have dedicated probes.
        a = req(modules, position_grid=c.Grid(3, 0), r_i=(-4, 0, 0), p_i=(4, 0, 0), dt=c.Ratio(1, 1))
        b = req(modules, position_grid=c.Grid(3, 0), r_i=(3, 0, 0), p_i=(1, 0, 0), dt=c.Ratio(1, 1))
        k = c.KickInput(c.Grid(3, 0), c.Grid(3, 0), (-4, 0, 0), (0, 0, 0), (1, 0, 0))
        checks = (comparator.compare_drift(a), comparator.compare_drift(b), comparator.compare_kick(k))
        assert all(check.match for check in checks)
    elif ident == "10":
        request = req(modules, position_grid=c.Grid(3, 0), p_i=(10, 0, 0), p_j=(10, 0, 0), dt=c.Ratio(1, 1))
        assert comparator.compare_drift(request).match
    elif ident == "10_write":
        request = req(modules, dt=c.Ratio(1, 1))
        before = repr(request)
        assert comparator.compare_drift(request).match
        assert repr(request) == before
    elif ident == "11":
        assert comparator.compare_drift(request).match
        assert comparator.compare_drift(req(modules, dt=c.Ratio(1, 3))).match
    elif ident == "geometry_tie":
        result = geometry.evaluate((-1, 1, 0), (1, 1, 0), (1, 0, 0), 1)
        assert not result.segment_intrusion and not result.stored_intrusion
    elif ident == "geometry_tau":
        result = geometry.evaluate((-2, 1, 2), (4, 1, 2), (4, 1, 2), 1)
        assert result.tau.numerator * 3 == result.tau.denominator and result.min_R2 == 5
    elif ident == "geometry_stored":
        result = geometry.evaluate((2, 0, 0), (2, 0, 0), (1, 0, 0), c.Ratio(121, 100))
        assert not result.segment_intrusion and result.stored_intrusion


COEFF = "return a * e, (1 << request.momentum_grid.frac_bits) * b * c"
MUTANTS = [
    ("1", "exact_fast.py", [("return q if q % 2 == 0 else q + 1", "return q + 1 if numerator >= 0 else q")]),
    ("2", "exact_fast.py", [(COEFF, "return a, (1 << request.momentum_grid.frac_bits) * b * c")]),
    ("3", "exact_fast.py", [(COEFF, "return a * e, b * c")]),
    ("4", "exact_fast.py", [(COEFF, "return a * c, (1 << request.momentum_grid.frac_bits) * b * e")]),
    ("5", "exact_fast.py", [(COEFF, "return b * e, (1 << request.momentum_grid.frac_bits) * a * c")]),
    ("6", "exact_fast.py", [("delta = nearest_even_ratio(numerator * scale, denominator)", "delta = nearest_even_ratio(old_r * denominator + numerator * scale, denominator) - old_r")]),
    ("7", "exact_geometry.py", [("q1 = tuple(a - b for a, b in zip(endpoints[:3], endpoints[3:]))", "q1 = tuple(Fraction(a - b, scale) for a, b in zip(result.r_i, result.r_j))")]),
    ("8", "exact_fast.py", [("value = raw - impulse if atom == \"i\" else raw + impulse", "value = raw + impulse if atom == \"i\" else raw - impulse")]),
    ("9", "exact_fast.py", [("if not minimum <= delta <= maximum:", "if False:"),
        ("if updated < minimum or updated > maximum:", "if False:"), ("if not minimum <= value <= maximum:", "if False:")]),
    ("10", "exact_fast.py", [("for atom, positions, momenta, mass in atoms:", "for atom, positions, momenta, mass in reversed(atoms):")]),
    ("10_write", "exact_fast.py", [("stored.append(updated)", "stored.append(updated)\n            object.__setattr__(request, 'r_i', tuple(stored[:3]))")]),
    ("11", "exact_fast.py", [(COEFF, "global _stale_cache\n    if '_stale_cache' not in globals():\n        _stale_cache = (a * e, (1 << request.momentum_grid.frac_bits) * b * c)\n    return _stale_cache")]),
    ("12", "exact_fast.py", [("    validate_kick(request)", "    request = __import__('dataclasses').replace(request, impulse_grid=request.momentum_grid)\n    validate_kick(request)")]),
    ("geometry_tie", "exact_geometry.py", [("minimum < threshold", "minimum <= threshold")]),
    ("geometry_tau", "exact_geometry.py", [("-B / C", "B / C")]),
    ("geometry_stored", "exact_geometry.py", [("stored_R2 < threshold)", "False)")]),
]


@pytest.mark.parametrize("ident,file,edits", MUTANTS, ids=[x[0] for x in MUTANTS])
def test_actual_mutated_source_is_detected(tmp_path, ident, file, edits):
    baseline, _ = load_copy(tmp_path / "baseline", "_c1b1_base_" + ident)
    mutant, digest = load_copy(tmp_path / "mutant", "_c1b1_mutant_" + ident, file, edits)
    try:
        scenario(baseline, ident)  # A failed baseline never counts as detection.
        with pytest.raises(AssertionError):
            scenario(mutant, ident)
        report_path = os.environ.get("C1B1_MUTANT_REPORT")
        if report_path:
            path = Path(report_path)
            rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            rows[ident] = {"source": file, "mutant_sha256": digest, "edits": edits,
                           "baseline": "PASS", "actual_mutant_execution": "DETECTED"}
            path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    finally:
        for key in list(sys.modules):
            if key.startswith(("_c1b1_base_" + ident, "_c1b1_mutant_" + ident)):
                del sys.modules[key]
