"""Author verification receipt for F-CLAIM-1; never an independent re-audit.

Run from any directory:
  python tools/verify_c1b1_claim_output_fix.py --out NEW_DIRECTORY \
    --preservation-before current/c1b1-claim-output-fix-2026-10-04/preservation-before.json
Writes exclusive new evidence and leaves historical reports untouched.
"""
import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TARGET = "f806d8ce1ef86a0948b1a8abafe1a22c3058178b"
BASE = "e976fa0fdeef16a27f112a0a4ee42494fe1e46b1"
ADAPTER = "independent_checker/c1b1/claim_adapter.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write("\n")


def tree(ref):
    result = {}
    for entry in subprocess.check_output(["git", "ls-tree", "-rz", ref], cwd=ROOT).split(b"\0"):
        if entry:
            metadata, path = entry.split(b"\t", 1)
            result[path.decode()] = metadata.decode()
    return result


def preservation(before):
    baseline = json.loads(before.read_bytes())
    prior = baseline["tracked_raw_sha256_before"]
    changed = [path for path, digest in prior.items() if sha((ROOT / path).read_bytes()) != digest]
    assert changed == [ADAPTER], changed
    base, old, head = tree(BASE), tree(TARGET), tree("HEAD")
    assert len(base) == 1921
    assert all(old[path] == metadata == head[path] for path, metadata in base.items())
    assert all(sha((ROOT / path).read_bytes()) == prior[path] for path in base)
    source_rows = {}
    for name in ("exact_slow.py", "exact_fast.py", "exact_geometry.py", "compare.py",
                 "contracts.py", "semantic_manifest_v1.json", "semantic_manifest_v1.sha256"):
        path = "independent_checker/c1b1/" + name
        pinned = subprocess.check_output(["git", "show", TARGET + ":" + path], cwd=ROOT)
        actual = (ROOT / path).read_bytes()
        assert actual == pinned, path
        source_rows[name] = {"audited_sha256": sha(pinned), "current_sha256": sha(actual),
                             "byte_identical": True}
    for name, record in baseline["received"].items():
        assert sha((before.parent / "received" / name).read_bytes()) == record["sha256"]
        assert sha(Path(record["origin"]).read_bytes()) == record["sha256"]
    return {"base_files": len(base), "base_git_blobs_unchanged": len(base),
            "base_raw_bytes_unchanged": len(base), "pre_fix_files": len(prior),
            "pre_fix_raw_bytes_unchanged": len(prior) - len(changed), "changed_existing": changed,
            "deleted_existing": [], "audited_source_sha256": source_rows,
            "received_originals_and_copies_byte_identical": len(baseline["received"]),
            "preservation_before_sha256": sha(before.read_bytes())}


