"""Missing runtime paths must not prevent verification of packaged ELF bytes."""
import json
from pathlib import Path
import platform
import shutil

import pytest

from runtime_trace.correspondence import AuditError, check
from runtime_trace.tests.test_captured_mutations import load, rehash

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(platform.system() != "Linux", reason="objdump ELF verification requires Linux")


def portable_trace(tmp_path):
    capture, rows = load()
    replacements = {path: f"/unavailable/captured/module-{i}.so" for i, path in enumerate(capture["modules"])}
    capture["modules"] = {replacements[path]: {**module, "path": replacements[path]}
                          for path, module in capture["modules"].items()}
    for row in rows:
        row["module_path"] = replacements[row["module_path"]]
        row["mapping"]["path"] = row["module_path"]
    rehash(capture, rows, tmp_path)


def test_checker_uses_packaged_images_when_all_recorded_paths_are_absent(tmp_path):
    portable_trace(tmp_path)
    try:
        result = check(tmp_path, ROOT)
    except FileNotFoundError as exc:
        pytest.fail(f"checker reopened unavailable provenance path: {exc}")
    assert result["verdict"] == "PASS"
    assert result["record_count"] == 446


def packaged_root(tmp_path):
    root = tmp_path / "package"
    for relative in ["runtime_trace/frozen_binaries", "audit/gate2c1/vendor",
                     "benchmarks/gate2b/fixtures/cloud-2026-10-01"]:
        shutil.copytree(ROOT / relative, root / relative)
    shutil.copy2(ROOT / "audit/gate2c1/machine_mapping.json", root / "audit/gate2c1/machine_mapping.json")
    return root


def test_missing_packaged_libc_fails_closed_even_if_runtime_libc_exists(tmp_path):
    root = packaged_root(tmp_path)
    (root / "runtime_trace/frozen_binaries/libc.so.6").unlink()
    with pytest.raises(AuditError, match="packaged module missing"):
        check(ROOT / "runtime_trace/artifacts/attempt-05", root)


def test_corrupt_packaged_libc_fails_closed_even_if_runtime_libc_exists(tmp_path):
    root = packaged_root(tmp_path)
    image = root / "runtime_trace/frozen_binaries/libc.so.6"
    data = bytearray(image.read_bytes())
    data[-1] ^= 1
    image.write_bytes(data)
    with pytest.raises(AuditError, match="packaged module raw hash"):
        check(ROOT / "runtime_trace/artifacts/attempt-05", root)


def test_unregistered_module_hash_does_not_fall_back_to_runtime_path(tmp_path):
    capture, rows = load()
    path = next(path for path in capture["modules"] if path.endswith("libc.so.6"))
    capture["modules"][path]["sha256"] = "0" * 64
    for row in rows:
        if row["module_path"] == path:
            row["module_sha256"] = "0" * 64
    rehash(capture, rows, tmp_path)
    with pytest.raises(AuditError, match="unpackaged module SHA-256"):
        check(tmp_path, ROOT)


def test_manifest_cannot_escape_package_root(tmp_path):
    root = packaged_root(tmp_path)
    manifest_path = root / "runtime_trace/frozen_binaries/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    libc_hash = "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf"
    manifest["modules"][libc_hash] = "../outside-libc.so.6"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AuditError, match="packaged module path escapes root"):
        check(ROOT / "runtime_trace/artifacts/attempt-05", root)
