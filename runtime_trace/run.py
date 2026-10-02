"""Linux only; one regular step; distinct acquisition and post-hoc validation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("REFUSED: Linux x86_64 required")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, RT_OUTPUT=str(out), LD_BIND_NOW="1")
    sources = {f"runtime_trace/{name}":hashlib.sha256((root/"runtime_trace"/name).read_bytes()).hexdigest()
               for name in ["run.py","harness.py","semantics.py","gdb_capture.py"]}
    cmd = ["gdb","-q","-nx","-batch","-x",str(root/"runtime_trace/gdb_capture.py"),
           "--args",sys.executable,str(root/"runtime_trace/harness.py")]
    started = time.perf_counter()
    try:
        result = subprocess.run(cmd,env=env,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
        log, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        log, code = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout,bytes) else (exc.stdout or ""), -1
    elapsed = time.perf_counter()-started
    (out/"gdb.log").write_text(log)
    (out/"execution.json").write_text(json.dumps({"command":cmd,"gdb_process_wall_seconds":elapsed,
        "return_code":code,"environment_changes":{"LD_BIND_NOW":"1"},"packages_installed":[],
        "source_sha256_before_execution":sources,
        "machine_mapping_used_during_acquisition":False},indent=2)+"\n")
    capture_path = out/"capture.json"
    capture = json.loads(capture_path.read_text()) if capture_path.exists() else {"verdict":"REFUSED","reason":"no capture result"}
    if capture["verdict"] == "CAPTURED" and code == 0:
        baseline = out/"baseline"
        baseline.mkdir()
        bcmd = [sys.executable,str(root/"runtime_trace/harness.py")]
        bstarted = time.perf_counter()
        bresult = subprocess.run(bcmd,env=dict(env,RT_OUTPUT=str(baseline)),cwd=root,text=True,capture_output=True,timeout=30)
        belapsed = time.perf_counter()-bstarted
        (baseline/"stdout.log").write_text(bresult.stdout+bresult.stderr)
        baseline_data = json.loads((baseline/"harness_output.json").read_text()) if bresult.returncode == 0 else None
        traced_data = json.loads((out/"harness_output.json").read_text())
        (out/"timing.json").write_text(json.dumps({"baseline_command":bcmd,"baseline_return_code":bresult.returncode,
            "baseline_process_wall_seconds":belapsed,"gdb_process_wall_seconds":elapsed,
            "process_wall_delta_seconds":elapsed-belapsed,
            "traced_integrate_call_seconds":traced_data["integrate_call_wall_seconds"],
            "baseline_integrate_call_seconds":baseline_data["integrate_call_wall_seconds"] if baseline_data else None,
            "scope":"one paired 1-step sample; includes GDB capture I/O; not a scaling estimate"},indent=2)+"\n")
    print(json.dumps({"out":str(out),"capture_verdict":capture["verdict"],"reason":capture.get("reason"),
                      "record_count":capture.get("record_count"),"scalar_fp_count":capture.get("scalar_fp_count"),
                      "gdb_process_wall_seconds":elapsed}))
    return 0 if capture["verdict"] == "CAPTURED" and code == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