def pytest_run(out, label, files, extra_env=None):
    command = [sys.executable, "-m", "pytest", *files, "-q", "--tb=short",
               "--junitxml=" + str(out / (label + ".xml"))]
    environment = os.environ.copy()
    for key in ("C1B1_MUTANT_REPORT", "C1B1_CLAIM_OUTPUT_MUTANT_REPORT"):
        environment.pop(key, None)
    environment.update(extra_env or {})
    environment["PYTHONIOENCODING"] = "utf-8"
    start = time.perf_counter()
    with (out / (label + ".log")).open("xb") as log:
        process = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    suites = ET.parse(out / (label + ".xml")).getroot().findall("testsuite")
    counts = {key: sum(int(suite.get(key, "0")) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    record = {"command": command, "exit_code": process.returncode, "seconds": time.perf_counter() - start,
              **counts, "log": label + ".log", "xml": label + ".xml"}
    write_json(out / (label + "-execution.json"), record)
    print(label, json.dumps(record), flush=True)
    return record


def reproduce(out):
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    from test_c1b1_claim_output_boundary import false_zero_claim
    from independent_checker.c1b1 import contracts as C, exact_slow, exact_fast
    from independent_checker.c1b1.claim_adapter import compare_claim
    payload = false_zero_claim()
    before = copy.deepcopy(payload)
    x = 10 ** 2150
    denominator = (x + 1) * (x + 3)
    assert 10 ** 4300 <= denominator < 10 ** 4301
    request = C.DriftInput(C.Grid(8, 0), C.Grid(8, 0), (0, 0, 0), (0, 0, 0),
        (1, 0, 0), (0, 0, 0), C.Ratio(x + 3, 1), C.Ratio(1, 1), C.Ratio(1, x + 1))
    request_before = copy.deepcopy(request)
    process_limit = sys.get_int_max_str_digits()
    rows = []
    wire = json.dumps(payload, separators=(",", ":"))
    for path, kernel in (("exact_slow", exact_slow), ("exact_fast", exact_fast)):
        result = kernel.drift(request)
        assert result.displacement[0].numerator == 1 and result.displacement[0].denominator == denominator
        assert result.delta_i == result.delta_j == result.r_i == result.r_j == (0, 0, 0)
        try:
            compare_claim(wire, path, opt_in=(path == "exact_fast"))
        except C.LabRefusal as exc:
            assert exc.failure.code == "CLAIM_OUTPUT_LIMIT" and exc.failure.phase == "claim_output"
            rows.append({"path": path, "kernel_exact_result_correct": True, "exception": "LabRefusal",
                         "failure": asdict(exc.failure)})
        else:
            raise AssertionError("expected output refusal")
    assert rows[0]["failure"] == rows[1]["failure"]
    assert payload == before and request == request_before
    assert sys.get_int_max_str_digits() == process_limit
    record = {"finding": "F-CLAIM-1", "status": "AUTHOR REPRODUCTION PASS",
              "input_integer_digits": 2151, "exact_denominator_digits": 4301,
              "wire_bytes": len(wire.encode()), "input_unchanged": True,
              "process_global_limit_before": process_limit, "process_global_limit_after": sys.get_int_max_str_digits(),
              "observations": rows, "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED"}
    write_json(out / "fix-reproduction.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preservation-before", type=Path, required=True)
    args = parser.parse_args()
    out, before = args.out.resolve(), args.preservation_before.resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Hash the source under test before running, and require the same bytes after.
    paths = [*sorted((ROOT / "independent_checker/c1b1").glob("*.py")),
             *sorted((ROOT / "tests").glob("test_c1b1_*.py")), Path(__file__).resolve()]
    tested_sources = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in paths}
    preserved_before = preservation(before)
    reproduction = reproduce(out)
    original = ["tests/test_c1b1_" + name + ".py" for name in
                ("slow", "fast", "differential", "geometry", "mutants", "claims", "boundary")]
    runs = {}
    runs["related-105"] = pytest_run(out, "related-105", original + ["tests/test_independence.py", "tests/test_provenance.py"],
                                     {"C1B1_MUTANT_REPORT": str(out / "existing-16-mutants.json")})
    runs["output-boundary"] = pytest_run(out, "output-boundary",
        ["tests/test_c1b1_claim_output_boundary.py", "tests/test_c1b1_claim_output_mutant.py"],
        {"C1B1_CLAIM_OUTPUT_MUTANT_REPORT": str(out / "fclaim1-source-mutant.json")})
    # Whole-repository verification is recorded separately from the requested
    # arithmetic suite; failures never silently become an arithmetic PASS.
    runs["repository-full"] = pytest_run(out, "repository-full", [])
    mutants = json.loads((out / "existing-16-mutants.json").read_bytes())
    historical = json.loads((ROOT / "docs/c1b1-arithmetic-v1/mutants.json").read_bytes())
    assert len(mutants) == 16 and all(row["baseline"] == "PASS" and row["actual_mutant_execution"] == "DETECTED" for row in mutants.values())
    assert all(mutants[key]["edits"] == historical[key]["edits"] and
               mutants[key]["mutant_sha256"] == historical[key]["mutant_sha256"] for key in mutants)
    new_mutant = json.loads((out / "fclaim1-source-mutant.json").read_bytes())
    assert new_mutant["baseline"] == "PASS" and new_mutant["actual_mutant_execution"] == "DETECTED"
    preserved_after = preservation(before)
    assert preserved_after == preserved_before
    assert all(sha((ROOT / path).read_bytes()) == digest for path, digest in tested_sources.items())
    author_pass = all(run["exit_code"] == 0 and run["failures"] == run["errors"] == 0 for run in runs.values())
    assert runs["related-105"]["tests"] == 105 and runs["related-105"]["skipped"] == 0
    receipt = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "arithmetic_audit_target": TARGET,
               "historical_overall_audit": "FAIL", "finding": "F-CLAIM-1", "python": sys.version,
               "implementation": "IMPLEMENTED FIX", "author_checks": "PASS" if author_pass else "FAIL",
               "independent_review": "INDEPENDENT RE-AUDIT PENDING", "certification": "NotCertified",
               "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED",
               "tested_source_sha256": tested_sources, "preservation": preserved_after,
               "runs": runs, "reproduction": reproduction, "existing_mutants": "16/16 DETECTED; identical historical edits and hashes",
               "new_mutant": "BASELINE PASS / MUTANT DETECTED on slow and fast",
               "performance": "NO PERFORMANCE PROMOTION; old timed kernels do not call claim_adapter",
               "commit_binding": "Source bytes pinned here; exact new commit bound by separate post-commit receipt",
               "push_performed": False}
    write_json(out / "author-verification-receipt.json", receipt)
    print("AUTHOR_CHECKS", receipt["author_checks"], flush=True)
    return 0 if author_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
