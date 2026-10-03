import copy
import hashlib
import json
from pathlib import Path

import pytest

from runtime_trace.regular_2step.acquire import (
    AcquisitionRefused,
    bind_antecedent,
    definition_only_nodes,
    prove_exact_harness,
    supplemental_required_reads,
)
from runtime_trace.regular_2step.structure import (
    StructureRefused,
    check_harness_output,
    check_process_local_handoff,
    compare_caller_corridor,
    compare_step_structures,
    normalize_decoded_instruction,
    validate_receipt_files,
)


def _row(seq, elf_address, opcode, kind, operand_address=None, post_elf_address=None):
    operands = []
    if operand_address is not None:
        operands.append({
            "kind": "memory", "address": operand_address, "width": 8,
            "access": "read", "raw_bits": "0x0000000000000000",
        })
    return {
        "seq": seq,
        "module_sha256": "a" * 64,
        "elf_address": elf_address,
        "bytes": f"{elf_address & 0xff:02x}",
        "opcode": opcode,
        "kind": kind,
        "operands": operands,
        "post_elf_address": post_elf_address,
    }


def _regions():
    common = {"q": 0x1000, "full_v": 0x2000, "latent": 0x3000, "gradient": 0x4000}
    return ({"occurrence": "step1", "pointers": common},
            {"occurrence": "step2", "pointers": {k: v + 0x10000 for k, v in common.items()}})


def _matching_rows():
    first_region, second_region = _regions()
    first = [
        _row(10, 0x101, "movsd", "MOVE", first_region["pointers"]["q"]),
        _row(11, 0x102, "addsd", "ADD", first_region["pointers"]["full_v"] + 8),
        _row(12, 0x103, "jne", "CONTROL", post_elf_address=0x105),
    ]
    second = copy.deepcopy(first)
    for index, row in enumerate(second):
        row["seq"] += 100
        if row["operands"]:
            role = "q" if index == 0 else "full_v"
            offset = 0 if index == 0 else 8
            row["operands"][0]["address"] = second_region["pointers"][role] + offset
    return first, second, first_region, second_region


def _valid_capture():
    bits = {
        "q": ["0x0000000000000001", "0x0000000000000002"],
        "full_v": ["0x0000000000000003", "0x0000000000000004"],
        "latent": ["0x0000000000000005", "0x0000000000000006"],
    }
    return {
        "acquisition_id": "acq-good",
        "verdict": "CAPTURED",
        "harness_binding": {
            "exact_one_token_n_steps_change": True,
            "executed_native_step_calls": 2,
            "harness_completed_normally": True,
            "inherited_stale_n_steps_metadata": True,
        },
        "process_local_handoff": {
            "from_acquisition_id": "acq-good",
            "to_acquisition_id": "acq-good",
            "from_occurrence": "step1-return",
            "to_occurrence": "step2-entry",
            "same_process": True,
            "roles": {name: {"from_bits": value, "to_bits": value, "equal": True}
                      for name, value in bits.items()},
        },
    }


def test_harness_requires_normal_completion_and_two_observed_native_calls():
    capture = _valid_capture()
    harness = {"orbit": "regular", "n_steps": 1, "dt_bits": "0x3f90000000000000",
               "output_bits": ["0x0"] * 4}
    check_harness_output(harness, capture)
    capture["harness_binding"]["executed_native_step_calls"] = 1
    with pytest.raises(StructureRefused, match="two observed native step calls"):
        check_harness_output(harness, capture)


def test_harness_rejects_malformed_inherited_metadata_receipt():
    capture = _valid_capture()
    capture["harness_binding"]["inherited_stale_n_steps_metadata"] = False
    harness = {"orbit": "regular", "n_steps": 1, "dt_bits": "0x3f90000000000000",
               "output_bits": ["0x0"] * 4}
    with pytest.raises(StructureRefused, match="stale inherited metadata"):
        check_harness_output(harness, capture)


