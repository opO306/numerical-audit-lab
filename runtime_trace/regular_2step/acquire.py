"""Exclusive production runner for regular two-step native capture."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from runtime_trace.regular_2step.structure import StructureRefused, compare


class AcquisitionRefused(ValueError):
    """The acquisition receipt cannot be finalized."""


def definition_only_nodes(source, class_name="Capture"):
    tree = ast.parse(source)
    selected = []
    found_capture = False
    for node in tree.body:
        definition = isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign,
                                       ast.FunctionDef, ast.ClassDef))
        docstring = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                     and isinstance(node.value.value, str))
        path_setup = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                      and isinstance(node.value.func, ast.Attribute)
                      and node.value.func.attr == "insert"
                      and isinstance(node.value.func.value, ast.Attribute)
                      and node.value.func.value.attr == "path"
                      and isinstance(node.value.func.value.value, ast.Name)
                      and node.value.func.value.value.id == "sys")
        if definition or docstring or (path_setup and not found_capture):
            selected.append(node)
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                found_capture = True
            continue
        if found_capture:
            break
        raise AcquisitionRefused(f"unexpected top-level node before Capture: {type(node).__name__}")
    if not found_capture:
        raise AcquisitionRefused(f"bounded loader did not find {class_name} definition")
    return selected


def supplemental_required_reads(assembly, registers, pc, length, site):
    from runtime_trace.semantics import effective_address, split_operands

    text = re.sub(r"\s+<[^>]*>", "", assembly.split("#", 1)[0]).strip()
    opcode, _, tail = text.partition(" ")
    operands = split_operands(tail.strip())
    pinned_imul = {
        "module_sha256": "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
        "elf_address": 0x35418,
        "bytes": "490faff6",
    }
    if (opcode == "imul" and operands == ["%r14", "%rsi"] and
            all(site.get(key) == value for key, value in pinned_imul.items())):
        return []
    if opcode in {"addsd", "subsd", "mulsd"} and len(operands) == 2 and re.fullmatch(
            r"%xmm\d+", operands[1]):
        source = operands[0]
        if re.fullmatch(r"%xmm\d+", source):
            return []
        if "(" in source and not source.startswith(("%fs:", "%gs:")):
            try:
                address = effective_address(source, registers, pc, length)
            except Exception as exc:
                raise AcquisitionRefused(f"unsupported supplemental scalar memory operand: {exc}") from exc
            return [{"address": address, "size": 8, "kind": "EXPLICIT", "operand": source}]
    raise AcquisitionRefused(f"unsupported supplemental read form: {text}")


def prove_exact_harness(root):
    root = Path(root)
    old = (root / "runtime_trace/harness.py").read_bytes()
    new = (root / "runtime_trace/harness_nsteps2.py").read_bytes()
    expected = old.replace(b"n_steps=1", b"n_steps=2", 1)
    if old.count(b"n_steps=1") != 1 or new != expected:
        raise AcquisitionRefused("harness is not the exact one-token n_steps change")
    return {
        "schema": "regular-2step-harness-source-proof-v1",
        "old_sha256": hashlib.sha256(old).hexdigest(),
        "new_sha256": hashlib.sha256(new).hexdigest(),
        "replacement": "n_steps=1 -> n_steps=2",
        "replacement_count": 1,
        "all_other_bytes_identical": True,
        "inherited_output_n_steps_metadata": 1,
        "inherited_metadata_status": "STALE_DO_NOT_USE_AS_EXECUTION_COUNT",
    }


def bind_antecedent(capture, antecedent, antecedent_path):
    if (antecedent.get("schema") != "gala-caller-transition-capture-v2" or
            antecedent.get("verdict") != "CONTROLLED_STOP"):
        raise AcquisitionRefused("antecedent caller capture receipt")
    old_identity = antecedent.get("process_identity")
    new_identity = capture.get("process_identity")
    if not old_identity or old_identity == new_identity:
        raise AcquisitionRefused("antecedent and new acquisition identities must be distinct")
    step2 = next((region for region in capture.get("regions", [])
                  if region.get("occurrence") == "step2"), None)
    if step2 is None:
        raise AcquisitionRefused("new step2 entry absent")
    old_entry = antecedent.get("second_step_entry", {})
    old_abi = old_entry.get("abi", {})
    roles = {}
    for name in ("q", "full_v", "latent", "gradient"):
        old_bits = old_abi.get("component_bits", {}).get(name)
        new_bits = step2.get("start_state", {}).get(name)
        if old_bits != new_bits:
            raise AcquisitionRefused(f"antecedent role bits differ: {name}")
        if name == "gradient" and new_bits != ["0x0000000000000000"] * 2:
            raise AcquisitionRefused("step2 gradient is not exact zero")
        roles[name] = {"antecedent_bits": old_bits, "new_process_bits": new_bits,
                       "equal": True, "address_equality_claimed": False}
    provenance = old_entry.get("argument_sources", {})
    for name in ("t", "dt"):
        old_bits = old_abi.get(f"{name}_bits")
        new_bits = step2.get(f"{name}_bits")
        if old_bits != new_bits or provenance.get(name, {}).get("source_bits") != old_bits:
            raise AcquisitionRefused(f"antecedent {name} provenance")
    old_gradient_observation = old_abi.get("stack_argument_observations", {}).get("gradient")
    new_gradient_observation = step2.get("entry_stack_observations", {}).get("gradient_pointer")
    new_gradient_pointer = step2.get("pointers", {}).get("gradient")
    expected_pointer_bytes = (new_gradient_pointer.to_bytes(8, "little").hex()
                              if isinstance(new_gradient_pointer, int) else None)
    if (old_gradient_observation is None or new_gradient_observation is None or
            new_gradient_observation.get("status") != "OK" or
            new_gradient_observation.get("timing") != "FUNCTION_ENTRY" or
            new_gradient_observation.get("size") != 8 or
            new_gradient_observation.get("bytes_hex") != expected_pointer_bytes):
        raise AcquisitionRefused("gradient pointer provenance")
    path = Path(antecedent_path)
    path_digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {
        "schema": "regular-2step-antecedent-binding-v1",
        "antecedent_capture_path": str(path).replace("\\", "/"),
        "antecedent_capture_sha256": path_digest,
        "antecedent_process_identity": old_identity,
        "new_process_identity": new_identity,
        "processes_distinct": True,
        "binding_basis": ["logical_role", "component_bits", "argument_provenance"],
        "roles": roles,
        "arguments": {name: {"antecedent": provenance[name],
                             "new_entry_bits": step2[f"{name}_bits"], "equal": True}
                      for name in ("t", "dt")},
        "gradient_pointer_provenance": {
            "antecedent": old_gradient_observation,
            "new_process": new_gradient_observation,
            "new_process_pointer": new_gradient_pointer,
            "address_equality_claimed": False,
        },
        "old_capture_continuation_claimed": False,
        "statement": "A new process reproduces the audited logical boundary; the stopped old process did not resume.",
    }


SOURCE_PATHS = [
    "runtime_trace/harness.py",
    "runtime_trace/harness_nsteps2.py",
    "runtime_trace/semantics.py",
    "runtime_trace/gdb_capture.py",
    "runtime_trace/caller_transition/read_effects.py",
    "runtime_trace/caller_transition/write_effects.py",
    "runtime_trace/caller_transition/write_effects_reads.py",
    "runtime_trace/caller_transition/gdb_acquire_reads.py",
    "runtime_trace/caller_transition/module_resolver.py",
    "runtime_trace/caller_transition/frozen_modules/manifest.json",
    "runtime_trace/regular_2step/__init__.py",
    "runtime_trace/regular_2step/acquire.py",
    "runtime_trace/regular_2step/gdb_acquire.py",
    "runtime_trace/regular_2step/structure.py",
    "runtime_trace/regular_2step/CONTRACT.md",
]


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_exclusive(path, value):
    Path(path).open("xb").write(_canonical(value))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_pinset(root):
    files = {}
    for relative in SOURCE_PATHS:
        path = root / relative
        if not path.is_file():
            raise AcquisitionRefused(f"source pin missing: {relative}")
        files[relative] = _sha(path)
    return {"schema": "regular-2step-source-pinset-v1", "files": files,
            "exact_key_set": sorted(files)}


def _process_local_handoff(capture):
    step1, step2 = capture["regions"][1:]
    roles = {}
    for name in ("q", "full_v", "latent"):
        before, after = step1["end_state"][name], step2["start_state"][name]
        if before != after:
            raise AcquisitionRefused(f"process-local handoff bits differ: {name}")
        roles[name] = {"from_bits": before, "to_bits": after, "equal": True,
                       "from_pointer": step1["pointers"][name],
                       "to_pointer": step2["pointers"][name]}
        if roles[name]["from_pointer"] != roles[name]["to_pointer"]:
            raise AcquisitionRefused(f"process-local handoff pointer differs: {name}")
    gradient_pointer = step2["pointers"]["gradient"]
    if (step1["pointers"]["gradient"] != gradient_pointer or
            step2["start_state"]["gradient"] != ["0x0000000000000000"] * 2):
        raise AcquisitionRefused("process-local gradient pointer/exact-zero entry")
    gradient_observation = step2["entry_stack_observations"]["gradient_pointer"]
    if gradient_observation.get("bytes_hex") != gradient_pointer.to_bytes(8, "little").hex():
        raise AcquisitionRefused("process-local gradient stack provenance")
    acquisition_id = capture["acquisition_id"]
    return {"from_acquisition_id": acquisition_id, "to_acquisition_id": acquisition_id,
            "from_occurrence": "step1-return", "to_occurrence": "step2-entry",
            "same_process": True, "roles": roles,
            "gradient_boundary": {"pointer": gradient_pointer,
                "step1_pointer": step1["pointers"]["gradient"],
                "from_bits": step1["end_state"]["gradient"],
                "to_bits": step2["start_state"]["gradient"],
                "entry_stack_observation": gradient_observation,
                "exact_zero": True, "caller_reset_write_required": True}}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--case", choices=["known", "fresh"], required=True)
    parser.add_argument("--antecedent", required=True)
    parser.add_argument("--distinct-from")
    args = parser.parse_args(argv)
    if args.case == "fresh" and not args.distinct_from:
        raise SystemExit("REFUSED: fresh acquisition requires --distinct-from known capture")
    if args.case == "known" and args.distinct_from:
        raise SystemExit("REFUSED: known acquisition must not declare --distinct-from")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("REFUSED: Linux x86_64 required")
    expected_python = Path("/home/otherside123/venvs/gate2c1-trace/bin/python").resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise SystemExit(f"REFUSED: frozen Python required: {expected_python}")
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    source_pinset = _source_pinset(root)
    _write_exclusive(out / "source_pinset.json", source_pinset)
    harness_proof = prove_exact_harness(root)
    command = ["gdb", "-q", "-nx", "-batch", "-x",
               str(root / "runtime_trace/regular_2step/gdb_acquire.py"),
               "--args", sys.executable, str(root / "runtime_trace/harness_nsteps2.py")]
    changes = {"LD_BIND_NOW": "1", "RT_OUTPUT": str(out), "RT2_CASE": args.case,
               "CT_ANTECEDENT_LABEL": args.case}
    env = dict(os.environ, **changes)
    try:
        result = subprocess.run(command, cwd=root, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        code = -1
    (out / "gdb.log").open("x", encoding="utf-8", newline="\n").write(output)
    pending_path = out / "capture.pending.json"
    pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.is_file() else {
        "schema": "gala-regular-2step-runtime-trace-v1", "verdict": "REFUSED",
        "reason": "GDB did not publish capture.pending.json",
    }
    execution = {
        "schema": "regular-2step-execution-v1", "case": args.case,
        "command": command, "cwd": str(root), "launcher_pid": os.getpid(),
        "inferior_pid": pending.get("process_identity", {}).get("pid"),
        "process_identity": pending.get("process_identity"), "return_code": code,
        "process_wall_seconds": time.perf_counter() - started,
        "environment_changes": changes, "harness_completed_normally":
            pending.get("harness_completed_normally", False),
        "gdb_exit_event": pending.get("gdb_exit_event"),
        "environment": {"python": platform.python_version(), "gdb": pending.get("gdb_version"),
                        "kernel": platform.release(), "platform": platform.platform(),
                        "packages": {name: metadata.version(name)
                                     for name in ["gala", "numpy", "scipy", "astropy"]}},
        "source_pinset_path": "source_pinset.json",
        "source_pinset_sha256": _sha(out / "source_pinset.json"),
        "source_sha256_before_execution": source_pinset["files"],
        "harness_source_proof": harness_proof,
        "machine_mapping_used_during_acquisition": False,
    }
    _write_exclusive(out / "execution.json", execution)
    if pending.get("verdict") != "CAPTURED" or code != 0 or not (out / "harness_output.json").is_file():
        print(json.dumps({"out": str(out), "verdict": pending.get("verdict"),
                          "reason": pending.get("reason"), "return_code": code}))
        return 2
    trace_sha = _sha(out / "trace.jsonl")
    acquisition_id = hashlib.sha256(_canonical({"case": args.case,
                                                "process_identity": pending["process_identity"],
                                                "trace_sha256": trace_sha})).hexdigest()
    capture = dict(pending)
    capture.update({"case": args.case, "acquisition_id": acquisition_id,
                    "trace_sha256": trace_sha, "execution_path": "execution.json",
                    "execution_sha256": _sha(out / "execution.json"),
                    "source_pinset_path": "source_pinset.json",
                    "source_pinset_sha256": _sha(out / "source_pinset.json"),
                    "harness_binding": {"exact_one_token_n_steps_change": True,
                        "executed_native_step_calls": 2, "harness_completed_normally": True,
                        "inherited_stale_n_steps_metadata": True,
                        "source_proof": harness_proof}})
    capture["process_local_handoff"] = _process_local_handoff(capture)
    antecedent_path = Path(args.antecedent).resolve()
    antecedent = json.loads(antecedent_path.read_text(encoding="utf-8"))
    capture["antecedent_binding"] = bind_antecedent(capture, antecedent, antecedent_path)
    if root in antecedent_path.parents:
        capture["antecedent_binding"]["antecedent_capture_path"] = str(
            antecedent_path.relative_to(root)).replace("\\", "/")
    if args.distinct_from:
        other_path = Path(args.distinct_from).resolve()
        other = json.loads((other_path / "capture.json").read_text(encoding="utf-8"))
        if (other.get("process_identity") == capture["process_identity"] or
                other.get("acquisition_id") == acquisition_id):
            raise AcquisitionRefused("known/fresh acquisitions are not distinct")
        stored_other_path = (str(other_path.relative_to(root)).replace("\\", "/")
                             if root in other_path.parents else str(other_path))
        capture["distinct_from"] = {"capture_path": stored_other_path,
                                    "capture_sha256": _sha(other_path / "capture.json"),
                                    "acquisition_id": other["acquisition_id"],
                                    "process_identity": other["process_identity"],
                                    "trace_sha256": other["trace_sha256"],
                                    "distinct": True}
    _write_exclusive(out / "capture.json", capture)
    pending_path.unlink()
    sealed_names = ["trace.jsonl", "capture.json", "execution.json", "source_pinset.json",
                    "harness_output.json", "gdb.log"]
    seal = {"schema": "regular-2step-acquisition-seal-v1",
            "acquisition_id": acquisition_id,
            "sealed_files": {name: _sha(out / name) for name in sealed_names},
            "sealed_file_name_set": sorted(sealed_names),
            "final_required_file_name_set": sorted(sealed_names +
                ["acquisition_seal.json", "structure_report.json"])}
    _write_exclusive(out / "acquisition_seal.json", seal)
    try:
        report = compare(out, root)
    except StructureRefused as exc:
        print(json.dumps({"out": str(out), "verdict": "REFUSED",
                          "reason": f"StructureRefused: {exc}"}))
        return 3
    _write_exclusive(out / "structure_report.json", report)
    print(json.dumps({"out": str(out), "verdict": report["verdict"],
                      "record_count": capture["record_count"],
                      "acquisition_id": acquisition_id,
                      "structure_report_sha256": _sha(out / "structure_report.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
