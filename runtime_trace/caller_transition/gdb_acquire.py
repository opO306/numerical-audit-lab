"""GDB Python acquisition: first-step RET through second-step entry, body excluded."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time

import gdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.caller_transition.module_resolver import resolve_module
from runtime_trace.caller_transition.write_effects import EffectsRefused, possible_writes
from runtime_trace.semantics import effective_address, split_operands

OUT = Path(os.environ["RT_OUTPUT"])
LABEL = os.environ["CT_ANTECEDENT_LABEL"]
STEP_SYMBOL = "_ZL66__pyx_f_4gala_9integrate_13cyintegrators_8leapfrog_c_leapfrog_stepP11_CPotentialmiddPdS1_S1_S1_"
WHEEL = ROOT / "audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
WHEEL_SHA = "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"
GPRS = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp", "r8", "r9",
        "r10", "r11", "r12", "r13", "r14", "r15", "rip"]


def hx(raw):
    return f"0x{int.from_bytes(raw, 'little'):0{len(raw) * 2}x}"


def elf_segments(raw):
    if raw[:6] != b"\x7fELF\x02\x01":
        raise EffectsRefused("not ELF64 little endian")
    offset = struct.unpack_from("<Q", raw, 32)[0]
    size, count = struct.unpack_from("<HH", raw, 54)
    result = []
    for i in range(count):
        kind, flags, file_offset, vaddr, _, filesz, memsz, _ = struct.unpack_from(
            "<IIQQQQQQ", raw, offset + i * size
        )
        if kind == 1:
            result.append({"file_offset": file_offset, "vaddr": vaddr, "filesz": filesz,
                           "memsz": memsz, "flags": flags})
    return result


class Acquisition:
    def __init__(self):
        if hashlib.sha256(WHEEL.read_bytes()).hexdigest() != WHEEL_SHA:
            raise EffectsRefused("wheel hash mismatch")
        self.started = time.perf_counter()
        self.inferior_pid = None
        self.owner = None
        self.maps = []
        self.map_snapshots = []
        self.modules = {}
        self.records = 0
        self.chain = "0" * 64
        self.trace = (OUT / "caller_trace.jsonl").open("x", encoding="utf-8", newline="\n")
        self.first_step_entry = None
        self.first_step_return = None
        self.second_step_entry = None
        self.opcodes = {}
        self.rows = []

    def refresh_maps(self, stage):
        rows = []
        path = Path(f"/proc/{self.inferior_pid}/maps")
        for line in path.read_text().splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) < 5:
                continue
            start, end = [int(x, 16) for x in parts[0].split("-")]
            rows.append({"start": start, "end": end, "perms": parts[1],
                         "file_offset": int(parts[2], 16), "dev": parts[3],
                         "inode": int(parts[4]), "path": parts[5] if len(parts) == 6 else ""})
        self.maps = rows
        self.map_snapshots.append({"stage": stage, "maps": rows})

    def module_at(self, address):
        mapping = next((m for m in self.maps if m["start"] <= address < m["end"] and m["path"].startswith("/")), None)
        if mapping is None:
            raise EffectsRefused(f"instruction address has no file mapping: {address:#x}")
        path = mapping["path"]
        if path not in self.modules:
            raw = Path(path).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            packaged = resolve_module(ROOT, digest)
            if packaged.read_bytes() != raw:
                raise EffectsRefused("loaded module differs from SHA resolver bytes")
            segments = elf_segments(raw)
            segment = next((s for s in segments if s["file_offset"] & ~4095 == mapping["file_offset"]), None)
            if segment is None:
                raise EffectsRefused("ELF mapping has no load segment")
            base = mapping["start"] - (segment["vaddr"] & ~4095)
            self.modules[path] = {"captured_path": path, "sha256": digest,
                                  "resolver_path": str(packaged.relative_to(ROOT)),
                                  "load_base": base, "segments": segments, "_raw": raw}
        return self.modules[path], mapping

    def instruction(self):
        pc = int(gdb.newest_frame().read_register("rip"))
        item = gdb.newest_frame().architecture().disassemble(pc, count=1)[0]
        length = item.get("length") or (item["addr"] + len(bytes(gdb.selected_inferior().read_memory(pc, 15))) - pc)
        # GDB 15 supplies length. Refuse rather than infer if that contract changes.
        if "length" not in item:
            raise EffectsRefused("GDB disassembly omitted instruction length")
        return pc, int(length), item["asm"]

    def context(self):
        frame = gdb.newest_frame()
        gpr = {name: int(frame.read_register(name)) & ((1 << 64) - 1) for name in GPRS}
        xmm = {}
        for i in range(16):
            raw = frame.read_register(f"xmm{i}").bytes
            if len(raw) != 16:
                raise EffectsRefused("xmm raw width")
            xmm[f"xmm{i}"] = hx(raw)
        return {"gpr": {k: f"0x{v:016x}" for k, v in gpr.items()}, "xmm": xmm,
                "eflags": int(frame.read_register("eflags")),
                "mxcsr": int(frame.read_register("mxcsr"))}

    @staticmethod
    def numeric_registers(context):
        result = {k: int(v, 16) for k, v in context["gpr"].items()}
        result["eflags"] = context["eflags"]
        return result

    def memory(self, address, size):
        return bytes(gdb.selected_inferior().read_memory(address, size))

    def component_state(self, pointers):
        return {name: [hx(self.memory(address + offset, 8)) for offset in (0, 8)]
                for name, address in pointers.items()}

    @staticmethod
    def thread_inventory():
        selected = gdb.selected_thread()
        result = []
        for thread in gdb.selected_inferior().threads():
            result.append({"ptid": list(thread.ptid), "global_num": thread.global_num,
                           "name": thread.name, "selected_owner": thread.ptid == selected.ptid,
                           "stopped_under_all_stop": bool(thread.is_stopped())})
        return sorted(result, key=lambda item: item["global_num"])

    def abi(self):
        context = self.context()
        g = {k: int(v, 16) for k, v in context["gpr"].items()}
        gradient = int.from_bytes(self.memory(g["rsp"] + 8, 8), "little")
        pointers = {"q": g["rcx"], "full_v": g["r8"], "latent": g["r9"], "gradient": gradient}
        return {"n": g["rsi"], "half_ndim": g["rdx"], "cpointer": g["rdi"],
                "pointers": pointers,
                "t_bits": f"0x{int(context['xmm']['xmm0'], 16) & ((1 << 64) - 1):016x}",
                "dt_bits": f"0x{int(context['xmm']['xmm1'], 16) & ((1 << 64) - 1):016x}",
                "entry_pc": g["rip"], "context": context,
                "component_bits": self.component_state(pointers)}

    def one(self, phase):
        if self.records >= 100000 or time.perf_counter() - self.started > 180:
            raise EffectsRefused("caller acquisition budget exceeded")
        if gdb.selected_thread().ptid != self.owner:
            raise EffectsRefused("different thread executed caller instruction")
        pc, length, assembly = self.instruction()
        pre = self.context()
        module, mapping = self.module_at(pc)
        relative = pc - module["load_base"]
        segment = next((s for s in module["segments"] if s["vaddr"] <= relative < s["vaddr"] + s["filesz"]), None)
        if segment is None:
            raise EffectsRefused("instruction outside file-backed ELF segment")
        file_offset = segment["file_offset"] + relative - segment["vaddr"]
        raw = self.memory(pc, length)
        if module["_raw"][file_offset:file_offset + length] != raw:
            raise EffectsRefused("runtime instruction bytes differ from ELF")
        writes = possible_writes(assembly, self.numeric_registers(pre), pc, length)
        for write in writes:
            write["before_bits"] = hx(self.memory(write["address"], write["size"]))
        gdb.execute("si", to_string=True)
        post = self.context()
        for write in writes:
            write["after_bits"] = hx(self.memory(write["address"], write["size"]))
            write["value_changed"] = write["before_bits"] != write["after_bits"]
        opcode = assembly.split()[0]
        self.opcodes[opcode] = self.opcodes.get(opcode, 0) + 1
        row = {"schema": "gala-caller-transition-instruction-v1", "sequence": self.records,
               "phase": phase, "pc": pc, "next_pc": int(post["gpr"]["rip"], 16),
               "module_sha256": module["sha256"], "captured_module_path": module["captured_path"],
               "load_base": module["load_base"], "elf_address": relative,
               "file_offset": file_offset, "instruction_bytes": raw.hex(), "assembly": assembly,
               "pre": pre, "post": post, "possible_memory_writes": writes,
               "thread_ptid": list(gdb.selected_thread().ptid), "previous_chain": self.chain}
        self.chain = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        row["record_chain"] = self.chain
        self.trace.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        self.trace.flush()
        self.rows.append(row)
        self.records += 1
        return row

    @staticmethod
    def low64(context, name):
        return f"0x{int(context['xmm'][name], 16) & ((1 << 64) - 1):016x}"

    def argument_source(self, register, expected_bits):
        candidates = [row for row in self.rows
                      if self.low64(row["post"], register) == expected_bits
                      and self.low64(row["pre"], register) != expected_bits]
        if not candidates:
            raise EffectsRefused(f"no observed source load for {register}")
        row = candidates[-1]
        text = re.sub(r"\s+<[^>]*>", "", row["assembly"].split("#", 1)[0].strip())
        _, _, tail = text.partition(" ")
        operands = split_operands(tail.strip())
        if len(operands) != 2 or operands[1] != f"%{register}" or operands[0].startswith(("%", "$")):
            raise EffectsRefused(f"last {register} change is not a memory load")
        registers = {name: int(value, 16) for name, value in row["pre"]["gpr"].items()}
        address = effective_address(operands[0], registers, row["pc"], len(bytes.fromhex(row["instruction_bytes"])))
        raw = self.memory(address, 8)
        if hx(raw) != expected_bits:
            raise EffectsRefused(f"{register} source memory differs at second entry")
        return {"instruction_sequence": row["sequence"], "assembly": row["assembly"],
                "source_memory_address": address, "source_bits": hx(raw),
                "source_operand": operands[0], "destination_register": register}

    def ret_addresses(self):
        text = gdb.execute(f"disassemble {STEP_SYMBOL}", to_string=True)
        (OUT / "first_step_disassembly.txt").write_text(text, encoding="utf-8")
        found = []
        for line in text.splitlines():
            address = re.match(r"\s*(?:=>\s*)?(0x[0-9a-fA-F]+)", line)
            after_colon = line.rsplit(":", 1)[-1]
            if address and re.search(r"\bretq?\b", after_colon):
                found.append(int(address.group(1), 16))
        if not found:
            raise EffectsRefused("no return instruction decoded for first step")
        return found

    def run(self):
        step_break = gdb.Breakpoint(STEP_SYMBOL, internal=True)
        gdb.execute("run", to_string=True)
        self.inferior_pid = gdb.selected_inferior().pid
        self.owner = gdb.selected_thread().ptid
        gdb.execute("set scheduler-locking on")
        self.refresh_maps("first-step-entry")
        self.first_step_entry = {"abi": self.abi(), "inferior_pid": self.inferior_pid,
                                 "thread_ptid": list(self.owner),
                                 "thread_inventory": self.thread_inventory()}
        if self.first_step_entry["abi"]["n"] != 1 or self.first_step_entry["abi"]["half_ndim"] != 2:
            raise EffectsRefused("unexpected first-step dimensions")
        step_pc = self.first_step_entry["abi"]["entry_pc"]
        step_break.enabled = False
        return_addresses = self.ret_addresses()
        returns = [gdb.Breakpoint(f"*{address:#x}", internal=True) for address in return_addresses]
        gdb.execute("continue", to_string=True)
        if int(gdb.newest_frame().read_register("rip")) not in return_addresses:
            raise EffectsRefused("first step did not stop at decoded return")
        for breakpoint in returns:
            breakpoint.delete()
        return_pre = {"pc": int(gdb.newest_frame().read_register("rip")),
                      "context": self.context(),
                      "component_bits": self.component_state(self.first_step_entry["abi"]["pointers"])}
        ret_row = self.one("first_step_return")
        self.first_step_return = {"instruction_sequence": ret_row["sequence"], "pre": return_pre,
                                  "post_context": ret_row["post"],
                                  "post_component_bits": self.component_state(self.first_step_entry["abi"]["pointers"]),
                                  "thread_inventory": self.thread_inventory()}
        while int(gdb.newest_frame().read_register("rip")) != step_pc:
            self.one("caller")
        self.refresh_maps("second-step-entry")
        self.second_step_entry = {"abi": self.abi(), "thread_ptid": list(gdb.selected_thread().ptid),
                                  "thread_inventory": self.thread_inventory()}
        if self.second_step_entry["abi"]["t_bits"] != "0x3fa0000000000000":
            raise EffectsRefused("second-step time argument mismatch")
        if self.second_step_entry["abi"]["dt_bits"] != "0x3f90000000000000":
            raise EffectsRefused("second-step dt argument mismatch")
        self.second_step_entry["argument_sources"] = {
            "t": self.argument_source("xmm0", self.second_step_entry["abi"]["t_bits"]),
            "dt": self.argument_source("xmm1", self.second_step_entry["abi"]["dt_bits"]),
        }
        self.trace.close()
        trace_raw = (OUT / "caller_trace.jsonl").read_bytes()
        pid = self.inferior_pid
        gdb.execute("kill", to_string=True)
        return {"schema": "gala-caller-transition-capture-v1", "verdict": "CONTROLLED_STOP",
                "reason": None, "antecedent_label": LABEL, "inferior_pid": pid,
                "wheel_sha256": WHEEL_SHA, "gdb_version": gdb.VERSION,
                "first_step_entry": self.first_step_entry, "first_step_return": self.first_step_return,
                "second_step_entry": self.second_step_entry, "record_count": self.records,
                "trace_sha256": hashlib.sha256(trace_raw).hexdigest(), "final_chain": self.chain,
                "opcode_histogram": self.opcodes, "modules": {path: {k: v for k, v in data.items() if k != "_raw"}
                                                                for path, data in self.modules.items()},
                "map_snapshots": self.map_snapshots, "unknown_effects_refused": True,
                "single_thread_all_stop": {"non_stop": gdb.execute("show non-stop", to_string=True).strip(),
                                            "scheduler_locking": "on", "owner_ptid": list(self.owner)},
                "old_capture_continuation_present": False,
                "controlled_stop_receipt": {"stop_pc": step_pc, "stop_symbol": STEP_SYMBOL,
                    "before_second_step_body": True, "second_step_body_instructions_executed": 0,
                    "inferior_terminated_by_debugger": True, "harness_completed_normally": False},
                "capture_wall_seconds": time.perf_counter() - self.started}

    def failure(self, exc):
        if not self.trace.closed:
            self.trace.close()
        raw = (OUT / "caller_trace.jsonl").read_bytes()
        try:
            pid = gdb.selected_inferior().pid
            if pid:
                gdb.execute("kill", to_string=True)
        except Exception:
            pid = self.inferior_pid
        return {"schema": "gala-caller-transition-capture-v1", "verdict": "REFUSED",
                "reason": f"{type(exc).__name__}: {exc}", "antecedent_label": LABEL,
                "inferior_pid": pid, "record_count": self.records,
                "trace_sha256": hashlib.sha256(raw).hexdigest(), "final_chain": self.chain,
                "unknown_effects_refused": True, "modules": {path: {k: v for k, v in data.items() if k != "_raw"}
                                                               for path, data in self.modules.items()},
                "capture_wall_seconds": time.perf_counter() - self.started}


gdb.execute("set pagination off")
gdb.execute("set confirm off")
gdb.execute("set breakpoint pending on")
gdb.execute("set disassembly-flavor att")
gdb.execute("set debuginfod enabled off")
gdb.execute("set non-stop off")
acquisition = None
try:
    acquisition = Acquisition()
    result = acquisition.run()
except Exception as exc:
    result = acquisition.failure(exc) if acquisition is not None else {
        "schema": "gala-caller-transition-capture-v1", "verdict": "REFUSED",
        "reason": f"{type(exc).__name__}: {exc}", "antecedent_label": LABEL,
        "unknown_effects_refused": True,
    }
(OUT / "capture.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
