"""Gate 0 closure: the committed report equals the home-PC run except for the closure labels."""
import subprocess
import sys

from lab.independence import ROOT


def test_committed_report_is_equivalent_to_the_home_pc_digest():
    out = subprocess.run([sys.executable, "tools/gate0_digest_equivalence.py"], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    assert "fields that differ    ['benchmark_3', 'open_items']" in out.stdout
