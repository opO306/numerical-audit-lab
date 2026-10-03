import hashlib
import json
from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "runtime_trace/caller_transition/artifacts"
CASES = [
    ("audited-attempt-05-readproof-01", "attempt-05"),
    ("fresh-closure-fresh-01-readproof-01", "closure-fresh-01"),
]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(case):
    path = ARTIFACTS / case / "caller_trace.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(("case", "label"), CASES)
def test_live_readproof_capture_is_complete_and_stops_before_body(case, label):
    capture = json.loads((ARTIFACTS / case / "capture.json").read_text(encoding="utf-8"))
    execution = json.loads((ARTIFACTS / case / "execution.json").read_text(encoding="utf-8"))
    rows = _rows(case)
    assert capture["schema"] == "gala-caller-transition-capture-v2"
    assert execution["schema"] == "caller-transition-execution-v2"
    assert capture["verdict"] == "CONTROLLED_STOP"
    assert capture["antecedent_label"] == execution["antecedent_label"] == label
    assert capture["record_count"] == len(rows) == 728
    assert capture["counts"] == {
        "rows": 728,
        "pre_memory_observations": 219,
        "pre_memory_observation_failures": 0,
        "possible_memory_writes": 111,
        "same_value_writes": 21,
        "indirect_memory_controls": 16,
        "returns": 23,
        "pops": 30,
        "leaves": 10,
    }
    assert capture["required_memory_observations_complete"] is True
    assert capture["segment_bases_complete"] is True
    assert capture["controlled_stop_receipt"]["second_step_body_instructions_executed"] == 0
    assert execution["pre_memory_observation_failures"] == 0
    assert capture["process_identity"]["pid"] == capture["inferior_pid"]
    assert capture["process_identity"]["proc_stat_start_time_ticks"] > 0
    assert capture["process_identity"]["linux_boot_id"]
    for row in rows:
        assert set(row["pre"]["segment_bases"]) == {"fs_base", "gs_base"}
        assert set(row["post"]["segment_bases"]) == {"fs_base", "gs_base"}
        assert all(item["status"] == "OK" and item["timing"] == "PRE_INSTRUCTION"
                   for item in row["pre_memory_observations"])


@pytest.mark.parametrize(("case", "label"), CASES)
def test_seal_source_receipt_and_module_pinset_are_exact(case, label):
    from runtime_trace.caller_transition.run_acquisition_reads import EXPECTED_MODULES, SOURCE_PATHS

    evidence = ARTIFACTS / case
    seal = json.loads((evidence / "acquisition_seal.json").read_text(encoding="utf-8"))
    execution = json.loads((evidence / "execution.json").read_text(encoding="utf-8"))
    capture = json.loads((evidence / "capture.json").read_text(encoding="utf-8"))
    source = json.loads((evidence / "source_pinset.json").read_text(encoding="utf-8"))
    modules = json.loads((evidence / "module_pinset.json").read_text(encoding="utf-8"))
    expected_files = sorted([
        "caller_trace.jsonl", "capture.json", "execution.json", "first_step_disassembly.txt",
        "gdb.log", "harness_diff.json", "module_pinset.json", "source_pinset.json",
    ])
    assert seal["schema"] == "caller-transition-acquisition-seal-v1"
    assert seal["antecedent_label"] == label
    assert seal["exact_file_name_set"] == expected_files
    assert sorted(path.name for path in evidence.iterdir()) == sorted(expected_files + ["acquisition_seal.json"])
    assert all(_sha(evidence / name) == seal["sealed_files"][name] for name in expected_files)
    assert source["exact_key_set"] == sorted(SOURCE_PATHS)
    assert execution["source_receipt_key_set"] == sorted(SOURCE_PATHS)
    assert execution["source_sha256_before_execution"] == source["files"]
    assert all(_sha(ROOT / path) == digest for path, digest in source["files"].items())
    assert set(modules["modules"]) == EXPECTED_MODULES
    assert set(capture["modules"][path]["sha256"] for path in capture["modules"]) == EXPECTED_MODULES
    assert capture["execution_sha256"] == _sha(evidence / "execution.json")
    assert capture["trace_sha256"] == _sha(evidence / "caller_trace.jsonl")


@pytest.mark.parametrize(("case", "label"), CASES)
def test_raw_sources_cover_control_tls_and_final_abi(case, label):
    rows = _rows(case)
    assert rows[0]["pre_memory_observations"][0]["kind"] == "IMPLICIT_RET"
    assert rows[4]["pre_memory_observations"][0]["kind"] == "INDIRECT_CONTROL"
    assert [rows[sequence]["pre_memory_observations"][0]["size"]
            for sequence in [718, 721, 722, 723, 724, 725, 726]] == [8, 8, 8, 8, 4, 8, 8]
    assert rows[727]["pre_memory_observations"][0]["kind"] == "ABI_STACK_ARGUMENT"
    for sequence in [369, 374, 457]:
        row = rows[sequence]
        assert len(row["possible_memory_writes"]) == 1
        write = row["possible_memory_writes"][0]
        fs_base = int(row["pre"]["segment_bases"]["fs_base"], 16)
        assert write["address"] == fs_base - 8
        assert write["size"] == 8
    for row in rows:
        for observation in row["pre_memory_observations"]:
            if observation["kind"] == "READ_MODIFY_WRITE":
                matching = [write for write in row["possible_memory_writes"]
                            if write["address"] == observation["address"]
                            and write["size"] == observation["size"]]
                assert len(matching) == 1
                assert observation["bytes_hex"] == int(
                    matching[0]["before_bits"], 16
                ).to_bytes(observation["size"], "little").hex()


