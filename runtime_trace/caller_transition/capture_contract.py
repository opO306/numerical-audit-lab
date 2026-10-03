import hashlib
import json

from .module_resolver import resolve_module


class CaptureRefused(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise CaptureRefused(message)


def validate_capture(capture, root):
    _require(capture.get("schema") == "gala-caller-transition-capture-v1", "capture schema")
    _require(capture.get("verdict") == "CONTROLLED_STOP", "capture is not controlled stop")
    _require(capture.get("unknown_effects_refused") is True, "unknown effects were not refused")
    receipt = capture.get("controlled_stop_receipt", {})
    _require(receipt.get("before_second_step_body") is True, "second body stop boundary")
    _require(receipt.get("second_step_body_instructions_executed") == 0, "second body executed")
    _require(receipt.get("inferior_terminated_by_debugger") is True, "inferior termination receipt")
    for module in capture.get("modules", {}).values():
        path = resolve_module(root, module["sha256"])
        _require(hashlib.sha256(path.read_bytes()).hexdigest() == module["sha256"], "module hash")
    count = capture.get("record_count")
    _require(type(count) is int and count > 0, "record count")
    for name in ["first_step_entry", "first_step_return", "second_step_entry"]:
        _require(type(capture.get(name)) is dict, f"missing {name}")
    return {"verdict": capture["verdict"], "record_count": count,
            "body_instructions_executed": receipt["second_step_body_instructions_executed"]}


def validate_trace_bytes(capture, raw):
    _require(hashlib.sha256(raw).hexdigest() == capture.get("trace_sha256"), "trace hash")
    lines = raw.splitlines()
    _require(len(lines) == capture.get("record_count"), "record count")
    chain = "0" * 64
    for expected, line in enumerate(lines):
        row = json.loads(line)
        _require(row.get("sequence") == expected, "trace sequence")
        _require(row.get("previous_chain") == chain, "trace previous chain")
        payload = {k: v for k, v in row.items() if k != "record_chain"}
        chain = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        _require(row.get("record_chain") == chain, "trace record chain")
    _require(chain == capture.get("final_chain"), "trace final chain")
    return [json.loads(line) for line in lines]
