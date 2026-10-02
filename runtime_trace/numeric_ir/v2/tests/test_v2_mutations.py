from __future__ import annotations

import copy

import pytest


@pytest.fixture(scope="module")
def candidate(audited_ir_path, repo_root):
    from runtime_trace.numeric_ir.v2.adapter import adapt

    return adapt(audited_ir_path, root=repo_root)


def _renumber_v2(operations):
    for sequence, operation in enumerate(operations):
        operation["v2_sequence"] = sequence


def _alternate_same_bits(candidate, operation, operand):
    raw_key = f"{operand}_raw_bits"
    value_key = f"{operand}_value_id"
    state_key = f"{operand}_state_id"
    form_key = f"{operand}_form"
    original_id = operation[value_key]
    for state in candidate["state_bindings"]:
        if (
            state["raw_center_bits"] == operation[raw_key]
            and state["value_id"] != original_id
        ):
            operation[value_key] = state["value_id"]
            operation[state_key] = state["state_id"]
            operation[form_key] = copy.deepcopy(state["form"])
            return
    raise AssertionError("fixture lacks a same-bit distinct dynamic state")


def mutate_add_to_mul(document):
    next(op for op in document["operations"] if op["v2_operation_kind"] == "ADD")[
        "v2_operation_kind"
    ] = "MUL"


def mutate_delete_operation(document):
    del document["operations"][1]
    _renumber_v2(document["operations"])


def mutate_duplicate_operation(document):
    document["operations"].insert(2, copy.deepcopy(document["operations"][1]))
    _renumber_v2(document["operations"])


def mutate_reorder_operations(document):
    document["operations"][0], document["operations"][1] = (
        document["operations"][1],
        document["operations"][0],
    )
    _renumber_v2(document["operations"])


def mutate_swap_operand_identities(document):
    operation = next(
        op for op in document["operations"] if op["input0_value_id"] != op["input1_value_id"]
    )
    for suffix in ("value_id", "state_id", "raw_bits", "form"):
        left, right = f"input0_{suffix}", f"input1_{suffix}"
        operation[left], operation[right] = operation[right], operation[left]


def mutate_same_bits_distinct_dynamic_id(document):
    for operation in document["operations"]:
        try:
            _alternate_same_bits(document, operation, "input0")
            return
        except AssertionError:
            continue
    raise AssertionError("fixture lacks a same-bit distinct identity")


def mutate_result_value_id(document):
    document["operations"][0]["output_value_id"] = document["operations"][1][
        "output_value_id"
    ]


def mutate_operand_bits(document):
    document["operations"][0]["input0_raw_bits"] = "0x0000000000000001"


def mutate_trace_sequence(document):
    document["operations"][0]["trace_sequence"] += 1


def mutate_boundary_copy_as_arithmetic(document):
    boundary = next(
        state
        for state in document["state_bindings"]
        if state["binding_kind"] == "COPY" and state["trace_sequence"] is None
    )
    forged = copy.deepcopy(document["operations"][-1])
    forged["input0_value_id"] = boundary["value_id"]
    forged["input0_state_id"] = boundary["state_id"]
    forged["input0_raw_bits"] = boundary["raw_center_bits"]
    forged["input0_form"] = copy.deepcopy(boundary["form"])
    document["operations"].append(forged)
    _renumber_v2(document["operations"])


def mutate_hide_arithmetic_as_initialization(document):
    removed = document["operations"].pop(0)
    _renumber_v2(document["operations"])
    state = next(
        item
        for item in document["state_bindings"]
        if item["state_id"] == removed["output_state_id"]
    )
    state["binding_kind"] = "LOAD"
    state["producer_ir_sequence"] = None


def mutate_extra_operation(document):
    document["operations"].append(copy.deepcopy(document["operations"][-1]))
    _renumber_v2(document["operations"])


def mutate_state_coefficient(document):
    document["state_bindings"][-1]["form"]["coef"][0] = "0x1.0000000000000p-100"


def mutate_state_box(document):
    document["state_bindings"][-1]["form"]["box"] = "0x1.0000000000000p-100"


def mutate_output_state_link(document):
    document["operations"][0]["output_state_id"] = document["operations"][1][
        "output_state_id"
    ]


def mutate_boundary_classification(document):
    document["boundaries"][0]["classification"] = "CAPTURED_STATE_HANDOFF"


def mutate_hidden_arithmetic_root(document):
    state = next(
        item for item in document["state_bindings"] if item["binding_kind"] == "ARITHMETIC_RESULT"
    )
    state["binding_kind"] = "ZERO"
    state["producer_ir_sequence"] = None


ATTACKS = [
    mutate_add_to_mul,
    mutate_delete_operation,
    mutate_duplicate_operation,
    mutate_reorder_operations,
    mutate_swap_operand_identities,
    mutate_same_bits_distinct_dynamic_id,
    mutate_result_value_id,
    mutate_operand_bits,
    mutate_trace_sequence,
    mutate_boundary_copy_as_arithmetic,
    mutate_hide_arithmetic_as_initialization,
    mutate_extra_operation,
    mutate_state_coefficient,
    mutate_state_box,
    mutate_output_state_link,
    mutate_boundary_classification,
    mutate_hidden_arithmetic_root,
]


@pytest.mark.parametrize("attack", ATTACKS, ids=lambda attack: attack.__name__)
def test_checker_rejects_coordinated_semantic_attack(
    candidate, audited_ir_path, repo_root, attack
):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    attacked = copy.deepcopy(candidate)
    attack(attacked)

    with pytest.raises(V2CheckError):
        check(attacked, audited_ir_path, root=repo_root)


def test_checker_rejects_noncanonical_form_hex(candidate, audited_ir_path, repo_root):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    attacked = copy.deepcopy(candidate)
    attacked["state_bindings"][0]["form"]["box"] = "0X0.0P+0"

    with pytest.raises(V2CheckError, match="form"):
        check(attacked, audited_ir_path, root=repo_root)


def test_checker_rejects_overflowing_form_hex_as_explicit_check_error(
    candidate, audited_ir_path, repo_root
):
    from runtime_trace.numeric_ir.v2.checker import V2CheckError, check

    attacked = copy.deepcopy(candidate)
    attacked["state_bindings"][0]["form"]["box"] = "0x1p+999999"

    with pytest.raises(V2CheckError, match="form"):
        check(attacked, audited_ir_path, root=repo_root)
