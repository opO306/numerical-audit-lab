"""G0-5: the Lab must run without A, and the checker side must not lean on the calculator."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Top-level package names of the A repository. None of them may be imported here.
A_PACKAGES = frozenset({"a_numeric", "a_numeric_native", "a_reference", "a_physics_native", "audit", "engine",
                        "c1b1_replay", "worlds", "research_store", "schemas", "tools", "ground_truth"})
CHECKER_DIRS = ("independent_checker", "lab")
CALCULATOR = "numeric_core"


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def static_violations(root: Path = ROOT) -> list:
    out = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        for name in _imports(path):
            if name in A_PACKAGES:
                out.append(f"{rel}: imports A package {name}")
            if rel.parts[0] in CHECKER_DIRS and name == CALCULATOR:
                out.append(f"{rel}: checker side imports the calculator")
    return out


def loaded_a_modules() -> list:
    return sorted(m for m in sys.modules if m.split(".")[0] in A_PACKAGES)
