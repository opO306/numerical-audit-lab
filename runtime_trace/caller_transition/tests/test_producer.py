import copy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "runtime_trace/caller_transition/artifacts"


@pytest.mark.parametrize(
    ("case", "label"),
    [("audited-attempt-05", "attempt-05"), ("fresh-closure-fresh-01", "closure-fresh-01")],
)
def test_transition_binds_six_terminal_components_and_fresh_roots(case, label):
    transition = json.loads((ARTIFACTS / case / "transition.json").read_text(encoding="utf-8"))
    assert transition["schema"] == "gala-caller-transition-v1"
    assert transition["verdict"] == "PRODUCED"
    assert transition["antecedent"]["label"] == label
    carry = transition["bindings"]["carry"]
    assert [(x["component"], x["byte_offset"]) for x in carry] == [
        ("q", 0), ("q", 8), ("full_v", 0), ("full_v", 8),
        ("latent", 0), ("latent", 8),
    ]
    assert all(x["transformation_class"] == "A_PURE_COPY" for x in carry)
    assert all(x["no_intervening_write"] is True for x in carry)
    assert all("endpoint_memory_value_id" in x for x in carry)
    assert all("form_source_state_id" in x for x in carry)
    assert all(x["old_endpoint_state_binding_present"] for x in carry[:2])
    assert all(x["endpoint_memory_state_id"] is not None for x in carry[:2])
    assert all(not x["old_endpoint_state_binding_present"] for x in carry[2:])
    assert all(x["endpoint_memory_state_id"] is None for x in carry[2:])
    assert transition["bindings"]["gradient"]["root_kind"] == "FRESH_EXACT_ZERO"
    assert transition["bindings"]["time"]["root_kind"] == "FRESH_SCHEDULE_LOAD"
    assert transition["bindings"]["dt"]["provenance_kind"] == "ACTUAL_CALL_ARGUMENT"
    assert transition["native_execution_has_form_objects"] is False
    assert transition["second_step_body_executed"] is False
    assert transition["producer"]["source_sha256"] == hashlib.sha256(
        (ROOT / "runtime_trace/caller_transition/producer.py").read_bytes()
    ).hexdigest()
    assert transition["producer"]["capture_contract_sha256"] == hashlib.sha256(
        (ROOT / "runtime_trace/caller_transition/capture_contract.py").read_bytes()
    ).hexdigest()


def test_producer_refuses_missing_caller_record(tmp_path):
    from runtime_trace.caller_transition.producer import ProducerRefused, produce

    source = ARTIFACTS / "audited-attempt-05"
    broken = tmp_path / "broken"
    broken.mkdir()
    for name in ["capture.json", "caller_trace.jsonl"]:
        (broken / name).write_bytes((source / name).read_bytes())
    rows = (broken / "caller_trace.jsonl").read_text().splitlines()
    (broken / "caller_trace.jsonl").write_text("\n".join(rows[:-1]) + "\n")
    with pytest.raises(ProducerRefused, match="trace hash|record count"):
        produce(broken, "attempt-05", tmp_path / "out.json", root=ROOT)


def test_producer_refuses_unknown_write_semantics(tmp_path):
    from runtime_trace.caller_transition.producer import ProducerRefused, produce

    source = ARTIFACTS / "audited-attempt-05"
    broken = tmp_path / "broken"
    broken.mkdir()
    capture = json.loads((source / "capture.json").read_text())
    capture["unknown_effects_refused"] = False
    (broken / "capture.json").write_text(json.dumps(capture))
    (broken / "caller_trace.jsonl").write_bytes((source / "caller_trace.jsonl").read_bytes())
    with pytest.raises(ProducerRefused, match="unknown effects"):
        produce(broken, "attempt-05", tmp_path / "out.json", root=ROOT)


def test_producer_publication_is_exclusive(tmp_path):
    from runtime_trace.caller_transition.producer import produce

    output = tmp_path / "transition.json"
    output.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        produce(ARTIFACTS / "audited-attempt-05", "attempt-05", output, root=ROOT)
    assert output.read_text(encoding="utf-8") == "preserve"


def test_existing_summary_refuses_before_partial_transition_publication(tmp_path):
    from runtime_trace.caller_transition.producer import produce

    output = tmp_path / "transition.json"
    summary = tmp_path / "summary.json"
    summary.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        produce(ARTIFACTS / "audited-attempt-05", "attempt-05", output, root=ROOT)
    assert not output.exists()
    assert summary.read_text(encoding="utf-8") == "preserve"
