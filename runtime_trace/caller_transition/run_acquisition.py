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


def ensure_exclusive_output(path):
    Path(path).mkdir(parents=True, exist_ok=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--antecedent", choices=["attempt-05", "closure-fresh-01"], required=True)
    args = parser.parse_args(argv)
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("REFUSED: Linux x86_64 required")
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve()
    ensure_exclusive_output(out)
    old = (root / "runtime_trace/harness.py").read_bytes()
    new = (root / "runtime_trace/harness_nsteps2.py").read_bytes()
    if old.count(b"n_steps=1") != 1 or new != old.replace(b"n_steps=1", b"n_steps=2", 1):
        raise SystemExit("REFUSED: harness is not exact one-token n_steps change")
    diff = {"schema": "caller-transition-harness-diff-v1", "old_sha256": hashlib.sha256(old).hexdigest(),
            "new_sha256": hashlib.sha256(new).hexdigest(), "replacement": "n_steps=1 -> n_steps=2",
            "replacement_count": 1, "all_other_bytes_identical": True}
    (out / "harness_diff.json").write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    sources = {}
    for relative in ["runtime_trace/harness.py", "runtime_trace/harness_nsteps2.py",
                     "runtime_trace/caller_transition/gdb_acquire.py",
                     "runtime_trace/caller_transition/write_effects.py",
                     "runtime_trace/caller_transition/module_resolver.py",
                     "runtime_trace/caller_transition/frozen_modules/manifest.json",
                     "runtime_trace/caller_transition/run_acquisition.py"]:
        sources[relative] = sha(root / relative)
    command = ["gdb", "-q", "-nx", "-batch", "-x",
               str(root / "runtime_trace/caller_transition/gdb_acquire.py"),
               "--args", sys.executable, str(root / "runtime_trace/harness_nsteps2.py")]
    env = dict(os.environ, RT_OUTPUT=str(out), CT_ANTECEDENT_LABEL=args.antecedent, LD_BIND_NOW="1")
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
    (out / "gdb.log").write_text(output, encoding="utf-8")
    capture_path = out / "capture.json"
    capture = json.loads(capture_path.read_text()) if capture_path.exists() else {
        "verdict": "REFUSED", "reason": "GDB did not publish capture.json"
    }
    execution = {"schema": "caller-transition-execution-v1", "antecedent_label": args.antecedent,
                 "launcher_pid": os.getpid(), "inferior_pid": capture.get("inferior_pid"),
                 "command": command, "cwd": str(root), "return_code": code,
                 "process_wall_seconds": elapsed, "environment_changes": {"LD_BIND_NOW": "1",
                    "RT_OUTPUT": str(out), "CT_ANTECEDENT_LABEL": args.antecedent},
                 "environment": {"python": platform.python_version(), "platform": platform.platform(),
                    "packages": {name: metadata.version(name) for name in ["gala", "numpy", "astropy", "scipy"]}},
                 "packages_installed": [], "source_sha256_before_execution": sources,
                 "machine_mapping_used_during_acquisition": False,
                 "harness_completed_normally": False,
                 "frozen_wheel_sha256": "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"}
    (out / "execution.json").write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "verdict": capture.get("verdict"),
                      "reason": capture.get("reason"), "record_count": capture.get("record_count")}))
    return 0 if capture.get("verdict") == "CONTROLLED_STOP" and code == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