def test_receipt_rejects_altered_sealed_file(tmp_path: Path):
    payload = b"actual trace\n"
    (tmp_path / "trace.jsonl").write_bytes(payload)
    seal = {
        "schema": "regular-2step-acquisition-seal-v1",
        "sealed_files": {"trace.jsonl": hashlib.sha256(payload).hexdigest()},
    }
    (tmp_path / "acquisition_seal.json").write_text(json.dumps(seal), encoding="utf-8")
    validate_receipt_files(tmp_path)
    (tmp_path / "trace.jsonl").write_bytes(b"altered trace\n")
    with pytest.raises(StructureRefused, match="sealed file hash"):
        validate_receipt_files(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        ("instruction", "instruction/byte sequence"),
        ("order", "instruction/byte sequence"),
        ("control", "control-flow sequence"),
        ("role", "memory-role topology"),
    ],
)
def test_structure_rejects_instruction_order_control_and_role_mutations(mutation, diagnostic):
    first, second, first_region, second_region = _matching_rows()
    assert compare_step_structures(first, second, first_region, second_region)["reusable"] is True
    if mutation == "instruction":
        second[0]["bytes"] = "ff"
    elif mutation == "order":
        second[0], second[1] = second[1], second[0]
    elif mutation == "control":
        second[2]["post_elf_address"] = 0x106
    else:
        second[0]["operands"][0]["address"] = second_region["pointers"]["gradient"]
    with pytest.raises(StructureRefused, match=diagnostic):
        compare_step_structures(first, second, first_region, second_region)


def test_equal_bits_cannot_hide_cross_acquisition_entry_binding():
    capture = _valid_capture()
    check_process_local_handoff(capture)
    capture["process_local_handoff"]["to_acquisition_id"] = "acq-other"
    with pytest.raises(StructureRefused, match="cross-acquisition"):
        check_process_local_handoff(capture)


def test_exact_harness_proof_accepts_only_the_one_call_token_change(tmp_path: Path):
    runtime = tmp_path / "runtime_trace"
    runtime.mkdir()
    old = b"prefix n_steps=1 suffix n_steps metadata=1\n"
    (runtime / "harness.py").write_bytes(old)
    (runtime / "harness_nsteps2.py").write_bytes(old.replace(b"n_steps=1", b"n_steps=2", 1))
    proof = prove_exact_harness(tmp_path)
    assert proof["replacement_count"] == 1
    assert proof["all_other_bytes_identical"] is True
    (runtime / "harness_nsteps2.py").write_bytes(old.replace(b"n_steps=1", b"n_steps=2", 1) + b"changed")
    with pytest.raises(AcquisitionRefused, match="exact one-token"):
        prove_exact_harness(tmp_path)


def test_antecedent_binding_uses_roles_bits_and_provenance_without_continuation():
    role_bits = {
        "q": ["0x1", "0x2"],
        "full_v": ["0x3", "0x4"],
        "latent": ["0x5", "0x6"],
    }
    capture = {
        "acquisition_id": "new-acq",
        "process_identity": {"linux_boot_id": "boot", "pid": 20,
                             "proc_stat_start_time_ticks": 200},
        "regions": [{"occurrence": "init"}, {"occurrence": "step1"},
                    {"occurrence": "step2", "start_state": role_bits,
                     "t_bits": "0x7", "dt_bits": "0x8"}],
    }
    antecedent = {
        "schema": "gala-caller-transition-capture-v2",
        "verdict": "CONTROLLED_STOP",
        "process_identity": {"linux_boot_id": "boot", "pid": 10,
                             "proc_stat_start_time_ticks": 100},
        "second_step_entry": {
            "abi": {"component_bits": {**role_bits, "gradient": ["0x0", "0x0"]},
                    "t_bits": "0x7", "dt_bits": "0x8"},
            "argument_sources": {
                "t": {"source_bits": "0x7", "instruction_sequence": 1},
                "dt": {"source_bits": "0x8", "instruction_sequence": 2},
            },
        },
    }
    result = bind_antecedent(capture, antecedent, Path("old/capture.json"))
    assert result["old_capture_continuation_claimed"] is False
    assert result["binding_basis"] == ["logical_role", "component_bits", "argument_provenance"]
    assert all(item["equal"] for item in result["roles"].values())
    altered = copy.deepcopy(antecedent)
    altered["second_step_entry"]["abi"]["component_bits"]["q"][0] = "0xffff"
    with pytest.raises(AcquisitionRefused, match="antecedent role bits"):
        bind_antecedent(capture, altered, Path("old/capture.json"))


