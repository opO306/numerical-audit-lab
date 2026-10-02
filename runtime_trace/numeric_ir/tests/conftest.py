from pathlib import Path
import json
import shutil

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def attempt05(repo_root: Path) -> Path:
    return repo_root / "runtime_trace" / "artifacts" / "attempt-05"


@pytest.fixture(scope="session")
def fresh(repo_root: Path) -> Path:
    return repo_root / "runtime_trace" / "artifacts" / "closure-fresh-01"


@pytest.fixture
def root_without_mapping(tmp_path: Path, repo_root: Path) -> Path:
    root = tmp_path / "isolated-root"
    manifest_relative = Path("runtime_trace/frozen_binaries/manifest.json")
    manifest = json.loads((repo_root / manifest_relative).read_text())
    (root / manifest_relative).parent.mkdir(parents=True)
    shutil.copy2(repo_root / manifest_relative, root / manifest_relative)
    for relative_text in manifest["modules"].values():
        relative = Path(relative_text)
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / relative, root / relative)
    return root
