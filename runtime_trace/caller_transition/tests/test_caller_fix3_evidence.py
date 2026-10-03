from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runtime_trace.caller_transition.generate_checker_fix3_mutations import generate


ROOT = Path(__file__).resolve().parents[3]
CALLER = ROOT / "runtime_trace" / "caller_transition"
EVIDENCE = CALLER / "artifacts" / "checker" / "fix-round3" / "mutations"
CHECKER_SHA256 = "8c1915ed19e9fb1cefd757d8a2ff8c475193ed581fa272784dabcd89e5e125a4"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_fix3_evidence_covers_retained_names_inputs_and_stages() -> None:
    manifest = json.loads((EVIDENCE / "manifest.json").read_text())
    fix1 = json.loads(
        (CALLER / "artifacts" / "checker" / "fix-round1" / "mutations" / "manifest.json").read_text()
    )
    fix2 = json.loads(
        (CALLER / "artifacts" / "checker" / "fix-round2" / "mutations" / "manifest.json").read_text()
    )
    retained_names = [item["name"] for item in fix1["cases"] + fix2["cases"]]

    assert manifest["all_refused"] is True
    assert manifest["case_count"] == 41
    assert [item["name"] for item in manifest["cases"]] == retained_names
    assert manifest["checker_sha256"] == CHECKER_SHA256 == _sha(CALLER / "checker.py")
    assert manifest["production_trust_override_exposed"] is False
    generator = CALLER / "generate_checker_fix3_mutations.py"
    assert manifest["generator_sha256"] == _sha(generator)
    assert manifest["authoritative_fix2_normal_report_sha256"] == {
        case: _sha(
            CALLER
            / "artifacts"
            / "checker"
            / "fix-round2"
            / case
            / "checker_report.json"
        )
        for case in (
            "audited-attempt-05-readproof-01",
            "fresh-closure-fresh-01-readproof-01",
        )
    }

    source_raw_hashes = manifest["source_raw_sha256"]
    source_raw = CALLER / "artifacts" / manifest["source_case"]
    assert len(source_raw_hashes) == 9
    assert source_raw_hashes == {
        path.name: _sha(path) for path in sorted(source_raw.iterdir()) if path.is_file()
    }

    for item in manifest["cases"]:
        case_dir = EVIDENCE / "cases" / item["name"]
        receipt_path = case_dir / "mutation-receipt.json"
        result_path = case_dir / "result.json"
        assert item["receipt_sha256"] == _sha(receipt_path)
        assert item["result_sha256"] == _sha(result_path)
        receipt = json.loads(receipt_path.read_text())
        result = json.loads(result_path.read_text())
        assert result["verdict"] == "REFUSED"
        assert result["code"] == receipt["expected_refusal_code"] == item["code"]
        assert result["declared_refusal_stage"] == receipt["declared_refusal_stage"]
        assert result["trust_mode"] == receipt["trust_mode"] == item["trust_mode"]
        assert result["actual_input_hashes"] == receipt["actual_input_hashes"]
        assert result["actual_input_hashes"]
        for relative, digest in result["actual_input_hashes"].items():
            assert _sha(case_dir / relative) == digest
        if item["input_kind"] == "RAW_BUNDLE_AND_TRANSITION":
            assert len(result["actual_input_hashes"]) == 10
            assert (case_dir / "input" / "raw" / "caller_trace.jsonl").is_file()
            assert (case_dir / "input" / "transition.json").is_file()
        elif item["input_kind"] == "TRANSITION_ONLY":
            assert list(result["actual_input_hashes"]) == ["input/transition.json"]
            assert receipt["source_raw_sha256"] == source_raw_hashes
        else:
            assert item["input_kind"] == "STRUCTURED_UNIT_FIXTURE"
            assert list(result["actual_input_hashes"]) == ["input/fixture.json"]

    by_name = {item["name"]: item for item in manifest["cases"]}
    assert by_name["public-coherent-repin"]["trust_mode"] == "PUBLIC_RIGID_PRODUCTION"
    assert by_name["public-coherent-repin"]["code"] == "TRUST_PATH"
    assert by_name["unknown-instruction-effect"]["trust_mode"] == "UNIT_CLOSED_DECODER"
    assert by_name["same-bits-wrong-origin-role"]["trust_mode"] == "UNIT_STRUCTURED_FIXTURE"
    assert by_name["dense-deletion-stale-receipts"]["receipt_preflight"] == "REFUSED"
    assert by_name["dense-reorder-stale-receipts"]["receipt_preflight"] == "REFUSED"
    for name in (
        "dense-record-deletion",
        "dense-record-reordering",
        "dense-deletion-fully-repaired",
        "dense-reorder-fully-repaired",
    ):
        assert by_name[name]["receipt_preflight"] == "PASSED"
        assert by_name[name]["code"] == "TRACE_CONTROL_TARGET"


def test_fix3_generator_reproduces_every_committed_byte(tmp_path: Path) -> None:
    reproduced = tmp_path / "mutations"
    generated = generate(reproduced)
    committed = json.loads((EVIDENCE / "manifest.json").read_text())
    assert generated == committed
    assert _file_map(reproduced) == _file_map(EVIDENCE)