def test_definition_only_loader_keeps_path_setup_and_class_but_excludes_execution():
    source = '''"""doc"""\nimport sys\nROOT = "root"\nsys.path.insert(0, ROOT)\nclass Capture:\n    pass\ngdb.execute("run")\n'''
    nodes = definition_only_nodes(source)
    rendered = [type(node).__name__ for node in nodes]
    assert rendered == ["Expr", "Import", "Assign", "Expr", "ClassDef"]


def test_supplemental_reads_accept_only_pinned_two_register_imul_site():
    registers = {"r14": 2, "rsi": 3, "rbp": 0x1000, "rax": 1}
    pinned = {"module_sha256": "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
              "elf_address": 0x35418, "bytes": "490faff6"}
    assert supplemental_required_reads("imul   %r14,%rsi", registers, 0x35418, 4, pinned) == []
    with pytest.raises(AcquisitionRefused, match="unsupported supplemental"):
        supplemental_required_reads("imul   0x8(%rbp),%rsi", registers, 0x35418, 4, pinned)
    wrong_site = {**pinned, "elf_address": 0x35419}
    with pytest.raises(AcquisitionRefused, match="unsupported supplemental"):
        supplemental_required_reads("imul   %r14,%rsi", registers, 0x35418, 4, wrong_site)


def test_supplemental_scalar_reads_capture_only_explicit_binary64_memory_source():
    registers = {"rbp": 0x1000, "rax": 2}
    site = {"module_sha256": "a" * 64, "elf_address": 1, "bytes": "00"}
    assert supplemental_required_reads(
        "mulsd  0x8(%rbp,%rax,8),%xmm1", registers, 0x2000, 5, site
    ) == [{"address": 0x1018, "size": 8, "kind": "EXPLICIT", "operand": "0x8(%rbp,%rax,8)"}]
    assert supplemental_required_reads("addsd  %xmm0,%xmm1", registers, 0x2000, 4, site) == []
    with pytest.raises(AcquisitionRefused, match="unsupported supplemental"):
        supplemental_required_reads("mul (%rbp)", registers, 0x2000, 3, site)


def test_independent_decode_normalizes_runtime_control_target_to_elf_address():
    load_base = 0x7FFFD5B11000
    assert normalize_decoded_instruction(
        "je 0x7fffd5b2dbc2 <symbol+370 at source.cpp:2282>", load_base
    ) == "je 1cbc2"
    assert normalize_decoded_instruction("je 1cbc2", 0) == "je 1cbc2"


def _caller_row(address=0x9000, changed=True):
    return {
        "schema": "gala-caller-transition-instruction-v2",
        "module_sha256": "b" * 64,
        "elf_address": 0x123,
        "instruction_bytes": "e800000000",
        "assembly": "call 0x123",
        "pre_memory_observations": [
            {"kind": "ABI_STACK_ARGUMENT", "size": 8, "operand": "(%rsp)",
             "address": 0x8000, "bytes_hex": "00" * 8, "status": "OK",
             "timing": "PRE_INSTRUCTION"}
        ],
        "possible_memory_writes": [
            {"kind": "CALL_STACK", "size": 8, "address": address,
             "before_bits": "0x0000000000000000",
             "after_bits": "0x0000000000000001" if changed else "0x0000000000000000",
             "value_changed": changed}
        ],
    }


def test_caller_corridor_checks_effect_equivalence_same_value_count_and_no_overlap():
    old = [_caller_row()]
    new = [copy.deepcopy(old[0])]
    result = compare_caller_corridor(new, old, {"q": (0x1000, 0x1010)})
    assert result["equivalent"] is True
    assert result["protected_write_overlaps"] == []
    new[0]["possible_memory_writes"][0]["value_changed"] = False
    with pytest.raises(StructureRefused, match="caller corridor effect sequence"):
        compare_caller_corridor(new, old, {"q": (0x1000, 0x1010)})


def test_caller_corridor_refuses_any_component_write_even_same_value():
    old = [_caller_row(changed=False)]
    new = [_caller_row(address=0x1008, changed=False)]
    with pytest.raises(StructureRefused, match="protected component overlap"):
        compare_caller_corridor(new, old, {"q": (0x1000, 0x1010)})
