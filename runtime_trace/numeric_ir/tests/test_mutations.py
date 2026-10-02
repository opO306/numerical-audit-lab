import copy
import hashlib

import pytest

from runtime_trace.numeric_ir.checker import IRCheckError, check
from runtime_trace.numeric_ir.schema import canonical_json, normalized_document
from runtime_trace.numeric_ir.translator import translate


def _repair_normalized_hash(ir: dict) -> dict:
    ir["source"]["normalized_numeric_sha256"] = hashlib.sha256(
        canonical_json(normalized_document(ir))
    ).hexdigest()
    return ir


def _resequence(ir: dict) -> None:
    for index, operation in enumerate(ir["operations"]):
        operation["ir_sequence"] = index


def _value(ir: dict, value_id: str) -> dict:
    return next(value for value in ir["values"] if value["value_id"] == value_id)


def _operation(ir: dict, trace_sequence: int) -> dict:
    return next(
        operation
        for operation in ir["operations"]
        if operation["trace_sequence"] == trace_sequence
    )


def _delete_operation(ir: dict) -> None:
    del ir["operations"][0]
    _resequence(ir)


def _duplicate_operation(ir: dict) -> None:
    ir["operations"].insert(1, copy.deepcopy(ir["operations"][0]))
    _resequence(ir)


def _reorder_operations(ir: dict) -> None:
    ir["operations"][0], ir["operations"][1] = (
        ir["operations"][1],
        ir["operations"][0],
    )
    _resequence(ir)


def _swap_kind_consistently(ir: dict) -> None:
    operation = ir["operations"][0]
    operation["operation_kind"] = "ADD_BINARY64"
    _value(ir, operation["output_value_id"])["producer"][
        "operation_kind"
    ] = "ADD_BINARY64"


def _change_input_id(ir: dict) -> None:
    ir["operations"][1]["input1_value_id"] = ir["operations"][0][
        "output_value_id"
    ]


def _change_operand_bits_consistently(ir: dict) -> None:
    operation = _operation(ir, 139)
    operation["input1_raw_bits"] = "0x3fd0000000000000"
    _value(ir, operation["input1_value_id"])["raw_bits"] = "0x3fd0000000000000"


def _change_result_bits_consistently(ir: dict) -> None:
    operation = _operation(ir, 139)
    operation["output_raw_bits"] = "0x3f70000000000000"
    _value(ir, operation["output_value_id"])["raw_bits"] = "0x3f70000000000000"


def _change_trace_sequence(ir: dict) -> None:
    ir["operations"][0]["trace_sequence"] = ir["operations"][1]["trace_sequence"]


def _change_elf_address(ir: dict) -> None:
    ir["operations"][0]["elf_address"] += 1


def _change_producer_edge_to_equal_bits(ir: dict) -> None:
    target = _value(ir, "v:r104:arithmetic-source-read")
    replacement = _value(ir, "v:r103:copy")
    part = target["source_slices"][0]
    part["value_id"] = replacement["value_id"]
    part["source_offset"] = 0
    part["source_storage"] = {
        "space": replacement["storage"]["space"],
        "name": replacement["storage"]["name"],
        "byte_offset": replacement["storage"]["byte_offset"],
        "width": part["width"],
    }


def _merge_equal_bit_occurrences(ir: dict) -> None:
    operation = _operation(ir, 107)
    assert operation["input0_raw_bits"] == operation["input1_raw_bits"]
    operation["input1_value_id"] = operation["input0_value_id"]


def _insert_extra_arithmetic(ir: dict) -> None:
    ir["operations"].append(copy.deepcopy(ir["operations"][-1]))
    _resequence(ir)


SEMANTIC_ATTACKS = [
    ("delete", _delete_operation),
    ("duplicate", _duplicate_operation),
    ("reorder", _reorder_operations),
    ("kind-swap", _swap_kind_consistently),
    ("input-id", _change_input_id),
    ("operand-bits", _change_operand_bits_consistently),
    ("result-bits", _change_result_bits_consistently),
    ("trace-sequence", _change_trace_sequence),
    ("elf-address", _change_elf_address),
    ("producer-edge", _change_producer_edge_to_equal_bits),
    ("equal-bit-merge", _merge_equal_bit_occurrences),
    ("extra-arithmetic", _insert_extra_arithmetic),
]


@pytest.mark.parametrize(
    ("attack_name", "mutate"),
    SEMANTIC_ATTACKS,
    ids=[name for name, _ in SEMANTIC_ATTACKS],
)
def test_rehashed_self_consistent_arithmetic_attacks_are_rejected(
    attempt05, repo_root, attack_name, mutate
):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    mutate(attacked)
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError):
        check(attacked, attempt05, root=repo_root)


def test_wrong_destination_byte_lane_is_rejected_after_hash_repair(
    attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    target = _value(attacked, "v:r65:copy")
    part = target["source_slices"][0]
    assert target["raw_bits"] == "0x0000000000000000"
    part["destination_offset"] = 4
    part["destination_storage"]["byte_offset"] += 4
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="value|provenance"):
        check(attacked, attempt05, root=repo_root)


def test_wrong_source_byte_offset_is_rejected_even_when_bytes_are_equal(
    attempt05, repo_root
):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    target = _value(attacked, "v:r101:copy")
    part = target["source_slices"][0]
    assert _value(attacked, part["value_id"])["raw_bits"] == "0x" + "00" * 16
    part["source_offset"] = 8
    part["source_storage"]["byte_offset"] = 8
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="value|provenance"):
        check(attacked, attempt05, root=repo_root)


def test_dangling_provenance_edge_has_dedicated_refusal(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    _value(attacked, "v:r104:arithmetic-source-read")["source_slices"][0][
        "value_id"
    ] = "v:missing"
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="dangling provenance edge"):
        check(attacked, attempt05, root=repo_root)


def test_provenance_cycle_has_dedicated_refusal(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    target = _value(attacked, "v:r60:copy")
    part = target["source_slices"][0]
    part["value_id"] = target["value_id"]
    part["source_offset"] = 0
    part["source_storage"] = copy.deepcopy(target["storage"])
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="provenance cycle"):
        check(attacked, attempt05, root=repo_root)


def test_unregistered_extra_value_is_rejected(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    attacked["values"].append(
        {
            "value_id": "v:rogue:root",
            "producer_kind": "LOAD_BITS",
            "raw_bits": "0x0000000000000000",
            "width": 8,
            "producer": {
                "role": "boundary",
                "phase": "init",
                "boundary": "rogue",
                "trace_sequence": None,
                "operand_index": None,
            },
            "storage": {
                "space": "register",
                "name": "v31",
                "byte_offset": 0,
                "width": 8,
            },
            "source_slices": [],
        }
    )
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="unregistered extra value"):
        check(attacked, attempt05, root=repo_root)


def test_step_linked_state_cannot_be_reset_to_equal_bit_root(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    latent = _value(attacked, "v:boundary:step:latent")
    latent["producer_kind"] = "LOAD_BITS"
    latent["source_slices"] = []
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="value|provenance"):
        check(attacked, attempt05, root=repo_root)


def test_duplicate_producer_identity_is_rejected(attempt05, repo_root):
    candidate = translate(attempt05, root=repo_root)
    attacked = copy.deepcopy(candidate)
    duplicate = copy.deepcopy(attacked["values"][0])
    duplicate["value_id"] = "v:duplicate-id"
    attacked["values"].append(duplicate)
    _repair_normalized_hash(attacked)

    with pytest.raises(IRCheckError, match="duplicate producer identity"):
        check(attacked, attempt05, root=repo_root)
