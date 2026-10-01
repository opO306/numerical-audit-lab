"""Copied files must still be what PROVENANCE.json says they are.

A Lab-side change to a copied file must be listed in lab_modifications;
silently drifting copies fail here.
"""
import hashlib
import json
from pathlib import Path

from numeric_core import IMPLEMENTATION_DIGEST

ROOT = Path(__file__).resolve().parents[1]
PROV = json.loads((ROOT / "PROVENANCE.json").read_text(encoding="utf-8"))


def _h(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_record_names_a_clean_source_commit():
    assert PROV["source_repository"] == "opO306/success-is-mother-of-failure"
    assert len(PROV["source_commit"]) == 40 and PROV["source_worktree_clean"] is True


def test_verbatim_copies_are_unchanged_unless_declared():
    declared = {m["lab_path"] for m in PROV["lab_modifications"]}
    verbatim = [f for f in PROV["files"] if f["mode"] == "verbatim_copy"]
    assert len(verbatim) == 11
    for f in verbatim:
        if f["lab_path"] not in declared:
            assert _h(ROOT / f["lab_path"]) == f["sha256_lf"], f["lab_path"]


def test_adapted_files_match_their_recorded_lab_hash():
    for f in PROV["files"]:
        if f["mode"] == "adapted":
            assert _h(ROOT / f["lab_path"]) == f["lab_sha256_lf"], f["lab_path"]


def test_calculator_fingerprint_equals_the_one_in_a_at_copy_time():
    assert IMPLEMENTATION_DIGEST == PROV["numeric_core_implementation_digest"]
