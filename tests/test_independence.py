"""G0-5: no A package anywhere; the checker side never imports the calculator."""
import subprocess
import sys
from pathlib import Path

from lab.independence import ROOT, static_violations


def test_no_violations_in_this_repository():
    assert static_violations() == []


def test_scanner_is_not_vacuous(tmp_path: Path):
    (tmp_path / "lab").mkdir()
    (tmp_path / "lab" / "x.py").write_text("from numeric_core import run\n")
    (tmp_path / "bench.py").write_text("import a_numeric.vm\nfrom c1b1_replay import verify\n")
    found = static_violations(tmp_path)
    assert any("checker side imports the calculator" in f for f in found)
    assert sum("imports A package" in f for f in found) == 2


def test_a_fresh_interpreter_loads_no_a_module():
    code = ("import run_gate0, sys; from lab.independence import loaded_a_modules; "
            "print(loaded_a_modules())")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"
