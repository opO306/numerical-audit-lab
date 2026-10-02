"""ASLR must be ignored while changed instruction/numerical bits are rejected."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def comparison_inputs():
    old = ROOT / "runtime_trace/artifacts/attempt-05"
    capture = json.loads((old / "capture.json").read_text())
    rows = [json.loads(line) for line in (old / "trace.jsonl").read_text().splitlines()]
    return rows, capture


def compare(old, fresh, old_capture, fresh_capture):
    # Import inside the test so the red run can state the missing closure check.
    try:
        from runtime_trace.closure_check import compare_traces
    except ImportError:
        pytest.fail("ELF-relative closure comparison is not implemented")
    return compare_traces(old, fresh, old_capture, fresh_capture)


def test_aslr_relocation_is_accepted_without_comparing_runtime_pc():
    rows, capture = comparison_inputs()
    fresh = deepcopy(rows)
    for row in fresh:
        row["runtime_pc"] += 0x100000
        row["module_load_base"] += 0x100000
    result = compare(rows, fresh, capture, deepcopy(capture))
    assert result["instruction_stream_match"] is True
    assert result["scalar_operand_result_bits_match"] is True


@pytest.mark.parametrize("mutation", ["elf_address", "elf_file_offset", "bytes", "module_sha256",
                                     "scalar_operand", "scalar_result", "scalar_post_xmm", "endpoint"])
def test_closure_comparison_rejects_changed_execution_evidence(mutation):
    rows, capture = comparison_inputs()
    fresh, fresh_capture = deepcopy(rows), deepcopy(capture)
    scalar = next(row for row in fresh if row["opcode"] == "mulsd")
    if mutation in {"elf_address", "elf_file_offset"}:
        fresh[0][mutation] += 1
    elif mutation == "bytes":
        fresh[0]["bytes"] = "90"
    elif mutation == "module_sha256":
        fresh[0]["module_sha256"] = "0" * 64
    elif mutation == "scalar_operand":
        scalar["operands"][0]["raw_bits"] = hex(int(scalar["operands"][0]["raw_bits"], 16) ^ 1)
    elif mutation == "scalar_result":
        scalar["result_bits"] = hex(int(scalar["result_bits"], 16) ^ 1)
    elif mutation == "scalar_post_xmm":
        name = scalar["operands"][-1]["register"]
        scalar["post"]["xmm"][name] = hex(int(scalar["post"]["xmm"][name], 16) ^ 1)
    elif mutation == "endpoint":
        fresh_capture["regions"][-1]["end_state"]["q"] = "0x0"
    with pytest.raises(ValueError):
        compare(rows, fresh, capture, fresh_capture)