def _repair_trace_and_wrappers(evidence, mutate):
    from runtime_trace.caller_transition.run_acquisition_reads import canonical

    rows = [json.loads(line) for line in (evidence / "caller_trace.jsonl").read_bytes().splitlines()]
    mutate(rows)
    chain = "0" * 64
    encoded_rows = []
    for row in rows:
        row["previous_chain"] = chain
        payload = {key: value for key, value in row.items() if key != "record_chain"}
        chain = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        row["record_chain"] = chain
        encoded_rows.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
    (evidence / "caller_trace.jsonl").write_text("\n".join(encoded_rows) + "\n", encoding="utf-8")
    capture = json.loads((evidence / "capture.json").read_text(encoding="utf-8"))
    capture["trace_sha256"] = _sha(evidence / "caller_trace.jsonl")
    capture["final_chain"] = chain
    capture["counts"]["pre_memory_observations"] = sum(
        len(row["pre_memory_observations"]) for row in rows
    )
    (evidence / "capture.json").write_bytes(canonical(capture))
    seal = json.loads((evidence / "acquisition_seal.json").read_text(encoding="utf-8"))
    seal["sealed_files"]["caller_trace.jsonl"] = _sha(evidence / "caller_trace.jsonl")
    seal["sealed_files"]["capture.json"] = _sha(evidence / "capture.json")
    (evidence / "acquisition_seal.json").write_bytes(canonical(seal))


def test_missing_required_read_refused_after_repaired_local_wrappers(tmp_path):
    from runtime_trace.caller_transition.producer_reads import ProducerReadsRefused, _validate_bundle

    evidence = tmp_path / "evidence"
    shutil.copytree(ARTIFACTS / CASES[0][0], evidence)
    _repair_trace_and_wrappers(evidence, lambda rows: rows[0]["pre_memory_observations"].clear())
    with pytest.raises(ProducerReadsRefused, match="missing or duplicate required memory observation"):
        _validate_bundle(evidence, ROOT, "attempt-05")


def test_sealed_file_mutation_is_refused(tmp_path):
    from runtime_trace.caller_transition.producer_reads import ProducerReadsRefused, _validate_bundle

    evidence = tmp_path / "evidence"
    shutil.copytree(ARTIFACTS / CASES[0][0], evidence)
    (evidence / "gdb.log").write_bytes((evidence / "gdb.log").read_bytes() + b"tamper")
    with pytest.raises(ProducerReadsRefused, match="sealed file hash"):
        _validate_bundle(evidence, ROOT, "attempt-05")


def test_source_receipt_omission_is_refused_even_after_seal_repair(tmp_path):
    from runtime_trace.caller_transition.producer_reads import ProducerReadsRefused, _validate_bundle
    from runtime_trace.caller_transition.run_acquisition_reads import canonical

    evidence = tmp_path / "evidence"
    shutil.copytree(ARTIFACTS / CASES[0][0], evidence)
    pinset = json.loads((evidence / "source_pinset.json").read_text(encoding="utf-8"))
    removed = pinset["exact_key_set"].pop()
    pinset["files"].pop(removed)
    (evidence / "source_pinset.json").write_bytes(canonical(pinset))
    seal = json.loads((evidence / "acquisition_seal.json").read_text(encoding="utf-8"))
    seal["sealed_files"]["source_pinset.json"] = _sha(evidence / "source_pinset.json")
    (evidence / "acquisition_seal.json").write_bytes(canonical(seal))
    with pytest.raises(ProducerReadsRefused, match="source pinset exact key set"):
        _validate_bundle(evidence, ROOT, "attempt-05")


@pytest.mark.parametrize(("case", "label"), CASES)
def test_v2_producer_output_is_authenticated_and_deterministic(tmp_path, case, label):
    from runtime_trace.caller_transition.producer_reads import produce

    published = ARTIFACTS / "producer-fix-round2" / case
    first = tmp_path / "first" / "transition.json"
    second = tmp_path / "second" / "transition.json"
    transition = produce(ARTIFACTS / case, label, first, root=ROOT)
    produce(ARTIFACTS / case, label, second, root=ROOT)
    assert first.read_bytes() == second.read_bytes() == (published / "transition.json").read_bytes()
    assert first.with_name("summary.json").read_bytes() == second.with_name("summary.json").read_bytes()
    assert transition["schema"] == "gala-caller-transition-v2"
    assert transition["authentication"]["seal_sha256"] == _sha(
        ARTIFACTS / case / "acquisition_seal.json"
    )
    assert transition["authentication"]["execution_sha256"] == _sha(
        ARTIFACTS / case / "execution.json"
    )
    assert [item["sequence"] for item in transition["readproof"]["final_abi_source_observations"]] == [
        718, 721, 722, 723, 724, 725, 726, 727,
    ]
    assert transition["readproof"]["pre_memory_observation_failures"] == 0
    assert transition["second_step_body_executed"] is False
