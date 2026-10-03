"""Build and verify the regular two-step external-audit delivery.

The final build is intentionally a one-shot operation against an exclusive
destination and a clean, committed HEAD.  It preserves the exact Git snapshot,
all refs in a bundle, ignored SDD review records, and the complete numbered
attempt history.  It also proves that the public known/fresh checker resolves
packaged relative paths from a relocated checkout reconstructed from the
bundle.  No native acquisition and no network operation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Iterable
import zipfile


ROOT = Path(__file__).resolve().parents[2]
BASELINE_HEAD = "43f1e9b21a014520facb5a545846d648eb67b288"
BRANCH = "regular-2step-chain"
WORKFLOW = ROOT / ".superpowers/sdd/2026-10-03-regular-2step"
DEFAULT_HISTORY = Path("/mnt/d/numerical-audit-lab-regular-2step-delivery-2026-10-03")
PREFLIGHT_NAME = "preflight.json"
ALLOWED_BASELINE_CHANGE = {".gitattributes"}
GITATTRIBUTES_APPEND = (
    b"\n# Received Caller external audit and regular two-step evidence: raw bytes.\n"
    b"current/caller-external-audit-2026-10-03/** -text\n"
    b"runtime_trace/regular_2step/artifacts/** -text\n"
    b"current/REGULAR_2STEP_RECEIVED_AUDIT_IDENTITY.json -text\n"
    b"runtime_trace/regular_2step/COST_REPORT.json -text\n"
)
WHEEL = "audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
PINNED = {
    WHEEL: "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0",
    "audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so":
        "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
    "lab/v2_bound.py": "48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780",
}
REQUIRED_TRACKED = {
    "current/REGULAR_2STEP_STATUS.md",
    "current/REGULAR_2STEP_RECEIVED_AUDIT_IDENTITY.json",
    "runtime_trace/regular_2step/IMPLEMENTATION_REPORT.md",
    "runtime_trace/regular_2step/COST_REPORT.json",
    "runtime_trace/regular_2step/delivery.py",
    "runtime_trace/regular_2step/artifacts/validation/summary.json",
    "runtime_trace/regular_2step/artifacts/validation/source_test_map.json",
    "runtime_trace/regular_2step/artifacts/validation/protected_baseline.json",
    "runtime_trace/regular_2step/artifacts/validation/mutation_replay.json",
    "runtime_trace/regular_2step/artifacts/derived/known/chain.json",
    "runtime_trace/regular_2step/artifacts/derived/fresh/chain.json",
    "runtime_trace/regular_2step/artifacts/mutations/manifest.json",
    "docs/superpowers/specs/2026-10-03-regular-2step-design.md",
    "docs/superpowers/plans/2026-10-03-regular-2step.md",
}
SOURCE_TEST_MAP = "runtime_trace/regular_2step/artifacts/validation/source_test_map.json"
REVIEWED_TESTED_RECEIPT = "final-reviewed-tested-head.json"
REQUIRED_REVIEW_DISPOSITIONS = {
    "task-3-review.md": "HISTORICAL_NEEDS_FIXES",
    "task-3-fix1-review.md": "APPROVED",
    "whole-branch-review.md": "APPROVED",
}
REQUIRED_WORKFLOW = {
    "task-1-brief.md", "task-1-report.md", "task-1-review.md",
    "task-1-fix1-report.md", "task-1-fix1-review.md",
    "task-1-fix2-report.md", "task-1-fix2-review.md",
    "task-2-brief.md", "task-2-report.md", "task-2-review.md",
    "task-2-fix1-report.md", "task-2-fix1-review.md",
    "task-3-brief.md", "task-3-context.md", "task-3-report.md", "task-3-review.md",
    "task-3-fix1-report.md", "task-3-fix1-review.md", "whole-branch-review.md",
    REVIEWED_TESTED_RECEIPT, "progress.md",
}
AUDIT_HOOK = r'''import json, os, sys
_fd = os.open(os.environ["REGULAR2_AUDIT_LOG"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
_denied = {os.path.realpath(path) for path in json.loads(os.environ["REGULAR2_DENIED_PATHS"])}
def _record(value):
    os.write(_fd, (json.dumps(value, sort_keys=True) + "\n").encode())
def _hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        path = os.path.realpath(os.fsdecode(args[0]))
        if path in _denied or path.startswith(os.environ["REGULAR2_DENIED_ROOT"] + os.sep):
            _record({"event": "DENIED_OPEN", "path": path})
            raise PermissionError("delivery relocation denied original evidence path: " + path)
        if path.startswith(os.environ["REGULAR2_RELOCATED_ROOT"] + os.sep):
            _record({"event": "OPEN", "path": path})
    elif event == "subprocess.Popen":
        argv = args[1] if len(args) > 1 else []
        rendered = [os.fsdecode(item) for item in argv] if isinstance(argv, (list, tuple)) else [str(argv)]
        resolved = [os.path.realpath(item) for item in rendered if os.path.isabs(item)]
        if any(path in _denied or path.startswith(os.environ["REGULAR2_DENIED_ROOT"] + os.sep)
               for path in resolved):
            _record({"event": "DENIED_SUBPROCESS", "argv": rendered})
            raise PermissionError("delivery relocation denied original evidence subprocess path")
        _record({"event": "SUBPROCESS", "argv": rendered})
sys.addaudithook(_hook)
'''


class SealRefused(ValueError):
    """The final reviewed/tested HEAD binding is absent or inconsistent."""


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def run(command: list[str], cwd: Path, *, env: dict[str, str] | None = None,
        check: bool = True) -> dict:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    receipt = {
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if check and completed.returncode:
        raise RuntimeError(json.dumps(receipt, indent=2))
    return receipt


def git_text(*args: str, cwd: Path = ROOT) -> str:
    return run(["git", *args], cwd)["stdout"].strip()


def git_bytes(spec: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", "show", spec], cwd=cwd)


def tree_blobs(revision: str, root: Path) -> dict[str, str]:
    output = run(["git", "ls-tree", "-r", revision], root)["stdout"]
    result = {}
    for line in output.splitlines():
        metadata, relative = line.split("\t", 1)
        _, kind, blob = metadata.split()
        if kind == "blob":
            result[relative] = blob
    return result


def archive_files(revision: str, root: Path) -> dict[str, bytes]:
    raw = subprocess.check_output(["git", "archive", "--format=tar", revision], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        return {member.name: archive.extractfile(member).read()
                for member in archive.getmembers() if member.isfile()}


def verify_baseline(root: Path, history: Path, head: str | None = None) -> dict:
    """Verify the original 1,488 raw files and blobs plus current pins."""
    preflight_path = history / PREFLIGHT_NAME
    preflight = read_json(preflight_path)
    if preflight["base_head"] != BASELINE_HEAD:
        raise ValueError("unexpected baseline HEAD")
    baseline = preflight["baseline_files"]
    if len(baseline) != 1488:
        raise ValueError(f"baseline file count is {len(baseline)}, expected 1488")
    head = head or git_text("rev-parse", "HEAD", cwd=root)
    baseline_blobs = tree_blobs(BASELINE_HEAD, root)
    current_blobs = tree_blobs(head, root)
    baseline_raw_files = archive_files(BASELINE_HEAD, root)
    mismatches = []
    authorized_metadata = []
    preserved = 0
    for relative, expected in sorted(baseline.items()):
        baseline_blob = baseline_blobs.get(relative)
        baseline_raw = baseline_raw_files.get(relative, b"")
        if baseline_blob != expected["git_blob"] or sha_bytes(baseline_raw) != expected["sha256"]:
            mismatches.append({"path": relative, "stage": "baseline", "expected": expected,
                               "actual_blob": baseline_blob, "actual_sha256": sha_bytes(baseline_raw)})
            continue
        if relative in ALLOWED_BASELINE_CHANGE:
            working_raw = (root / relative).read_bytes()
            expected_current = baseline_raw + GITATTRIBUTES_APPEND
            if working_raw != expected_current:
                mismatches.append({"path": relative, "stage": "authorized metadata delta",
                                   "expected_sha256": sha_bytes(expected_current),
                                   "actual_sha256": sha_bytes(working_raw)})
            else:
                authorized_metadata.append({"path": relative,
                                            "baseline_sha256": expected["sha256"],
                                            "current_sha256": sha_bytes(working_raw),
                                            "exact_append_sha256": sha_bytes(GITATTRIBUTES_APPEND)})
            continue
        current_blob = current_blobs.get(relative)
        working = root / relative
        current_sha = sha_file(working) if working.is_file() else None
        if current_blob != expected["git_blob"] or current_sha != expected["sha256"]:
            mismatches.append({"path": relative, "stage": "current", "expected": expected,
                               "actual_blob": current_blob, "actual_sha256": current_sha})
        else:
            preserved += 1
    pins = []
    for relative, expected in PINNED.items():
        actual = sha_file(root / relative)
        pins.append({"path": relative, "expected_sha256": expected, "actual_sha256": actual,
                     "match": actual == expected})
    if mismatches or not all(item["match"] for item in pins):
        raise ValueError("protected baseline or pinned source mismatch")
    return {
        "schema": "regular-2step-protected-baseline-v1",
        "baseline_head": BASELINE_HEAD,
        "tested_head": head,
        "baseline_files": len(baseline),
        "byte_and_blob_preserved": preserved,
        "authorized_metadata_delta": authorized_metadata,
        "mismatches": mismatches,
        "pinned": pins,
        "received_audit_zip_sha256": preflight["received_audit_zip_sha256"],
        "received_audit_report_sha256": preflight["received_audit_report_sha256"],
        "verdict": "PASS",
    }


def tracked_source_map(root: Path, head: str) -> dict:
    committed = archive_files(head, root)
    blobs = tree_blobs(head, root)
    paths = sorted(path for path in committed if path.endswith(".py"))
    entries = []
    for relative in paths:
        raw = committed[relative]
        entries.append({"path": relative, "git_blob": blobs[relative],
                        "sha256": sha_bytes(raw), "bytes": len(raw),
                        "lines": len(raw.splitlines())})
    return {"schema": "regular-2step-tested-python-source-map-v1", "git_head": head,
            "files": entries, "count": len(entries)}


def _is_new_package_python(relative: str) -> bool:
    package = "runtime_trace/regular_2step/"
    if not relative.startswith(package) or not relative.endswith(".py"):
        return False
    suffix = relative[len(package):]
    return "/" not in suffix or (suffix.startswith("tests/") and "/" not in suffix[6:])


def validate_reviewed_tested_seal(committed: dict[str, bytes], workflow: Path,
                                  head: str) -> dict:
    """Bind current archive bytes to tested sources and both completed reviews."""
    if SOURCE_TEST_MAP not in committed:
        raise SealRefused("saved source map is absent from committed archive")
    map_raw = committed[SOURCE_TEST_MAP]
    try:
        source_map = json.loads(map_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SealRefused("saved source map is invalid") from error
    if source_map.get("schema") != "regular-2step-final-source-test-map-v1":
        raise SealRefused("saved source map schema mismatch")

    expected = {}
    sections = ("production", "tests", "documentation")
    for section in sections:
        entries = source_map.get(section)
        if not isinstance(entries, list):
            raise SealRefused(f"saved source map section is invalid: {section}")
        for identity in entries:
            relative = identity.get("path") if isinstance(identity, dict) else None
            if not isinstance(relative, str) or relative in expected:
                raise SealRefused("saved source map has invalid or duplicate path")
            expected[relative] = identity

    expected_python = {
        identity["path"] for section in ("production", "tests")
        for identity in source_map[section]
    }
    actual_python = {relative for relative in committed if _is_new_package_python(relative)}
    if expected_python != actual_python:
        raise SealRefused("tested Python path set differs from current archive")

    checked = []
    for relative, identity in sorted(expected.items()):
        raw = committed.get(relative)
        if raw is None:
            raise SealRefused(f"mapped source is absent from current archive: {relative}")
        actual = {"sha256": sha_bytes(raw), "bytes": len(raw),
                  "physical_lines": len(raw.splitlines())}
        if any(identity.get(key) != value for key, value in actual.items()):
            raise SealRefused(f"source identity differs from saved tested map: {relative}")
        checked.append({"path": relative, **actual})

    receipt_path = workflow / REVIEWED_TESTED_RECEIPT
    if not receipt_path.is_file():
        raise SealRefused(f"reviewed/tested HEAD receipt is absent: {REVIEWED_TESTED_RECEIPT}")
    try:
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SealRefused("reviewed/tested HEAD receipt is invalid") from error
    if receipt.get("schema") != "regular-2step-final-reviewed-tested-head-v1":
        raise SealRefused("reviewed/tested HEAD receipt schema mismatch")
    if receipt.get("git_head") != head:
        raise SealRefused("reviewed/tested HEAD receipt HEAD mismatch")
    map_pin = receipt.get("source_test_map")
    if map_pin != {"path": SOURCE_TEST_MAP, "sha256": sha_bytes(map_raw)}:
        raise SealRefused("reviewed/tested HEAD source-map identity mismatch")
    if receipt.get("review_gate") != "APPROVED":
        raise SealRefused("reviewed/tested HEAD receipt is not approved")

    reviews = receipt.get("reviews")
    if not isinstance(reviews, list):
        raise SealRefused("review inventory is invalid")
    by_path = {}
    for item in reviews:
        relative = item.get("path") if isinstance(item, dict) else None
        if not isinstance(relative, str) or relative in by_path:
            raise SealRefused("review inventory has invalid or duplicate path")
        by_path[relative] = item
    if set(by_path) != set(REQUIRED_REVIEW_DISPOSITIONS):
        raise SealRefused("review inventory does not contain the exact required gates")
    review_identity = []
    for relative, disposition in REQUIRED_REVIEW_DISPOSITIONS.items():
        review_path = workflow / relative
        if not review_path.is_file():
            raise SealRefused(f"required review file is absent: {relative}")
        raw = review_path.read_bytes()
        expected_item = {"path": relative, "sha256": sha_bytes(raw),
                         "disposition": disposition}
        if by_path[relative] != expected_item:
            raise SealRefused(f"review identity or disposition mismatch: {relative}")
        review_identity.append(expected_item)
    return {
        "schema": "regular-2step-reviewed-tested-seal-verification-v1",
        "git_head": head,
        "source_test_map": map_pin,
        "source_test_map_entries": checked,
        "tested_python_files": len(expected_python),
        "mapped_documentation_files": len(source_map["documentation"]),
        "receipt": {"path": REVIEWED_TESTED_RECEIPT,
                    "sha256": sha_bytes(receipt_raw)},
        "reviews": review_identity,
        "review_gate": "APPROVED",
        "verdict": "PASS",
    }


def add_file(zout: zipfile.ZipFile, manifest: dict, source: Path, arcname: str) -> None:
    data = source.read_bytes()
    if arcname in manifest:
        raise ValueError(f"duplicate package member: {arcname}")
    zout.writestr(arcname, data)
    manifest[arcname] = {"sha256": sha_bytes(data), "bytes": len(data)}


def add_tree(zout: zipfile.ZipFile, manifest: dict, source: Path, prefix: str,
             *, excluded: Iterable[Path] = ()) -> None:
    excluded_resolved = [path.resolve() for path in excluded]
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if any(resolved == item or item in resolved.parents for item in excluded_resolved):
            continue
        add_file(zout, manifest, path, f"{prefix}/{path.relative_to(source).as_posix()}")


def validate_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        bad = archive.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failure: {bad}")
        package_manifest = json.loads(archive.read("PACKAGE_MANIFEST.json"))
        expected = package_manifest["members"]
        if set(names) != set(expected) | {"PACKAGE_MANIFEST.json"}:
            raise ValueError("ZIP member set differs from manifest")
        for name, identity in expected.items():
            raw = archive.read(name)
            if sha_bytes(raw) != identity["sha256"] or len(raw) != identity["bytes"]:
                raise ValueError(f"ZIP member identity mismatch: {name}")
    return {"schema": "regular-2step-zip-verification-v1", "zip": path.name,
            "zip_sha256": sha_file(path), "zip_bytes": path.stat().st_size,
            "payload_members": len(expected), "crc": "PASS", "member_hashes": "PASS"}


def verify_delivery(directory: Path) -> dict:
    directory = Path(directory).resolve()
    receipt = read_json(directory / "delivery_receipt.json")
    package = directory / receipt["zip_file"]
    verified = validate_zip(package)
    if verified["zip_sha256"] != receipt["zip_sha256"] or verified["zip_bytes"] != receipt["zip_bytes"]:
        raise ValueError("delivery receipt differs from final ZIP")
    sidecar = (directory / (package.name + ".sha256")).read_text(encoding="ascii").strip()
    if sidecar != f"{verified['zip_sha256']}  {package.name}":
        raise ValueError("ZIP SHA sidecar mismatch")
    return verified


def build(out: Path, history: Path) -> dict:
    out, history = Path(out).resolve(), Path(history).resolve()
    if out.exists():
        raise ValueError("exclusive destination already exists")
    if not history.is_dir() or not (history / PREFLIGHT_NAME).is_file():
        raise ValueError("attempt-history root with preflight.json required")
    if history == out or out in history.parents:
        raise ValueError("destination cannot contain the attempt-history root")
    if git_text("status", "--porcelain", cwd=ROOT):
        raise ValueError("clean committed HEAD required")
    head = git_text("rev-parse", "HEAD", cwd=ROOT)
    branch = git_text("branch", "--show-current", cwd=ROOT)
    if branch != BRANCH:
        raise ValueError(f"wrong branch: {branch}")
    tracked = set(git_text("ls-files", cwd=ROOT).splitlines())
    missing = sorted(REQUIRED_TRACKED - tracked)
    if missing:
        raise ValueError(f"required tracked delivery inputs absent: {missing}")
    workflow_names = {path.name for path in WORKFLOW.iterdir() if path.is_file()}
    if not REQUIRED_WORKFLOW <= workflow_names:
        raise ValueError(f"required workflow records absent: {sorted(REQUIRED_WORKFLOW - workflow_names)}")
    committed = archive_files(head, ROOT)
    reviewed_tested = validate_reviewed_tested_seal(committed, WORKFLOW, head)
    protected = verify_baseline(ROOT, history, head)
    source_map = tracked_source_map(ROOT, head)

    with tempfile.TemporaryDirectory(prefix="regular-2step-delivery-") as temporary:
        stage = Path(temporary)
        snapshot = stage / "regular-2step-head.tar"
        bundle = stage / "regular-2step-all.bundle"
        bare = stage / "recovered.git"
        relocated = stage / "relocated"
        run(["git", "archive", "--format=tar", f"--output={snapshot}", head], ROOT)
        run(["git", "bundle", "create", str(bundle), "--all"], ROOT)
        bundle_verify = run(["git", "bundle", "verify", str(bundle)], ROOT)
        clone_bare = run(["git", "clone", "--bare", str(bundle), str(bare)], stage)
        fsck = run(["git", "fsck", "--full", "--strict"], bare)
        recovered_head = git_text("rev-parse", f"refs/heads/{BRANCH}", cwd=bare)
        if recovered_head != head:
            raise ValueError("bare recovery branch HEAD mismatch")
        ancestry = run(["git", "merge-base", "--is-ancestor", BASELINE_HEAD, head], bare)
        run(["git", "clone", str(bundle), str(relocated)], stage)
        run(["git", "checkout", "--detach", head], relocated)
        relocated_archive = stage / "relocated-head.tar"
        run(["git", "archive", "--format=tar", f"--output={relocated_archive}", head], relocated)
        if sha_file(snapshot) != sha_file(relocated_archive):
            raise ValueError("relocated exact-HEAD archive mismatch")
        hook = stage / "audit-hook"
        hook.mkdir()
        (hook / "sitecustomize.py").write_text(AUDIT_HOOK, encoding="utf-8")
        semantic = []
        for case in ("known", "fresh"):
            capture_dir = relocated / f"runtime_trace/regular_2step/artifacts/{case}-03"
            derived_dir = relocated / f"runtime_trace/regular_2step/artifacts/derived/{case}"
            capture_doc = read_json(capture_dir / "capture.json")
            denied_module_paths = sorted({module["captured_path"]
                                          for module in capture_doc["modules"].values()})
            resolver_paths = sorted({str((relocated / module["resolver_path"]).resolve())
                                     for module in capture_doc["modules"].values()})
            audit_log = stage / f"{case}-path-audit.jsonl"
            env = dict(os.environ)
            env.update({
                "PYTHONPATH": str(hook) + os.pathsep + str(relocated),
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "REGULAR2_AUDIT_LOG": str(audit_log),
                "REGULAR2_DENIED_ROOT": str(ROOT.resolve()),
                "REGULAR2_RELOCATED_ROOT": str(relocated.resolve()),
                "REGULAR2_DENIED_PATHS": json.dumps(denied_module_paths),
            })
            command = [sys.executable, "-m", "runtime_trace.regular_2step.checker",
                       "--root", str(relocated), "--capture",
                       str(capture_dir), "--derived", str(derived_dir)]
            execution = run(command, relocated, env=env)
            audit_events = [json.loads(line) for line in audit_log.read_text().splitlines()]
            opened = {event["path"] for event in audit_events if event["event"] == "OPEN"}
            subprocess_argv = [event["argv"] for event in audit_events if event["event"] == "SUBPROCESS"]
            required_reads = {
                str((relocated / "runtime_trace/regular_2step/checker.py").resolve()),
                str((capture_dir / "capture.json").resolve()),
                str((capture_dir / "trace.jsonl").resolve()),
                str((derived_dir / "numeric_ir.json").resolve()),
                str((derived_dir / "v2_correspondence.json").resolve()),
                str((derived_dir / "chain.json").resolve()),
                *resolver_paths,
            }
            missing_reads = sorted(required_reads - opened)
            objdump_targets = {item for argv in subprocess_argv if argv and "objdump" in Path(argv[0]).name
                               for item in argv if os.path.isabs(item)}
            missing_objdump = sorted(set(resolver_paths) - objdump_targets)
            denied_events = [event for event in audit_events if event["event"].startswith("DENIED")]
            if missing_reads or missing_objdump or denied_events:
                raise ValueError(f"relocated path audit failed for {case}: "
                                 f"reads={missing_reads}, objdump={missing_objdump}, denied={denied_events}")
            path_audit = {
                "denied_original_checkout": str(ROOT.resolve()),
                "denied_captured_module_paths": denied_module_paths,
                "required_relocated_reads": sorted(required_reads),
                "observed_relocated_reads": sorted(opened),
                "objdump_argv": subprocess_argv,
                "verdict": "PASS",
            }
            semantic.append({"case": case, **execution, "path_audit": path_audit})

        recovery = {
            "schema": "regular-2step-bundle-recovery-v1", "head": head,
            "branch": branch, "base_ancestor": BASELINE_HEAD,
            "snapshot_sha256": sha_file(snapshot), "snapshot_bytes": snapshot.stat().st_size,
            "bundle_sha256": sha_file(bundle), "bundle_bytes": bundle.stat().st_size,
            "bundle_verify": bundle_verify, "bare_clone": clone_bare, "fsck": fsck,
            "ancestry": ancestry, "recovered_branch_head": recovered_head,
            "relocated_snapshot_equal": True, "relocated_public_checkers": semantic,
            "native_acquisition_performed": False, "network_operation_performed": False,
        }
        write_json(stage / "protected_baseline.json", protected)
        write_json(stage / "tested_source_map.json", source_map)
        write_json(stage / "reviewed_tested_head_verification.json", reviewed_tested)
        write_json(stage / "recovery_verification.json", recovery)

        out.mkdir(parents=True)
        package = out / "regular-2step-audit-delivery-2026-10-03.zip"
        members = {}
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
                             allowZip64=True) as archive:
            add_file(archive, members, snapshot, "git/regular-2step-head.tar")
            add_file(archive, members, bundle, "git/regular-2step-all.bundle")
            add_file(archive, members, stage / "protected_baseline.json", "verification/protected_baseline.json")
            add_file(archive, members, stage / "tested_source_map.json", "verification/tested_source_map.json")
            add_file(archive, members, stage / "reviewed_tested_head_verification.json",
                     "verification/reviewed_tested_head_verification.json")
            add_file(archive, members, stage / "recovery_verification.json", "verification/recovery_verification.json")
            add_tree(archive, members, WORKFLOW, "workflow")
            add_tree(archive, members, history, "attempt-history", excluded=[out])
            package_manifest = {
                "schema": "regular-2step-audit-delivery-v1", "git_head": head,
                "branch": branch, "baseline_head": BASELINE_HEAD,
                "members": members, "payload_member_count": len(members),
                "regular_2step_status": "IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING",
                "reviewed_tested_head_gate": "PASS",
                "reviewed_tested_receipt_sha256": reviewed_tested["receipt"]["sha256"],
                "push": "AUTHORIZED / NOT YET EXECUTED AT PACKAGE SEAL",
            }
            archive.writestr("PACKAGE_MANIFEST.json",
                             (json.dumps(package_manifest, indent=2, sort_keys=True) + "\n").encode())
        verified = validate_zip(package)
        receipt = {
            "schema": "regular-2step-final-delivery-receipt-v1", "zip_file": package.name,
            "zip_sha256": verified["zip_sha256"], "zip_bytes": verified["zip_bytes"],
            "git_head": head, "branch": branch, "payload_members": verified["payload_members"],
            "snapshot_sha256": recovery["snapshot_sha256"], "bundle_sha256": recovery["bundle_sha256"],
            "bare_recovery_fsck": "PASS", "baseline_ancestry": "PASS",
            "relocated_known_checker": "CHECKER_PASS", "relocated_fresh_checker": "CHECKER_PASS",
            "reviewed_tested_head_gate": "PASS",
            "reviewed_tested_receipt_sha256": reviewed_tested["receipt"]["sha256"],
            "push": "AUTHORIZED / NOT YET EXECUTED AT PACKAGE SEAL",
            "independent_audit": "PENDING",
        }
        write_json(out / "delivery_receipt.json", receipt)
        (out / (package.name + ".sha256")).write_text(
            f"{verified['zip_sha256']}  {package.name}\n", encoding="ascii")
        (out / "DELIVERY.md").write_text(
            "# Regular 2-Step Chain audit delivery\n\n"
            f"ZIP: `{package.name}`\n\nSHA-256: `{verified['zip_sha256']}`\n\n"
            f"Bytes: `{verified['zip_bytes']}`\n\nGit HEAD: `{head}`\n\nBranch: `{branch}`\n\n"
            "Status: IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING.\n\n"
            "Push was authorized but had not been executed when this package was sealed.\n",
            encoding="utf-8")
    verify_delivery(out)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--verify-baseline", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_delivery(args.verify), indent=2, sort_keys=True))
        return 0
    if args.verify_baseline:
        print(json.dumps(verify_baseline(ROOT, args.history), indent=2, sort_keys=True))
        return 0
    if args.out is None:
        parser.error("--out is required for a final build")
    print(json.dumps(build(args.out, args.history), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
