"""Exclusive v2 read-proof runner and acyclic acquisition bundle sealer."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


SOURCE_PATHS = [
    "runtime_trace/harness.py",
    "runtime_trace/harness_nsteps2.py",
    "runtime_trace/semantics.py",
    "runtime_trace/caller_transition/__init__.py",
    "runtime_trace/caller_transition/gdb_acquire_reads.py",
    "runtime_trace/caller_transition/read_effects.py",
    "runtime_trace/caller_transition/write_effects.py",
    "runtime_trace/caller_transition/write_effects_reads.py",
    "runtime_trace/caller_transition/module_resolver.py",
    "runtime_trace/caller_transition/frozen_modules/manifest.json",
    "runtime_trace/caller_transition/run_acquisition_reads.py",
]
EXPECTED_MODULES = {
    "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf",
    "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
    "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f",
}
WHEEL_SHA = "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"
MEMORY_POLICY = "all-explicit-and-implicit-control-stack-v1"
SEGMENT_POLICY = "per-row-fs-gs-base-v1"


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_exclusive(path, value):
    Path(path).open("xb").write(canonical(value))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin_sources(root):
    files = {relative: sha(root / relative) for relative in SOURCE_PATHS}
    return {"schema": "caller-transition-source-pinset-v1", "files": files,
            "exact_key_set": sorted(files)}


def pin_modules(root):
    manifest_path = root / "runtime_trace/caller_transition/frozen_modules/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(manifest.get("modules", {})) != EXPECTED_MODULES:
        raise SystemExit("REFUSED: frozen module manifest set")
    modules = {}
    for digest, relative in manifest["modules"].items():
        path = (manifest_path.parent / relative).resolve()
        if root not in path.parents or sha(path) != digest:
            raise SystemExit("REFUSED: frozen module bytes")
        modules[digest] = {"resolver_path": str(path.relative_to(root)).replace("\\", "/"),
                           "bytes": path.stat().st_size}
    return {"schema": "caller-transition-module-pinset-v1",
            "manifest_path": "runtime_trace/caller_transition/frozen_modules/manifest.json",
            "manifest_sha256": sha(manifest_path), "modules": modules,
            "exact_sha256_set": sorted(modules)}


def validate_trace_for_finalization(path, pending):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != pending.get("record_count"):
        raise SystemExit("REFUSED: pending/trace record count")
    failures = 0
    observations = 0
    for expected, row in enumerate(rows):
        if row.get("schema") != "gala-caller-transition-instruction-v2" or row.get("sequence") != expected:
            raise SystemExit("REFUSED: v2 trace schema or sequence")
        for side in ("pre", "post"):
            bases = row.get(side, {}).get("segment_bases", {})
            if set(bases) != {"fs_base", "gs_base"}:
                raise SystemExit("REFUSED: incomplete segment bases")
        for observation in row.get("pre_memory_observations", []):
            observations += 1
            if observation.get("status") != "OK" or observation.get("timing") != "PRE_INSTRUCTION":
                failures += 1
            raw_hex = observation.get("bytes_hex")
            if not isinstance(raw_hex, str) or len(raw_hex) != 2 * observation.get("size", -1):
                failures += 1
    if failures:
        raise SystemExit("REFUSED: failed or malformed pre-memory observation")
    if observations != pending.get("counts", {}).get("pre_memory_observations"):
        raise SystemExit("REFUSED: pre-memory observation count")
    return raw, rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--antecedent", choices=["attempt-05", "closure-fresh-01"], required=True)
    args = parser.parse_args(argv)
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("REFUSED: Linux x86_64 required")
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)

    old = (root / "runtime_trace/harness.py").read_bytes()
    new = (root / "runtime_trace/harness_nsteps2.py").read_bytes()
    if old.count(b"n_steps=1") != 1 or new != old.replace(b"n_steps=1", b"n_steps=2", 1):
        raise SystemExit("REFUSED: harness is not exact one-token n_steps change")
    harness_diff = {"schema": "caller-transition-harness-diff-v1",
                    "old_sha256": hashlib.sha256(old).hexdigest(),
                    "new_sha256": hashlib.sha256(new).hexdigest(),
                    "replacement": "n_steps=1 -> n_steps=2", "replacement_count": 1,
                    "all_other_bytes_identical": True}
    write_exclusive(out / "harness_diff.json", harness_diff)

    source_pinset = pin_sources(root)
    module_pinset = pin_modules(root)
    write_exclusive(out / "source_pinset.json", source_pinset)
    write_exclusive(out / "module_pinset.json", module_pinset)
    source_pinset_sha = sha(out / "source_pinset.json")
    module_pinset_sha = sha(out / "module_pinset.json")

    command = ["gdb", "-q", "-nx", "-batch", "-x",
               str(root / "runtime_trace/caller_transition/gdb_acquire_reads.py"),
               "--args", sys.executable, str(root / "runtime_trace/harness_nsteps2.py")]
    changes = {"LD_BIND_NOW": "1", "RT_OUTPUT": str(out),
               "CT_ANTECEDENT_LABEL": args.antecedent}
    env = dict(os.environ, **changes)
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=root, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        code = -1
    elapsed = time.perf_counter() - started
    (out / "gdb.log").open("x", encoding="utf-8", newline="\n").write(output)
    pending_path = out / "capture.pending.json"
    pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else {
        "schema": "gala-caller-transition-capture-v2", "verdict": "REFUSED",
        "reason": "GDB did not publish capture.pending.json", "antecedent_label": args.antecedent,
        "pre_memory_observation_failures": 1,
    }

    execution = {
        "schema": "caller-transition-execution-v2", "antecedent_label": args.antecedent,
        "command": command, "cwd": str(root), "launcher_pid": os.getpid(),
        "inferior_pid": pending.get("inferior_pid"), "return_code": code,
        "process_identity": pending.get("process_identity"), "process_wall_seconds": elapsed,
        "environment_changes": changes, "all_stop_mode": True, "scheduler_locking": "on",
        "environment": {"python": platform.python_version(), "gdb": pending.get("gdb_version"),
            "kernel": platform.release(), "platform": platform.platform(),
            "wsl_proc_version": Path("/proc/version").read_text(encoding="utf-8").strip(),
            "packages": {name: metadata.version(name) for name in ["gala", "numpy", "scipy", "astropy"]}},
        "packages_installed": [], "frozen_wheel_sha256": WHEEL_SHA,
        "source_sha256_before_execution": source_pinset["files"],
        "source_receipt_key_set": source_pinset["exact_key_set"],
        "source_pinset_path": "source_pinset.json", "source_pinset_sha256": source_pinset_sha,
        "module_pinset_path": "module_pinset.json", "module_pinset_sha256": module_pinset_sha,
        "frozen_module_manifest_sha256": module_pinset["manifest_sha256"],
        "frozen_module_sha256_set": module_pinset["exact_sha256_set"],
        "trace_schema": "gala-caller-transition-instruction-v2",
        "memory_observation_policy_id": MEMORY_POLICY, "segment_base_policy_id": SEGMENT_POLICY,
        "pre_memory_observation_failures": pending.get("pre_memory_observation_failures", 1),
        "machine_mapping_used_during_acquisition": False, "harness_completed_normally": False,
    }
    write_exclusive(out / "execution.json", execution)

    success = pending.get("verdict") == "CONTROLLED_STOP" and code == 0
    if not success:
        print(json.dumps({"out": str(out), "verdict": pending.get("verdict"),
                          "reason": pending.get("reason"), "record_count": pending.get("record_count")}))
        return 2

    trace_raw, rows = validate_trace_for_finalization(out / "caller_trace.jsonl", pending)
    if pending.get("pre_memory_observation_failures") != 0:
        raise SystemExit("REFUSED: pending memory observation failures")
    capture = dict(pending)
    capture.update({
        "execution_path": "execution.json", "execution_sha256": sha(out / "execution.json"),
        "trace_sha256": hashlib.sha256(trace_raw).hexdigest(),
        "source_pinset_path": "source_pinset.json", "source_pinset_sha256": source_pinset_sha,
        "module_pinset_path": "module_pinset.json", "module_pinset_sha256": module_pinset_sha,
        "source_receipt_key_set": source_pinset["exact_key_set"],
        "module_sha256_set": module_pinset["exact_sha256_set"],
        "required_memory_observations_complete": True, "segment_bases_complete": True,
    })
    write_exclusive(out / "capture.json", capture)
    pending_path.unlink()

    sealed_names = sorted([
        "caller_trace.jsonl", "capture.json", "execution.json", "first_step_disassembly.txt",
        "gdb.log", "harness_diff.json", "module_pinset.json", "source_pinset.json",
    ])
    actual_before_seal = sorted(path.name for path in out.iterdir())
    if actual_before_seal != sealed_names:
        raise SystemExit(f"REFUSED: unexpected acquisition file set {actual_before_seal}")
    sealed_files = {name: sha(out / name) for name in sealed_names}
    seal = {"schema": "caller-transition-acquisition-seal-v1",
            "antecedent_label": args.antecedent, "exact_file_name_set": sealed_names,
            "sealed_files": sealed_files, "file_count": len(sealed_names)}
    write_exclusive(out / "acquisition_seal.json", seal)
    print(json.dumps({"out": str(out), "verdict": capture["verdict"],
                      "record_count": len(rows), "seal_sha256": sha(out / "acquisition_seal.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
