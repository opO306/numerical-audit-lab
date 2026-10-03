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
    transition = json.loads(
        (ARTIFACTS / "producer-fix-round1" / case / "transition.json").read_text(encoding="utf-8")
    )
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
    assert transition["antecedent"]["capture_label"] == label
    assert transition["antecedent"]["requested_label_matches_capture"] is True
    pointer_identity = transition["bindings"]["pointer_identity"]
    assert set(pointer_identity) == {"q", "full_v", "latent", "gradient"}
    assert all(item["first_step_address"] == item["second_step_address"]
               for item in pointer_identity.values())
    assert all(item["same_memory_region"] is True for item in pointer_identity.values())


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


def _mutated_evidence(tmp_path, mutate):
    source = ARTIFACTS / "audited-attempt-05"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    capture = json.loads((source / "capture.json").read_text(encoding="utf-8"))
    mutate(capture)
    (evidence / "capture.json").write_text(json.dumps(capture), encoding="utf-8")
    (evidence / "caller_trace.jsonl").write_bytes((source / "caller_trace.jsonl").read_bytes())
    return evidence


def test_producer_refuses_capture_antecedent_label_mismatch(tmp_path):
    from runtime_trace.caller_transition.producer import ProducerRefused, produce

    evidence = _mutated_evidence(
        tmp_path, lambda capture: capture.__setitem__("antecedent_label", "closure-fresh-01")
    )
    with pytest.raises(ProducerRefused, match="capture antecedent label"):
        produce(evidence, "attempt-05", tmp_path / "transition.json", root=ROOT)


@pytest.mark.parametrize("component", ["q", "full_v", "latent"])
def test_producer_refuses_rebound_carried_pointer(tmp_path, component):
    from runtime_trace.caller_transition.producer import ProducerRefused, produce

    def mutate(capture):
        capture["second_step_entry"]["abi"]["pointers"][component] += 4096

    evidence = _mutated_evidence(tmp_path, mutate)
    with pytest.raises(ProducerRefused, match=rf"second-entry {component} pointer identity"):
        produce(evidence, "attempt-05", tmp_path / "transition.json", root=ROOT)


def test_producer_refuses_rebound_gradient_pointer(tmp_path):
    from runtime_trace.caller_transition.producer import ProducerRefused, produce

    def mutate(capture):
        capture["second_step_entry"]["abi"]["pointers"]["gradient"] += 4096

    evidence = _mutated_evidence(tmp_path, mutate)
    with pytest.raises(ProducerRefused, match="second-entry gradient pointer identity"):
        produce(evidence, "attempt-05", tmp_path / "transition.json", root=ROOT)


def test_fresh_producer_output_records_both_pointer_boundaries(tmp_path):
    from runtime_trace.caller_transition.producer import produce

    output = tmp_path / "transition.json"
    transition = produce(ARTIFACTS / "audited-attempt-05", "attempt-05", output, root=ROOT)
    pointers = transition["bindings"]["pointer_identity"]
    assert set(pointers) == {"q", "full_v", "latent", "gradient"}
    assert all(item["first_step_address"] == item["second_step_address"] for item in pointers.values())
    assert all(item["same_memory_region"] is True for item in pointers.values())
    assert transition["antecedent"]["capture_label"] == "attempt-05"
    assert transition["antecedent"]["requested_label_matches_capture"] is True
    assert transition["producer"]["source_sha256"] == hashlib.sha256(
        (ROOT / "runtime_trace/caller_transition/producer.py").read_bytes()
    ).hexdigest()
