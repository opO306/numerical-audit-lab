import copy

import pytest

from runtime_trace.numeric_ir.checker import check
from runtime_trace.numeric_ir.normalization import (
    NormalizationMismatch,
    compare_normalized,
    normalize,
)
from runtime_trace.numeric_ir.translator import translate


def test_normalize_excludes_only_source_and_keeps_full_numeric_graph():
    document = {
        "schema": "runtime-trace-numeric-ir-regular-1step-v1",
        "source": {"diagnostic": {"source_path": "/runtime/address/dependent"}},
        "operations": [{"ir_sequence": 0, "input0_value_id": "v:left"}],
        "values": [
            {
                "value_id": "v:left",
                "producer": {"role": "boundary", "phase": "init"},
                "storage": {"space": "buffer", "name": "q", "byte_offset": 0},
                "source_slices": [],
            }
        ],
    }

    assert normalize(document) == {
        "schema": "runtime-trace-numeric-ir-regular-1step-v1",
        "operations": [{"ir_sequence": 0, "input0_value_id": "v:left"}],
        "values": [
            {
                "value_id": "v:left",
                "producer": {"role": "boundary", "phase": "init"},
                "storage": {"space": "buffer", "name": "q", "byte_offset": 0},
                "source_slices": [],
            }
        ],
    }


def test_compare_normalized_reports_hash_and_counts_but_preserves_inputs():
    old = {
        "schema": "runtime-trace-numeric-ir-regular-1step-v1",
        "source": {"trace_sha256": "old"},
        "operations": [],
        "values": [],
    }
    fresh = copy.deepcopy(old)
    fresh["source"]["trace_sha256"] = "fresh"

    result = compare_normalized(old, fresh)

    assert result == {
        "verdict": "PASS",
        "normalized_numeric_sha256": "2e2b64a210fab0f0c6b2c755b99e4fe08e9b356434401984037d3a155576f1f2",
        "operation_count": 0,
        "value_count": 0,
    }
    assert old["source"]["trace_sha256"] == "old"
    assert fresh["source"]["trace_sha256"] == "fresh"


def test_compare_normalized_rejects_changed_provenance_edge():
    old = {
        "schema": "runtime-trace-numeric-ir-regular-1step-v1",
        "source": {},
        "operations": [],
        "values": [{"value_id": "v:copy", "source_slices": [{"source_offset": 0}]}],
    }
    fresh = copy.deepcopy(old)
    fresh["values"][0]["source_slices"][0]["source_offset"] = 1

    with pytest.raises(NormalizationMismatch, match="normalized Numeric IR mismatch"):
        compare_normalized(old, fresh)


def test_old_then_fresh_are_checked_independently_before_normalized_comparison(
    attempt05, fresh, repo_root
):
    old_ir = translate(attempt05, root=repo_root)
    old_report = check(old_ir, attempt05, root=repo_root)
    assert old_report["verdict"] == "PASS"

    fresh_ir = translate(fresh, root=repo_root)
    fresh_report = check(fresh_ir, fresh, root=repo_root)
    assert fresh_report["verdict"] == "PASS"

    comparison = compare_normalized(old_ir, fresh_ir)
    assert comparison == {
        "verdict": "PASS",
        "normalized_numeric_sha256": "1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2",
        "operation_count": 36,
        "value_count": 254,
    }
    assert old_ir["source"]["trace_sha256"] != fresh_ir["source"]["trace_sha256"]
