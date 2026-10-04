"""Author-only static closure checks; never import or run an arithmetic/impulse kernel.

Checks fixed specification files, identifiers, preservation and recorded witness
inequalities. This is not an Impulse validator, V2 executor or independent audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path


BASE = "4cb2910fe936f7b1d5150196e062b6b61edc240f"
ANTECEDENT = "65d8fd29ae255529afead70289098d36b825b3b4"
FAILURE_FIELDS = [
    "schema", "status", "phase", "reason", "resource_kind", "spec_sha256",
    "state_sha256", "occurrence_sha256", "budget_sha256", "attempt_count",
    "attempt_digest",
]
GUARD = {
    "point_admission": "exact current R_squared >= r_min_squared",
    "after_drift": {
        "exact_unrounded_closed_relative_segment_minimum": ">= r_min_squared",
        "stored_final_relative_position_squared": ">= r_min_squared",
        "combine": "AND",
    },
}
EVIDENCE = "current/c1b1-closure-fixes-2026-10-05"
SPEC = "specs/c1b1-independent-impulse-v1"
DOC = "docs/c1b1-independent-impulse-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def object_without_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate specification key")
        out[key] = value
    return out


def load(path):
    return json.loads(path.read_bytes(), object_pairs_hook=object_without_duplicates)


def fields_from_secondary(wire):
    match = re.match(r"^closed fixed fields only:\s*([^;]+);", wire["resource_failure_record"])
    if match is None:
        raise ValueError("secondary closed field declaration missing")
    return [part.strip() for part in match.group(1).split(",")]


def main(root, output):
    evidence, specs, docs = root / EVIDENCE, root / SPEC, root / DOC
    before = load(evidence / "receipt-before.json")
    review = load(evidence / "received/verdicts.json")
    checks = []

    def require(ok, name, detail=None):
        if not ok:
            raise ValueError("static check failed: " + name)
        checks.append({"check": name, "result": "PASS", "detail": detail})

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    require(before["audited_commit"] == BASE == review["audited_commit"], "baseline binding")
    require(review["overall"] == "CLOSURE REVISION REQUIRED" and not review["implementation_may_start"],
            "historical finding preserved")
    current = {p.name: load(p) for p in specs.glob("*.json")}
    old = {p.name: load(p) for p in (evidence / "before-specs").glob("*.json")}
    hashes = {p.name: sha(p.read_bytes()) for p in specs.glob("*.json")}
    for name, value in current.items():
        require((specs / name).read_bytes() == canonical(value), "canonical bytes: " + name)
        require((specs / (name + ".sha256")).read_bytes() == (hashes[name] + "  " + name + "\n").encode(),
                "sidecar: " + name)

    wire = current["proof-wire.json"]
    a, b = wire["closed_object_keys"]["Failure"], fields_from_secondary(wire)
    require(a == b == FAILURE_FIELDS and len(a) == len(set(a)), "Failure closed key sets equal", a)
    require("required Failure field" in wire["resource_kind_rule"]
            and "null for nonresource failure" in wire["resource_kind_rule"],
            "resource_kind required; nonresource null")
    b4 = (docs / "B4-proof-wire-resource.md").read_text(encoding="utf-8")
    failure_row = next(line for line in b4.splitlines() if line.startswith("| Failure |"))
    md_fields = re.findall(r"\b([a-z][a-z0-9_]*)[:=]", failure_row)
    require(md_fields == FAILURE_FIELDS, "Failure markdown keys equal JSON keys")
    require(wire["limits"] == old["proof-wire.json"]["limits"]
            and wire["limits"]["failure_record_bytes"] == "4096", "wire caps unchanged")
    layers = current["status-composition.json"]["layers"]
    failure = {key: "f" * 64 for key in FAILURE_FIELDS}
    failure.update(schema="LAB_C1B1_IMPULSE_FAILURE_V1",
                   status={k: max(v, key=len) for k, v in layers.items()},
                   phase=max(wire["phases"], key=len), reason=max(wire["reasons"], key=len),
                   resource_kind=max(wire["resource_kinds"], key=len), attempt_count=None)
    failure_bytes = len(canonical(failure))
    require(failure_bytes <= 4096, "closed failure envelope byte upper bound", failure_bytes)
    old_wire = old["proof-wire.json"]
    require(set(old_wire["closed_object_keys"]["Failure"]) - set(fields_from_secondary(old_wire))
            == {"resource_kind"}, "historical F-CLOSURE-2 conflict retained in archive")

    domain = current["physical-domain.json"]
    require(domain["guard_contract"] == GUARD, "point / exact segment / stored final point contract")
    b3 = (docs / "B3-physical-domain.md").read_text(encoding="utf-8")
    clauses = ["exact current R² >= r_min²",
               "minimum over the exact unrounded closed relative segment >= r_min²",
               "stored final relative position squared >= r_min²"]
    require(all(c in b3 for c in clauses) and "    AND\n" in b3,
            "B3 markdown has both after-drift conjuncts")
    phrase = ("minimum over exact unrounded closed relative segment >= r_min_squared AND "
              "stored final relative position squared >= r_min_squared")
    require(phrase in current["status-composition.json"]["future_KDK"], "B8 JSON guard reference")
    b8 = (docs / "B8-status-composition.md").read_text(encoding="utf-8")
    require("exact unrounded closed relative segment minimum >= r_min² AND "
            "stored final relative position squared >= r_min²" in b8, "B8 markdown guard reference")
    forbidden = ["future exact and stored drift segment guards", "exact/stored full segment guards",
                 "exact/stored 전체 segment guards", "exact segment와 저장 segment 각각",
                 "minimum over the stored rounded segment"]
    active_files = list(specs.glob("*.json")) + list(docs.glob("*.md"))
    require(not any(term in p.read_text(encoding="utf-8") for p in active_files for term in forbidden),
            "forbidden guard requirements absent from active normative files")

    allowed = {
        "physical-domain.json": {"dependencies", "applies_to", "cases", "guard_contract"},
        "proof-wire.json": {"dependencies", "resource_failure_record"},
        "status-composition.json": {"dependencies", "future_KDK"},
        "package-manifest.json": {"dependencies", "semantic_bundle_sha256", "revision", "review_state"},
    }
    for name, value in current.items():
        skip = allowed.get(name, {"dependencies"})
        require({k: v for k, v in value.items() if k not in skip}
                == {k: v for k, v in old[name].items() if k not in skip},
                "no unrelated semantic redesign: " + name)
    require({k: v for k, v in domain["cases"].items() if k != "R=r_min"}
            == {k: v for k, v in old["physical-domain.json"]["cases"].items() if k != "R=r_min"},
            "other admission cases unchanged")
    secondary_fix = old_wire["resource_failure_record"].replace(
        "schema,status,phase,reason,spec_sha256", "schema,status,phase,reason,resource_kind,spec_sha256")
    require(wire["resource_failure_record"] == secondary_fix, "F-CLOSURE-2 exact minimal delta")
    external = {
        "P0_raw_sha256": root / "current/c1b1-impulse-design-conditions-2026-10-04/provenance/P0-S2_ar2_pot.f90.raw",
        "source_recovery_sha256": root / "current/c1b1-impulse-design-conditions-2026-10-04/provenance/source-recovery.json",
    }
    edges = []
    for name, value in current.items():
        for key, digest in value["dependencies"].items():
            target = next((n for n, h in hashes.items() if h == digest), None)
            require(target is not None or (key in external and sha(external[key].read_bytes()) == digest),
                    "dependency: " + name + ":" + key)
            if target:
                edges.append((name, target))
    require(current["package-manifest.json"]["dependencies"]
            == {n: h for n, h in hashes.items() if n != "package-manifest.json"}, "manifest member hashes")
    require(current["package-manifest.json"]["semantic_bundle_sha256"] == hashes["semantic-bundle.json"],
            "manifest semantic bundle hash")
    old_hashes = {p.name: sha(p.read_bytes()) for p in (evidence / "before-specs").glob("*.json")}
    stale = {h for n, h in old_hashes.items() if hashes[n] != h}
    require(not any(h in p.read_text(encoding="utf-8") for p in active_files for h in stale),
            "old changed hashes absent from active normative reverse references")

    ledger = (docs / "obligation-ledger.md").read_text(encoding="utf-8")
    rows = {parts[1].strip(): (parts[3].strip(), parts[4].strip())
            for line in ledger.splitlines() if re.match(r"^\| I\d+ \|", line)
            for parts in [line.split("|")]}
    for obligation in review["obligations"]:
        identity, state = obligation["id"], obligation["state"]
        expected = "FIX APPLIED / INDEPENDENT RECHECK PENDING" if identity in {"I1", "I14", "I10", "I18"} else state
        require(rows.get(identity) == (state, expected), "ledger state: " + identity)
    update = load(evidence / "audit-result-update.json")
    require(update["B5"] == "METHOD SPEC PASS / RUNTIME NUMERIC INSTANCE STILL REQUIRED BEFORE ACTIVATION",
            "B5 method PASS and activation separation")
    require(update["provenance"]["P0"]["independent_review_confirmed"]
            and update["provenance"]["constants"]["exact_transcription_independently_matched"]
            and update["provenance"]["AEV"]["exact_object_and_path_independently_verified"]
            and not update["provenance"]["AEV"]["trusted_antecedent"], "confirmed provenance; A-EV trust unchanged")

    def ratio(record):
        return Fraction(int(record["n"]), int(record["d"]))

    witness = load(evidence / "received/guard_contract_witness.json")
    threshold = ratio(witness["r_min_squared"])
    require(threshold == ratio(domain["r_min_squared_bohr2"]), "witness threshold identity")
    for name, difference, sign in [
        ("exact_segment_min", "exact_segment_minus_threshold", 1),
        ("stored_endpoint_R2", "stored_endpoint_minus_threshold", 1),
        ("stored_segment_min", "stored_segment_minus_threshold", -1),
    ]:
        delta = ratio(witness[name]) - threshold
        require(delta == ratio(witness[difference]) and delta * sign > 0,
                "recorded witness exact inequality: " + name)
    require(witness["old_contract_accepts"] and not witness["new_stored_segment_requirement_accepts"],
            "PRE-IMPLEMENTATION CONTRACT NON-EQUIVALENCE WITNESS; no kernel-bug claim")

    protected = []
    for name in ["exact_slow.py", "exact_fast.py", "exact_geometry.py", "compare.py", "contracts.py",
                 "claim_adapter.py", "semantic_manifest_v1.json", "semantic_manifest_v1.sha256"]:
        path = "independent_checker/c1b1/" + name
        data = (root / path).read_bytes()
        require(data == git("show", ANTECEDENT + ":" + path), "antecedent raw bytes: " + name)
        protected.append({"path": path, "sha256": sha(data), "antecedent_byte_identical": True})
    changed = [p for p, h in before["tracked_raw_sha256"].items() if sha((root / p).read_bytes()) != h]
    permitted_docs = {DOC + "/" + n for n in ["B1-semantic-bundle.md", "B3-physical-domain.md",
                                               "B4-proof-wire-resource.md", "B8-status-composition.md",
                                               "obligation-ledger.md", "README.md"]}
    permitted_specs = {SPEC + "/" + n + suffix for n in current if n != "constants.json" for suffix in ["", ".sha256"]}
    require(set(changed) <= permitted_docs | permitted_specs, "tracked changes limited to normative delta and IDs")
    require(not any(p.endswith(".py") or p.startswith("tests/") for p in changed),
            "existing tracked source/test bytes unchanged")
    new_files = [p for p in git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0") if p]
    new_python = [p for p in new_files if p.endswith(".py")]
    allowed_python = {"audit/c1b1-closure-fixes-2026-10-05/check_static.py", EVIDENCE + "/received/guard_contract_witness.py"}
    require(set(new_python) <= allowed_python, "no new Impulse production Python", new_python)
    for item in before["received"]:
        require(sha((evidence / "received" / item["name"]).read_bytes()) == item["sha256"],
                "historical attachment exact bytes: " + item["name"])
    frozen_docs = ["B2-units-constants-provenance.md", "B5-finite-computation-policy.md",
                   "B6-rechecker-lineage.md", "B7-acquisition-identity.md", "mutation-obligations.md"]
    require(all(sha((docs / n).read_bytes()) == before["tracked_raw_sha256"][DOC + "/" + n]
                for n in frozen_docs), "passed method/provenance/identity/mutation documents byte preserved")
    require((specs / "constants.json").read_bytes() == (evidence / "before-specs/constants.json").read_bytes(),
            "91-record constants bundle byte preserved")

    result = {
        "schema": "C1B1_CLOSURE_REVISION_STATIC_CONSISTENCY_V1", "result": "PASS",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "level": "AUTHOR STATIC CHECKS ONLY",
        "audited_baseline": BASE, "head_at_check": git("rev-parse", "HEAD").decode().strip(),
        "checks": checks, "canonical_hashes": hashes, "dependency_edges": edges,
        "protected_arithmetic_files": protected, "tracked_count_before": before["tracked_count"],
        "changed_tracked_paths": changed, "unchanged_tracked_count": before["tracked_count"] - len(changed),
        "failure_envelope_upper_bound_bytes": failure_bytes, "new_nonproduction_python": new_python,
        "witness_scope": "recorded exact rational inequalities only; segment/witness script NOT executed",
        "impulse_or_V2_executed": False, "production_tests_run": False, "mutants_run": False,
        "benchmark_run": False, "numeric_runtime_instance_issued": False,
        "implementation_may_start": False, "J_status": "J_NOT_VERIFIED", "certification": "NotCertified",
    }
    if output:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"result": "PASS", "checks": len(checks), "changed_tracked": len(changed),
                      "protected_arithmetic": len(protected), "failure_bound_bytes": failure_bytes,
                      "canonical_bundle_sha256": hashes["semantic-bundle.json"],
                      "implementation_may_start": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    main(options.repo.resolve(), options.output)
