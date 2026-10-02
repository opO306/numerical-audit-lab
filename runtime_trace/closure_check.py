"""Closure evidence checks; imports neither acquisition nor correspondence code.

This is implementation-side closure evidence, not the auditor's new verdict.
ELF headers and objdump bytes are read directly, including the preserved libc.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def load_trace(directory):
    capture = json.loads((directory / "capture.json").read_text())
    stream = (directory / "trace.jsonl").read_bytes()
    ensure(hashlib.sha256(stream).hexdigest() == capture["trace_sha256"], "trace raw SHA-256")
    rows = [json.loads(line) for line in stream.splitlines()]
    ensure(len(rows) == capture["record_count"], "trace record count")
    ensure([r["seq"] for r in rows] == list(range(len(rows))), "trace sequence")
    chain = "0" * 64
    for row in rows:
        unsigned = {k: v for k, v in row.items() if k != "chain"}
        chain = hashlib.sha256(bytes.fromhex(chain) + json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        ensure(chain == row["chain"], "trace chain")
    ensure(chain == capture["final_chain"], "trace final chain")
    return rows, capture


def elf_segments(image):
    ensure(image[:6] == b"\x7fELF\x02\x01", "ELF64 little endian required")
    start = struct.unpack_from("<Q", image, 32)[0]
    size, count = struct.unpack_from("<HH", image, 54)
    segments = []
    for i in range(count):
        kind, flags, offset, vaddr, _, filesz, memsz, _ = struct.unpack_from("<IIQQQQQQ", image, start + i * size)
        if kind == 1:
            segments.append(dict(flags=flags, offset=offset, vaddr=vaddr, filesz=filesz, memsz=memsz))
    return segments


def bind_trace(rows, capture, root):
    registry = json.loads((root / "runtime_trace/frozen_binaries/manifest.json").read_text())["modules"]
    result = []
    for digest in sorted({r["module_sha256"] for r in rows}):
        ensure(digest in registry, "missing packaged SHA-256")
        relative = Path(registry[digest])
        path = (root / relative).resolve()
        ensure(not relative.is_absolute() and path.is_relative_to(root.resolve()), "image outside package")
        image = path.read_bytes()
        ensure(hashlib.sha256(image).hexdigest() == digest, "image SHA-256 mismatch")
        segments = elf_segments(image)
        subset = [r for r in rows if r["module_sha256"] == digest]
        first = min(r["elf_address"] for r in subset)
        stop = max(r["elf_address"] + len(bytes.fromhex(r["bytes"])) for r in subset)
        text = subprocess.check_output(["objdump", "-d", "-w", f"--start-address={first}", f"--stop-address={stop}", str(path)], text=True)
        decoded = {}
        for line in text.splitlines():
            match = re.match(r"\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+)+)\s*(.+)$", line)
            if match:
                decoded[int(match[1], 16)] = (bytes.fromhex(match[2]), match[3].strip())
        for row in subset:
            bytecode = bytes.fromhex(row["bytes"])
            va = row["runtime_pc"] - row["module_load_base"]
            ensure(va == row["elf_address"], "PC/load-base/ELF mismatch")
            ensure(capture["modules"][row["module_path"]]["sha256"] == digest, "module metadata mismatch")
            segment = next((s for s in segments if s["flags"] & 1 and s["vaddr"] <= va and va + len(bytecode) <= s["vaddr"] + s["filesz"]), None)
            ensure(segment is not None, "instruction outside executable file-backed PT_LOAD")
            offset = segment["offset"] + va - segment["vaddr"]
            ensure(offset == row["elf_file_offset"], "file offset mismatch")
            ensure(image[offset:offset + len(bytecode)] == bytecode, "instruction bytes mismatch")
            mapping = row["mapping"]
            ensure(mapping["start"] <= row["runtime_pc"] < mapping["end"] and "x" in mapping["perms"], "runtime executable mapping")
            ensure(any((s["offset"] & ~4095) == mapping["file_offset"] and mapping["start"] - (s["vaddr"] & ~4095) == row["module_load_base"] for s in segments if s["flags"] & 1), "mapping/load base mismatch")
            ensure(va in decoded, "instruction absent in objdump")
            decode_bytes, assembly = decoded[va]
            ensure(decode_bytes == bytecode, "objdump instruction bytes/length mismatch")
            words = assembly.split()
            while words and words[0] in {"cs", "data16"}:
                words.pop(0)
            ensure(words and words[0] == row["opcode"], "objdump opcode mismatch")
            result.append(dict(seq=row["seq"], phase=row["phase"], module_sha256=digest,
                               runtime_pc=row["runtime_pc"], module_load_base=row["module_load_base"],
                               elf_address=va, file_offset=offset, bytes=bytecode.hex(), decode=assembly))
    return sorted(result, key=lambda r: r["seq"])


def compare_traces(old, fresh, old_capture, fresh_capture):
    keys = ["seq", "phase", "step", "module_sha256", "elf_address", "elf_file_offset", "bytes", "opcode", "kind"]
    ensure([[r[k] for k in keys] for r in old] == [[r[k] for k in keys] for r in fresh], "ELF-relative instruction stream mismatch")
    def scalar_projection(rows):
        result = []
        for row in rows:
            if row["opcode"] not in {"addsd", "subsd", "mulsd"}:
                continue
            operands = [{k: op.get(k) for k in ["kind", "register", "width", "access", "raw_bits", "constant_origin"]} for op in row["operands"]]
            destination = row["operands"][-1]["register"]
            result.append(dict(seq=row["seq"], opcode=row["opcode"], operands=operands,
                               result_bits=row["result_bits"], pre_xmm=row["pre"]["xmm"][destination],
                               post_xmm=row["post"]["xmm"][destination], pre_mxcsr=row["pre"]["mxcsr"], post_mxcsr=row["post"]["mxcsr"]))
        return result
    old_scalar, fresh_scalar = scalar_projection(old), scalar_projection(fresh)
    ensure(old_scalar == fresh_scalar, "scalar operand/result bits or MXCSR mismatch")
    ensure(old_capture["regions"][-1]["end_state"] == fresh_capture["regions"][-1]["end_state"], "endpoint mismatch")
    return dict(instruction_stream_match=True, elf_offsets_match=True, scalar_sequence_match=True,
                scalar_operand_result_bits_match=True, endpoint_match=True, record_count=len(old),
                scalar_count=len(old_scalar), runtime_pc_comparison_used=False,
                runtime_pc_differences=sum(a["runtime_pc"] != b["runtime_pc"] for a, b in zip(old, fresh)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--old", default="attempt-05")
    parser.add_argument("--fresh", default="closure-fresh-01")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    old, old_capture = load_trace(root / "runtime_trace/artifacts" / args.old)
    fresh, fresh_capture = load_trace(root / "runtime_trace/artifacts" / args.fresh)
    old_bindings = bind_trace(old, old_capture, root)
    fresh_bindings = bind_trace(fresh, fresh_capture, root)
    comparison = compare_traces(old, fresh, old_capture, fresh_capture)
    ensure([r["decode"] for r in old_bindings] == [r["decode"] for r in fresh_bindings], "ELF instruction decode comparison")
    report = dict(verdict="PASS", scope="implementation-side closure evidence; independent auditor re-audit remains pending",
                  old_attempt=args.old, fresh_attempt=args.fresh, comparison=comparison,
                  module_counts=dict(Counter(r["module_sha256"] for r in old)),
                  old_bindings=old_bindings, fresh_bindings=fresh_bindings)
    with Path(args.out).open("x") as file:
        file.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"old_bindings", "fresh_bindings"}}))


if __name__ == "__main__":
    main()
