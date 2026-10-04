"""Small author regression measurement; no arithmetic speedup promotion.

python current/c1b1-claim-output-fix-2026-10-04/measure_claim_regression.py
Writes an exclusive claim-regression.json beside this script. Imports/startup
are outside timing. Only one hand-authored synthetic Drift claim is measured.
"""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import types


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "independent_checker/c1b1"
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from test_c1b1_claims import envelope


def main():
    output = HERE / "claim-regression.json"
    assert not output.exists()
    original = subprocess.check_output(["git", "show", "f806d8ce1ef86a0948b1a8abafe1a22c3058178b:independent_checker/c1b1/claim_adapter.py"], cwd=ROOT)
    current = (SOURCE / "claim_adapter.py").read_bytes()
    payload = envelope()
    wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    rows = {revision + "." + path: [] for revision in ("audited", "fix")
            for path in ("exact_slow", "exact_fast")}
    process_limit = sys.get_int_max_str_digits()
    with tempfile.TemporaryDirectory(prefix="claim-regression-") as temporary:
        modules = {}
        for revision, adapter_bytes in (("audited", original), ("fix", current)):
            directory = Path(temporary) / revision
            directory.mkdir()
            for item in SOURCE.iterdir():
                if item.suffix in (".py", ".json", ".sha256"):
                    shutil.copyfile(item, directory / item.name)
            (directory / "claim_adapter.py").write_bytes(adapter_bytes)
            name = "_claim_regression_" + revision
            package = types.ModuleType(name)
            package.__path__ = [str(directory)]
            sys.modules[name] = package
            modules[revision] = importlib.import_module(name + ".claim_adapter")
        for path in ("exact_slow", "exact_fast"):
            answers = [modules[revision].compare_claim(wire, path, opt_in=(path == "exact_fast"))
                       for revision in ("audited", "fix")]
            assert all(answer.status == "ARITHMETIC_MATCH" for answer in answers)
            assert answers[0].computed_json == answers[1].computed_json
            assert all(answer.scope == "ARITHMETIC_ONLY" and answer.j_status == "J_NOT_VERIFIED" for answer in answers)
            for _ in range(20):
                for module in modules.values():
                    module.compare_claim(wire, path, opt_in=(path == "exact_fast"))
        invocations = 400
        for repetition in range(9):
            revisions = ("audited", "fix") if repetition % 2 == 0 else ("fix", "audited")
            for path in ("exact_slow", "exact_fast"):
                for revision in revisions:
                    start = time.perf_counter_ns()
                    for _ in range(invocations):
                        answer = modules[revision].compare_claim(wire, path, opt_in=(path == "exact_fast"))
                    rows[revision + "." + path].append((time.perf_counter_ns() - start) / invocations)
                    assert answer.status == "ARITHMETIC_MATCH"
    assert sys.get_int_max_str_digits() == process_limit
    report = {"purpose": "AUTHOR REGRESSION MEASUREMENT ONLY / NO PERFORMANCE PROMOTION",
              "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "certification": "NotCertified",
              "python": sys.version, "fixture": "one HAND_DERIVED_TEST_ONLY synthetic Drift claim",
              "fixture_sha256": hashlib.sha256(wire.encode()).hexdigest(),
              "ordinary_modules": True, "imports_and_startup_outside_timing": True,
              "module_loading": "isolated source copies; parent package startup excluded for both revisions",
              "measurement": "JSON decode + exact drift + canonical artifact + claim comparison + computed_json",
              "invocations_per_sample": invocations, "samples": 9, "warmup_per_path_per_revision": 20,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "adapter_sha256": {"audited": hashlib.sha256(original).hexdigest(), "fix": hashlib.sha256(current).hexdigest()},
              "rows": {key: {"wall_ns_per_invocation": values, "median_ns": statistics.median(values),
                             "min_ns": min(values), "max_ns": max(values)} for key, values in rows.items()},
              "results_match": True, "process_integer_limit_unchanged": process_limit,
              "limitations": "small single-fixture local regression; no claim about other inputs, hardware, kernel speedup, physical work or long-run throughput"}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(output), "median_ns": {key: row["median_ns"] for key, row in report["rows"].items()}}, indent=2))


if __name__ == "__main__":
    main()
