import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from runtime_trace.regular_2step.acquire import (
    AcquisitionRefused,
    SOURCE_PATHS,
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
    compare,
    compare_pair,
    compare_step_structures,
    normalize_decoded_instruction,
    validate_receipt_files,
)


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "runtime_trace/regular_2step/artifacts"


def _canonical_file(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def _repair_seal(directory):
    seal_path = directory / "acquisition_seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    for name in seal["sealed_files"]:
        seal["sealed_files"][name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    _canonical_file(seal_path, seal)


def _repaired_copy(tmp_path, case="known"):
    destination = tmp_path / case
    shutil.copytree(ARTIFACTS / f"{case}-03", destination)
    return destination


def _rewrite_trace_chain(directory, mutate):
    rows = [json.loads(line) for line in (directory / "trace.jsonl").read_text(
        encoding="utf-8").splitlines()]
    mutate(rows)
    chain = "0" * 64
    with (directory / "trace.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            unsigned = {key: value for key, value in row.items() if key != "chain"}
            chain = hashlib.sha256(bytes.fromhex(chain) + json.dumps(
                unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            row["chain"] = chain
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    capture["trace_sha256"] = hashlib.sha256((directory / "trace.jsonl").read_bytes()).hexdigest()
    capture["final_chain"] = chain
    acquisition_id = hashlib.sha256((json.dumps({"case": capture["case"],
        "process_identity": capture["process_identity"],
        "trace_sha256": capture["trace_sha256"]}, sort_keys=True,
        separators=(",", ":")) + "\n").encode()).hexdigest()
    capture["acquisition_id"] = acquisition_id
    capture["process_local_handoff"]["from_acquisition_id"] = acquisition_id
    capture["process_local_handoff"]["to_acquisition_id"] = acquisition_id
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    seal_path = directory / "acquisition_seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["acquisition_id"] = acquisition_id
    _canonical_file(seal_path, seal)


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
        "regions": [{"occurrence": "step2", "end_state": {
            "q": bits["q"], "full_v": bits["full_v"]}}],
        "process_local_handoff": {
            "from_acquisition_id": "acq-good",
            "to_acquisition_id": "acq-good",
            "from_occurrence": "step1-return",
            "to_occurrence": "step2-entry",
            "same_process": True,
            "roles": {name: {"from_bits": value, "to_bits": value, "equal": True,
                              "from_pointer": index, "to_pointer": index}
                      for index, (name, value) in enumerate(bits.items(), 1)},
            "gradient_boundary": {"pointer": 4, "step1_pointer": 4,
                "from_bits": ["0x0000000000000005", "0x0000000000000006"],
                "to_bits": ["0x0000000000000000"] * 2, "exact_zero": True,
                "caller_reset_write_required": True,
                "entry_stack_observation": {"status": "OK", "timing": "FUNCTION_ENTRY",
                    "size": 8, "bytes_hex": (4).to_bytes(8, "little").hex()}},
        },
    }


def test_harness_requires_normal_completion_and_two_observed_native_calls():
    capture = _valid_capture()
    harness = {"orbit": "regular", "n_steps": 1, "dt_bits": "0x3f90000000000000",
               "output_bits": ["0x0000000000000001", "0x0000000000000002",
                               "0x0000000000000003", "0x0000000000000004"]}
    check_harness_output(harness, capture)
    capture["harness_binding"]["executed_native_step_calls"] = 1
    with pytest.raises(StructureRefused, match="two observed native step calls"):
        check_harness_output(harness, capture)


def test_harness_rejects_malformed_inherited_metadata_receipt():
    capture = _valid_capture()
    capture["harness_binding"]["inherited_stale_n_steps_metadata"] = False
    harness = {"orbit": "regular", "n_steps": 1, "dt_bits": "0x3f90000000000000",
               "output_bits": ["0x0000000000000001", "0x0000000000000002",
                               "0x0000000000000003", "0x0000000000000004"]}
    with pytest.raises(StructureRefused, match="stale inherited metadata"):
        check_harness_output(harness, capture)


def test_receipt_rejects_altered_sealed_file(tmp_path: Path):
    payload = b"actual trace\n"
    for name in ["trace.jsonl", "capture.json", "execution.json", "source_pinset.json",
                 "harness_output.json", "gdb.log"]:
        (tmp_path / name).write_bytes(payload)
    seal = {
        "schema": "regular-2step-acquisition-seal-v1",
        "acquisition_id": "test",
        "sealed_files": {name: hashlib.sha256(payload).hexdigest() for name in
                         ["trace.jsonl", "capture.json", "execution.json", "source_pinset.json",
                          "harness_output.json", "gdb.log"]},
        "sealed_file_name_set": sorted(["trace.jsonl", "capture.json", "execution.json",
                                        "source_pinset.json", "harness_output.json", "gdb.log"]),
        "final_required_file_name_set": sorted(["trace.jsonl", "capture.json", "execution.json",
            "source_pinset.json", "harness_output.json", "gdb.log", "acquisition_seal.json",
            "structure_report.json"]),
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
        "gradient": ["0x0000000000000000", "0x0000000000000000"],
    }
    capture = {
        "acquisition_id": "new-acq",
        "process_identity": {"linux_boot_id": "boot", "pid": 20,
                             "proc_stat_start_time_ticks": 200},
        "regions": [{"occurrence": "init"}, {"occurrence": "step1"},
                    {"occurrence": "step2", "start_state": role_bits,
                     "pointers": {"gradient": 0x1000},
                     "entry_stack_observations": {"gradient_pointer": {
                         "status": "OK", "timing": "FUNCTION_ENTRY", "size": 8,
                         "bytes_hex": (0x1000).to_bytes(8, "little").hex()}},
                     "t_bits": "0x7", "dt_bits": "0x8"}],
    }
    antecedent = {
        "schema": "gala-caller-transition-capture-v2",
        "verdict": "CONTROLLED_STOP",
        "process_identity": {"linux_boot_id": "boot", "pid": 10,
                             "proc_stat_start_time_ticks": 100},
        "second_step_entry": {
            "abi": {"component_bits": role_bits,
                    "stack_argument_observations": {"gradient": {"status": "OK"}},
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


@pytest.mark.parametrize("field", ["q", "full_v", "latent", "gradient", "t", "dt"])
def test_repaired_seal_rejects_each_boundary_field_mutation(tmp_path: Path, field):
    directory = _repaired_copy(tmp_path)
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    step2 = capture["regions"][2]
    if field in {"q", "full_v", "latent", "gradient"}:
        step2["start_state"][field][0] = "0x0000000000000001"
    else:
        step2[f"{field}_bits"] = "0x0000000000000001"
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused):
        compare(directory, ROOT)


def test_repaired_seal_rejects_bogus_antecedent_digest(tmp_path: Path):
    directory = _repaired_copy(tmp_path)
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    capture["antecedent_binding"]["antecedent_capture_sha256"] = "0" * 64
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="antecedent capture hash"):
        compare(directory, ROOT)


def test_repaired_seal_rejects_unbound_harness_endpoint(tmp_path: Path):
    directory = _repaired_copy(tmp_path)
    harness_path = directory / "harness_output.json"
    harness = json.loads(harness_path.read_text(encoding="utf-8"))
    harness["output_bits"] = ["0x00000000deadbeef"] * 4
    _canonical_file(harness_path, harness)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="step2 final endpoint"):
        compare(directory, ROOT)


def test_repaired_seal_rejects_shrunk_source_pinset(tmp_path: Path):
    directory = _repaired_copy(tmp_path)
    pin_path = directory / "source_pinset.json"
    pinset = json.loads(pin_path.read_text(encoding="utf-8"))
    only = SOURCE_PATHS[0]
    pinset["files"] = {only: pinset["files"][only]}
    pinset["exact_key_set"] = [only]
    _canonical_file(pin_path, pinset)
    execution_path = directory / "execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["source_pinset_sha256"] = hashlib.sha256(pin_path.read_bytes()).hexdigest()
    execution["source_sha256_before_execution"] = pinset["files"]
    _canonical_file(execution_path, execution)
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    capture["source_pinset_sha256"] = hashlib.sha256(pin_path.read_bytes()).hexdigest()
    capture["execution_sha256"] = hashlib.sha256(execution_path.read_bytes()).hexdigest()
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="source pin exact key set"):
        compare(directory, ROOT)


def test_repaired_seal_rejects_missing_fresh_distinct_binding(tmp_path: Path):
    directory = _repaired_copy(tmp_path, "fresh")
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    capture.pop("distinct_from")
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="fresh distinct-from binding"):
        compare(directory, ROOT)


@pytest.mark.parametrize("mutation,diagnostic", [
    ("runtime_pc", "runtime PC/load base/ELF address"),
    ("pre_rip", "body PRE rip/runtime PC"),
    ("post_rip", "body POST rip/next PC"),
    ("mapping", "body executable mapping membership"),
])
def test_repaired_chain_rejects_row_address_contradictions(tmp_path: Path, mutation, diagnostic):
    directory = _repaired_copy(tmp_path)
    def alter(rows):
        row = rows[200]
        if mutation == "runtime_pc":
            row["runtime_pc"] += 1
        elif mutation == "pre_rip":
            row["pre"]["gpr"]["rip"] = "0x0000000000000001"
        elif mutation == "post_rip":
            row["post"]["gpr"]["rip"] = "0x0000000000000001"
        else:
            row["mapping"]["start"] = row["runtime_pc"] + 1
    _rewrite_trace_chain(directory, alter)
    with pytest.raises(StructureRefused, match=diagnostic):
        compare(directory, ROOT)


def test_repaired_seal_rejects_normal_exit_event_mutation(tmp_path: Path):
    directory = _repaired_copy(tmp_path)
    capture_path, execution_path = directory / "capture.json", directory / "execution.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    capture["gdb_exit_event"]["exit_code"] = 9
    execution["gdb_exit_event"]["exit_code"] = 9
    _canonical_file(execution_path, execution)
    capture["execution_sha256"] = hashlib.sha256(execution_path.read_bytes()).hexdigest()
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="sealed GDB normal exit"):
        compare(directory, ROOT)


def test_authoritative_pair_replay_requires_distinct_known_and_fresh():
    report = compare_pair(ARTIFACTS / "known-03", ARTIFACTS / "fresh-03", ROOT)
    assert report["verdict"] == "PAIR_REUSE_PROVEN"
    assert report["runtime_address_equality_required_across_processes"] is False


@pytest.mark.parametrize("role", ["q", "full_v", "latent"])
@pytest.mark.parametrize("edge", ["step1_endpoint", "handoff_bits", "corridor_bits",
                                   "handoff_pointer"])
def test_repaired_seal_rejects_each_protected_role_join(tmp_path: Path, role, edge):
    directory = _repaired_copy(tmp_path)
    capture_path = directory / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    wrong_bits = ["0x0000000000000001", "0x0000000000000002"]
    handoff = capture["process_local_handoff"]["roles"][role]
    corridor = capture["caller_corridor"]
    if edge == "step1_endpoint":
        capture["regions"][1]["end_state"][role] = wrong_bits
    elif edge == "handoff_bits":
        handoff["from_bits"] = wrong_bits
        handoff["to_bits"] = wrong_bits
    elif edge == "corridor_bits":
        corridor["start_component_bits"][role] = wrong_bits
        corridor["end_component_bits"][role] = wrong_bits
    else:
        handoff["from_pointer"] += 0x1000
        handoff["to_pointer"] += 0x1000
    _canonical_file(capture_path, capture)
    _repair_seal(directory)
    with pytest.raises(StructureRefused, match="protected boundary join"):
        compare(directory, ROOT)
