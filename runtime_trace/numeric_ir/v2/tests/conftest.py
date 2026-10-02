from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def audited_ir_path(repo_root: Path) -> Path:
    return repo_root / "runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json"


@pytest.fixture(scope="session")
def audited_ir(audited_ir_path: Path) -> dict:
    return json.loads(audited_ir_path.read_text(encoding="utf-8"))


@pytest.fixture
def adapter_api():
    try:
        from runtime_trace.numeric_ir.v2.adapter import (
            AdapterRefused,
            adapt,
            adapt_to_directory,
        )
    except ModuleNotFoundError:
        class MissingAdapter:
            def __iter__(self):
                raise AssertionError("Numeric IR to frozen V2 adapter module is missing")

        return MissingAdapter()
    return AdapterRefused, adapt, adapt_to_directory
