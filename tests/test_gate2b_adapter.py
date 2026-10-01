"""G2B-0: the gala capture adapter only calls gala; it never modifies or monkeypatches it."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "gate2b_capture_gala.py"
FORBIDDEN_CALLS = {"setattr", "delattr", "exec", "eval"}


def _gala_aliases(tree) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.asname or a.name.split(".")[0] for a in node.names if a.name.split(".")[0] == "gala"}
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "gala":
            names |= {a.asname or a.name for a in node.names}
    return names


def _root(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def violations(src: str) -> list:
    """Direct attribute assignment anywhere, any assignment into something rooted at a gala name,
    or setattr/delattr/exec/eval."""
    tree = ast.parse(src)
    gala_names = _gala_aliases(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute):
                    out.append(f"line {node.lineno}: assigns an attribute")
                elif _root(t) in gala_names:
                    out.append(f"line {node.lineno}: assigns into gala object {_root(t)}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            out.append(f"line {node.lineno}: calls {node.func.id}")
    return out


def test_adapter_never_assigns_into_gala_or_patches():
    assert violations(ADAPTER.read_text(encoding="utf-8")) == []


def test_the_check_is_not_vacuous():
    bad = ["import gala.integrate as gi\ngi.LeapfrogIntegrator = None\n",
           "import gala.potential as gp\ngp.registry['x'] = 1\n",
           "import gala\nsetattr(gala, 'x', 1)\n",
           "obj = object()\nobj.attr = 1\n"]
    for src in bad:
        assert violations(src), src
    assert violations("d = {}\nd.setdefault('k', {})['n'] = 1\n") == []      # Lab's own dict: allowed


def test_adapter_does_not_import_lab_code():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"lab", "benchmarks", "numeric_core", "independent_checker", "run_v2", "run_gate2a"}
