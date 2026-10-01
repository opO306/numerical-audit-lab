"""G2B-0: the gala capture adapter only calls gala; it never modifies or monkeypatches it."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "gate2b_capture_gala.py"


def test_adapter_never_assigns_attributes_or_patches():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for sub in ast.walk(t):
                    assert not isinstance(sub, ast.Attribute), f"attribute assignment at line {node.lineno}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("setattr", "delattr", "exec", "eval"), node.func.id
    src = ADAPTER.read_text(encoding="utf-8")
    assert "monkeypatch" not in src.split('"""', 2)[-1]


def test_adapter_does_not_import_lab_code():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"lab", "benchmarks", "numeric_core", "independent_checker", "run_v2", "run_gate2a"}
