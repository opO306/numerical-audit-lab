from __future__ import annotations

import copy

import pytest


@pytest.fixture(scope="module")
def old_and_fresh(repo_root):
    from runtime_trace.numeric_ir.v2.adapter import adapt

    base = repo_root / "runtime_trace/numeric_ir/artifacts"
    return (
        adapt(base / "attempt-05/numeric_ir.json", root=repo_root),
        adapt(base / "closure-fresh-01/numeric_ir.json", root=repo_root),
    )


def test_normalized_audited_old_and_fresh_are_exactly_equal(old_and_fresh, repo_root):
    from runtime_trace.numeric_ir.v2.checker import check
    from runtime_trace.numeric_ir.v2.normalization import compare_normalized

    base = repo_root / "runtime_trace/numeric_ir/artifacts"
    check(old_and_fresh[0], base / "attempt-05/numeric_ir.json", root=repo_root)
    check(old_and_fresh[1], base / "closure-fresh-01/numeric_ir.json", root=repo_root)
    report = compare_normalized(*old_and_fresh)

    assert report["verdict"] == "EQUAL"
    assert len(report["normalized_sha256"]) == 64


def test_normalization_removes_only_source_instance_metadata(old_and_fresh):
    from runtime_trace.numeric_ir.v2.normalization import normalize

    old, fresh = old_and_fresh
    normalized = normalize(old)

    assert "audited_input_label" not in normalized["source"]
    assert "numeric_ir_sha256" not in normalized["source"]
    assert "trace_sha256" not in normalized["source"]["numeric_ir_source"]
    assert "final_chain" not in normalized["source"]["numeric_ir_source"]
    assert "diagnostic" not in normalized["source"]["numeric_ir_source"]
    assert normalized["source"]["numeric_ir_schema"] == old["source"]["numeric_ir_schema"]
    assert normalized["source"]["numeric_ir_source"]["regions"] == old["source"][
        "numeric_ir_source"
    ]["regions"]
    assert normalized["values"] == old["values"]
    assert normalized["state_bindings"] == old["state_bindings"]
    assert normalized["operations"] == old["operations"]
    assert normalized["boundaries"] == old["boundaries"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["values"][0].__setitem__("value_id", "changed"),
        lambda d: d["state_bindings"][0]["form"].__setitem__("box", "0x1.0000000000000p-1"),
        lambda d: d["operations"][0].__setitem__("v2_operation_kind", "ADD"),
        lambda d: d["boundaries"][0].__setitem__("classification", "changed"),
        lambda d: d["source"]["frozen_v2"].__setitem__("lf_sha256", "0" * 64),
    ],
)
def test_compare_reports_mismatch_for_protocol_or_semantic_change(old_and_fresh, mutate):
    from runtime_trace.numeric_ir.v2.normalization import NormalizedMismatch, compare_normalized

    old, fresh = old_and_fresh
    changed = copy.deepcopy(fresh)
    mutate(changed)

    with pytest.raises(NormalizedMismatch):
        compare_normalized(old, changed)


def test_normalize_rejects_bool_integer_confusion(old_and_fresh):
    from runtime_trace.numeric_ir.v2.normalization import NormalizationError, normalize

    changed = copy.deepcopy(old_and_fresh[0])
    changed["source"]["frozen_v2"]["k"] = True

    with pytest.raises(NormalizationError):
        normalize(changed)


def test_normalize_rejects_overflowing_form_hex_as_normalization_error(old_and_fresh):
    from runtime_trace.numeric_ir.v2.normalization import NormalizationError, normalize

    changed = copy.deepcopy(old_and_fresh[0])
    changed["state_bindings"][0]["form"]["box"] = "0x1p+999999"

    with pytest.raises(NormalizationError, match="form"):
        normalize(changed)


def test_normalize_does_not_mutate_input(old_and_fresh):
    from runtime_trace.numeric_ir.v2.normalization import normalize

    original = copy.deepcopy(old_and_fresh[0])
    normalize(old_and_fresh[0])

    assert old_and_fresh[0] == original
