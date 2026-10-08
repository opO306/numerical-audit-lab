"""GDB Python acquisition, hard limited to frozen gala regular init + one step.

Run only via run.py. Every completed stepi writes one record; no replay/template reads.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import zipfile

import gdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime_trace.semantics import (ARITHMETIC, GPRS, Refused, check_finite, check_mxcsr,
                                     decode, effective_address, register_width, routing_widths)

OUT = Path(os.environ["RT_OUTPUT"])
WHEEL = ROOT / "audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
EXPECTED_WHEEL = "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"
SYMBOLS = {
    "init": "_ZL66__pyx_f_4gala_9integrate_13cyintegrators_8leapfrog_c_init_velocityP11_CPotentialmiddPdS1_S1_S1_",
    "step": "_ZL66__pyx_f_4gala_9integrate_13cyintegrators_8leapfrog_c_leapfrog_stepP11_CPotentialmiddPdS1_S1_S1_",
}


def hx(raw):
    return f"0x{int.from_bytes(raw, 'little'):0{len(raw)*2}x}"


def unhex(text, width):
    return int(text, 16).to_bytes(width, "little")


def elf_segments(raw):
    if raw[:6] != b"\x7fELF\x02\x01": raise Refused("not ELF64 little endian")
    offset = struct.unpack_from("<Q", raw, 32)[0]
    size, count = struct.unpack_from("<HH", raw, 54)
    result = []
    for i in range(count):
        kind, flags, file_offset, vaddr, _, filesz, memsz, _ = struct.unpack_from("<IIQQQQQQ", raw, offset+i*size)
        if kind == 1:
            result.append({"file_offset": file_offset, "vaddr": vaddr, "filesz": filesz,
                           "memsz": memsz, "flags": flags})
    return result


class Capture:
    def __init__(self):
        raw = WHEEL.read_bytes()
        if hashlib.sha256(raw).hexdigest() != EXPECTED_WHEEL: raise Refused("wheel hash mismatch")
        with zipfile.ZipFile(WHEEL) as z:
            self.wheel_hashes = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.endswith(".so")}
        self.modules, self.maps, self.known, self.regions = {}, [], {}, []
        self.owner = None
        self.count = 0
        self.started = None
        self.last_event = None
        self.pending = None
        self.stream = (OUT / "trace.jsonl").open("x", encoding="utf-8")
        self.chain = "0"*64
        self.histogram = {}
        self.fp_count = 0
        self.stop_handler = lambda event: setattr(self, "last_event", event)
        gdb.events.stop.connect(self.stop_handler)

    def refresh_maps(self):
        self.maps = []
        for line in Path(f"/proc/{gdb.selected_inferior().pid}/maps").read_text().splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) < 6 or not parts[5].startswith("/"): continue
            start, end = [int(x, 16) for x in parts[0].split("-")]
            self.maps.append({"start": start, "end": end, "perms": parts[1],
                              "file_offset": int(parts[2], 16), "path": parts[5]})

    def module_at(self, address):
        mapping = next((m for m in self.maps if m["start"] <= address < m["end"]), None)
        if mapping is None: raise Refused(f"unmapped module address {address:#x}")
        path = mapping["path"]
        if path not in self.modules:
            raw = Path(path).read_bytes()
            segs = elf_segments(raw)
            seg = next((s for s in segs if s["file_offset"] & ~4095 == mapping["file_offset"]), None)
            if seg is None: raise Refused("ELF load segment correspondence")
            base = mapping["start"] - (seg["vaddr"] & ~4095)
            digest = hashlib.sha256(raw).hexdigest()
            marker = "/gala/"
            member = "gala/" + path.split(marker, 1)[1] if marker in path else None
            if member and self.wheel_hashes.get(member) != digest: raise Refused("loaded wheel member mismatch")
            self.modules[path] = {"path": path, "sha256": digest, "load_base": base,
                                  "segments": segs, "wheel_member": member, "_raw": raw}
        return self.modules[path], mapping

    def file_slice(self, module, address, size):
        relative = address-module["load_base"]
        seg = next((s for s in module["segments"] if s["vaddr"] <= relative and relative+size <= s["vaddr"]+s["filesz"]), None)
        if seg is None: raise Refused("address outside file-backed ELF segment")
        offset = seg["file_offset"]+relative-seg["vaddr"]
        return module["_raw"][offset:offset+size], offset

    def context(self, extras=()):
        frame = gdb.newest_frame()
        def raw_register(name):
            value = frame.read_register(name)
            raw = value.bytes
            if len(raw) != register_width(name): raise Refused("raw register width")
            return hx(raw)
        names = sorted(set(full for width, full in GPRS.values()))
        return {"gpr": {name: f"0x{int(frame.read_register(name)) & ((1<<64)-1):016x}" for name in names},
                "xmm": {f"xmm{i}": raw_register(f"xmm{i}") for i in range(16)},
                "extra_vectors": {name: raw_register(name) for name in extras if name not in {f"xmm{i}" for i in range(16)}},
                "mxcsr": int(frame.read_register("mxcsr")), "eflags": int(frame.read_register("eflags"))}

    def register_bytes(self, context, name, width):
        if name in GPRS:
            return unhex(context["gpr"][GPRS[name][1]], 8)[:width]
        text = context["xmm"].get(name, context["extra_vectors"].get(name))
        if text is None: raise Refused("register not captured")
        return unhex(text, register_width(name))[:width]

    def keys(self, operand):
        if operand["kind"] == "register":
            name = operand["register"]
            base = GPRS[name][1] if name in GPRS else "vector" + re.search(r"\d+", name)[0]
            return [("reg", base, i) for i in range(operand["width"])]
        if operand["kind"] == "memory":
            return [("mem", operand["address"]+i) for i in range(operand["width"])]
        return []

    def origins(self, operand, raw):
        keys = self.keys(operand)
        if operand["kind"] in {"immediate", "code_address"}:
            return ["instruction_literal"]*len(raw)
        known = [self.known.get(k) for k in keys]
        for byte, value in zip(raw, known):
            if value is not None and value[0] != byte: raise Refused("unrecorded alias/write changed tracked bits")
        if operand["kind"] == "memory" and not all(known):
            try:
                module, mapping = self.module_at(operand["address"])
            except Refused:
                module, mapping = None, None
            if mapping and "w" not in mapping["perms"]:
                expected, offset = self.file_slice(module, operand["address"], len(raw))
                if expected != raw: raise Refused("constant memory differs from ELF")
                operand["constant_origin"] = {"module_sha256": module["sha256"], "file_offset": offset}
                return [f"ELF_CONST:{module['sha256']}:{offset+i}" for i in range(len(raw))]
        return [value[1] if value else None for value in known]

    def operand(self, text, width, context, pc, length, access):
        if text.startswith("*"): text = text[1:]
        if text.startswith("%") and ":" not in text:
            name = text[1:]
            if width is None: width = register_width(name)
            result = {"kind": "register", "register": name, "width": width, "access": access}
            raw = self.register_bytes(context, name, width)
        elif text.startswith("$"):
            width = width or 8
            raw = (int(text[1:], 0) & ((1 << (8*width))-1)).to_bytes(width, "little")
            result = {"kind": "immediate", "width": width, "access": access}
        else:
            address = effective_address(text, {k: int(v, 16) for k,v in context["gpr"].items()}, pc, length)
            width = width or 8
            raw = bytes(gdb.selected_inferior().read_memory(address, width))
            result = {"kind": "memory", "address": address, "width": width, "access": access}
        result["raw_bits"] = hx(raw)
        result["origins"] = self.origins(result, raw)
        return result

    def put(self, destination, raw, origin, numeric=False):
        origins = origin if isinstance(origin, list) else [origin]*len(raw)
        for key, byte, item in zip(self.keys(destination), raw, origins): self.known[key] = (byte, item, numeric)

    def forget_changed_gprs(self, before, after, exempt=()):
        for name in before["gpr"]:
            if name == "rip" or name in exempt or before["gpr"][name] == after["gpr"][name]: continue
            keys = [("reg", name, i) for i in range(8)]
            if any(self.known.get(k, (0,None,False))[2] for k in keys):
                raise Refused("integer routing modifies numerical payload")
            for key in keys: self.known.pop(key, None)

    def result_bytes(self, destination, context):
        if destination["kind"] == "register":
            return self.register_bytes(context, destination["register"], destination["width"])
        return bytes(gdb.selected_inferior().read_memory(destination["address"], destination["width"]))

    def one(self, phase):
        if time.perf_counter()-self.started > 120 or self.count >= 5000: raise Refused("fixed one-step acquisition budget")
        if gdb.selected_thread().ptid != self.owner: raise Refused("another thread entered numerical trace")
        pc = int(gdb.newest_frame().read_register("rip"))
        ins = gdb.newest_frame().architecture().disassemble(pc, count=1)[0]
        length, assembly = ins["length"], ins["asm"]
        self.pending = {"runtime_pc":pc,"phase":phase,"instruction":assembly,"executed":False}
        opcode, kind, texts, width = decode(assembly)
        module, mapping = self.module_at(pc)
        symbol = gdb.newest_frame().name() or gdb.execute(f"info symbol {pc:#x}", to_string=True).strip()
        if not module["wheel_member"] and "memset" not in symbol:
            raise Refused(f"external code outside frozen wheel/memset: {module['path']} {symbol}")
        instruction_bytes = bytes(gdb.selected_inferior().read_memory(pc, length))
        disk, offset = self.file_slice(module, pc, length)
        if disk != instruction_bytes: raise Refused("executed bytes differ from ELF / debugger trap")
        extra = sorted(set(re.findall(r"%((?:xmm|ymm|zmm)\d+)", assembly)))
        before = self.context(extra)
        check_mxcsr(before["mxcsr"])
        operands, destination = [], None
        if kind in {"ADD", "SUB", "MUL", "MOVE"}:
            operands = [self.operand(t, width, before, pc, length, "read" if i == 0 else "read_write" if kind in ARITHMETIC.values() else "write") for i,t in enumerate(texts)]
            destination = operands[1]
        elif kind in {"ZERO", "ZERO_FILL"}:
            operands = [self.operand(t, 1 if kind=="ZERO_FILL" and i==0 else min(register_width(t[1:]), width), before, pc, length, "read" if i < len(texts)-1 else "write") for i,t in enumerate(texts)]
            destination = operands[-1]
        elif kind == "STACK":
            rsp = int(before["gpr"]["rsp"], 16)
            if opcode.startswith("push"):
                operands = [self.operand(texts[0], 8, before, pc, length, "read"), self.operand(f"{rsp-8:#x}", 8, before, pc, length, "write")]
            else:
                operands = [self.operand(f"{rsp:#x}", 8, before, pc, length, "read"), self.operand(texts[0], 8, before, pc, length, "write")]
            destination = operands[1]
        elif kind == "CONTROL":
            if opcode.startswith("ret"):
                operands = [self.operand("(%rsp)", 8, before, pc, length, "read")]
            elif texts:
                t = texts[0]
                if t.startswith("*"):
                    operands = [self.operand(t, 8, before, pc, length, "read")]
                else:
                    operands = [{"kind": "code_address", "width": 8, "raw_bits": f"0x{int(t,16):016x}", "access": "control", "origins": ["instruction_literal"]*8}]
        elif kind == "ROUTING" and not opcode.startswith("nop"):
            # Record actual integer input bits. LEA/NOP encodings do not read memory.
            if opcode != "lea":
                widths=routing_widths(opcode,texts)
                operands = [self.operand(t, w, before, pc, length, "write" if opcode in {"movslq","movzbl","movzwl"} and i==1 else "read" if opcode.startswith(("cmp","test")) or i==0 else "read_write") for i,(t,w) in enumerate(zip(texts,widths))]
        if kind in ARITHMETIC.values():
            for op in operands:
                if None in op["origins"]: raise Refused("unknown numerical memory/register source")
                check_finite(op["raw_bits"])
        if kind == "ZERO_FILL" and int(operands[0]["raw_bits"], 16) & 255:
            raise Refused("only actual zero-fill broadcast is supported")
        record = {"seq": self.count, "pid": gdb.selected_inferior().pid, "ptid": list(self.owner),
                  "phase": phase, "step": 0 if phase == "init" else 1, "symbol": symbol,
                  "module_path": module["path"], "module_sha256": module["sha256"],
                  "module_load_base": module["load_base"], "runtime_pc": pc,
                  "elf_address": pc-module["load_base"], "elf_file_offset": offset,
                  "mapping": mapping,
                  "bytes": instruction_bytes.hex(), "instruction": assembly, "opcode": opcode,
                  "kind": kind, "operands": operands, "pre": before}
        self.pending = record
        self.last_event = None
        gdb.execute("stepi", to_string=True)
        if isinstance(self.last_event, gdb.SignalEvent): raise Refused(f"signal during stepi: {self.last_event.stop_signal}")
        if gdb.selected_thread().ptid != self.owner: raise Refused("thread changed during stepi")
        after = self.context(extra)
        check_mxcsr(after["mxcsr"])
        record["post"] = after
        record["post_pc"] = int(after["gpr"]["rip"], 16)
        record["changed_gpr_results"]={name:value for name,value in after["gpr"].items() if name!="rip" and value!=before["gpr"][name]}
        exempt = {"rsp"} if kind in {"STACK", "CONTROL"} else set()
        if destination:
            result = self.result_bytes(destination, after)
            record["result_bits"] = hx(result)
            if kind in ARITHMETIC.values(): check_finite(record["result_bits"])
            source = operands[0]
            if kind in {"MOVE", "STACK"}:
                if source["raw_bits"] != hx(result): raise Refused("bit copy differs from observed result")
            if kind in {"ZERO", "ZERO_FILL"} and any(result): raise Refused("zero generation result")
            origins = [f"record:{self.count}" if item is not None else None for item in source["origins"]] if kind in {"MOVE","STACK"} else f"record:{self.count}"
            self.put(destination, result, origins, kind in ARITHMETIC.values() or any(self.known.get(k,(0,None,False))[2] for k in self.keys(source)))
            if destination["kind"] == "register":
                name = destination["register"]
                if name in GPRS:
                    exempt.add(GPRS[name][1])
                    if GPRS[name][0] == 4:
                        for i in range(4,8): self.known[("reg",GPRS[name][1],i)] = (0,f"record:{self.count}:zero_extend",False)
                elif (opcode in {"movq","vmovd"} or opcode == "movsd" and source["kind"] == "memory"):
                    for i in range(width,16): self.known[("reg","vector"+re.search(r"\d+",name)[0],i)] = (0,f"record:{self.count}:zero_upper",False)
        # Explicit integer XOR reg,reg is a bit-zero source, not FP arithmetic.
        if opcode == "xor" and len(texts) == 2 and texts[0] == texts[1] and operands:
            dest = operands[-1]
            self.put(dest, self.result_bytes(dest, after), f"record:{self.count}:integer_zero")
            exempt.add(GPRS[dest["register"]][1])
        self.forget_changed_gprs(before, after, exempt)
        encoded = json.dumps(record, sort_keys=True, separators=(",",":"))
        self.chain = hashlib.sha256(bytes.fromhex(self.chain)+encoded.encode()).hexdigest()
        record["chain"] = self.chain
        self.stream.write(json.dumps(record, separators=(",",":"))+"\n"); self.stream.flush()
        self.count += 1
        self.histogram[opcode] = self.histogram.get(opcode,0)+1
        self.fp_count += kind in ARITHMETIC.values()
        self.pending = None

    def memory_state(self, pointers):
        return {name: hx(bytes(gdb.selected_inferior().read_memory(address,16))) for name,address in pointers.items()}

    def region(self, phase):
        frame = gdb.newest_frame()
        if SYMBOLS[phase] not in gdb.execute(f"info symbol {int(frame.read_register('rip')):#x}", to_string=True):
            # GDB may demangle the name; function name still identifies the actual breakpoint.
            if f"c_{'init_velocity' if phase == 'init' else 'leapfrog_step'}" not in (frame.name() or ""):
                raise Refused("incorrect function entry")
        selected = gdb.selected_thread().ptid
        if self.owner is not None and selected != self.owner: raise Refused("different numerical thread")
        self.owner = selected
        gdb.execute("set scheduler-locking on")
        self.refresh_maps()
        before = self.context()
        if int(before["gpr"]["rsi"],16) != 1 or int(before["gpr"]["rdx"],16) != 2:
            raise Refused("only one orbit / two coordinates supported")
        rsp = int(before["gpr"]["rsp"],16)
        memory = lambda address: bytes(gdb.selected_inferior().read_memory(address,8))
        return_pc = int.from_bytes(memory(rsp),"little")
        pointers = {"q":int(before["gpr"]["rcx"],16), "full_v":int(before["gpr"]["r8"],16),
                    "latent":int(before["gpr"]["r9"],16), "gradient":int.from_bytes(memory(rsp+8),"little")}
        state = self.memory_state(pointers)
        if phase == "init":
            if state["q"] != "0x00000000000000000000000000000000" or state["full_v"] != "0x3fc00000000000003fd0000000000000":
                raise Refused("only frozen regular initial state supported")
        elif any(state[name] != self.regions[0]["end_state"][name] for name in ["q","full_v","latent"]):
            raise Refused("init endpoint to step input mismatch")
        # Caller setup between the two explicit regions is outside capture. Preserve
        # the checked numerical buffers, not retired stack frames/scratch storage.
        allowed_memory = {address+i for address in pointers.values() for i in range(16)}
        for key in list(self.known):
            if key[0] == "mem" and key[1] not in allowed_memory: self.known.pop(key)
        if self.register_bytes(before,"xmm1",8) != struct.pack("<d",1/64): raise Refused("dt changed")
        for name, address in pointers.items():
            raw = bytes(gdb.selected_inferior().read_memory(address,16))
            for i,byte in enumerate(raw): self.known[("mem",address+i)] = (byte,f"boundary:{phase}:{name}:{i}",True)
        for name in ["xmm0","xmm1"]:
            raw = self.register_bytes(before,name,8)
            for i,byte in enumerate(raw): self.known[("reg","vector"+name[3:],i)] = (byte,f"boundary:{phase}:{name}",True)
        # Only the numerical state crosses regions; incidental caller scratch registers are fresh boundary state.
        for key in list(self.known):
            if key[0] == "reg" and not (key[1] in {"vector0","vector1"} and key[2] < 8): self.known.pop(key)
        region = {"phase": phase, "entry_pc": int(before["gpr"]["rip"],16), "return_pc":return_pc,
                  "start_seq":self.count, "pointers":pointers, "start_state":state, "mxcsr":before["mxcsr"],
                  "threads": [{"ptid":list(t.ptid),"name":t.name,"owner":t.ptid==self.owner} for t in gdb.selected_inferior().threads()],
                  "scheduler_locking":gdb.execute("show scheduler-locking",to_string=True).strip()}
        check_mxcsr(before["mxcsr"])
        while int(gdb.newest_frame().read_register("rip")) != return_pc:
            self.one(phase)
        region.update({"end_seq":self.count,"end_state":self.memory_state(pointers)})
        self.regions.append(region)

    def run(self):
        self.started = time.perf_counter()
        breakpoints = {phase:gdb.Breakpoint(symbol,internal=True) for phase,symbol in SYMBOLS.items()}
        for phase in ["init","step"]:
            gdb.execute("run" if phase == "init" else "continue",to_string=True)
            breakpoints[phase].enabled = False
            self.region(phase)
        for b in breakpoints.values(): b.delete()
        # Both numerical regions are over. Import-created workers must be allowed
        # to finish normal Python shutdown; no further numerical steps are added.
        gdb.execute("set scheduler-locking off")
        gdb.execute("continue",to_string=True)
        if not (OUT / "harness_output.json").exists(): raise Refused("harness did not complete")
        if gdb.selected_inferior().pid != 0: raise Refused("inferior did not exit normally after capture")

    def finish(self, verdict, reason=None):
        self.stream.close()
        result = {"schema":"gala-regular-1step-runtime-trace-v1", "verdict":verdict,"reason":reason,
                  "record_count":self.count,"scalar_fp_count":self.fp_count,"opcode_histogram":self.histogram,
                  "regions":self.regions,"modules":{p:{k:v for k,v in m.items() if k!="_raw"} for p,m in self.modules.items()},
                  "trace_sha256":hashlib.sha256((OUT/"trace.jsonl").read_bytes()).hexdigest(),"final_chain":self.chain,
                  "capture_wall_seconds":time.perf_counter()-self.started if self.started else None,
                  "gdb_version":gdb.VERSION,"gdb_python":sys.version,"wheel_sha256":EXPECTED_WHEEL,
                  "pending_uncompleted_instruction":self.pending,"machine_mapping_read_by_tracer":False,
                  "scope":"regular init and one c_leapfrog_step including nested gradient and actual memset; caller outside these two regions excluded"}
        (OUT/"capture.json").write_text(json.dumps(result,indent=2)+"\n")


gdb.execute("set pagination off")
gdb.execute("set confirm off")
gdb.execute("set breakpoint pending on")
gdb.execute("set disassembly-flavor att")
gdb.execute("set print symbol-filename on")
gdb.execute("set debuginfod enabled off")
capture = None
try:
    capture = Capture()
    capture.run()
    capture.finish("CAPTURED")
except Exception as exc:
    if capture is not None: capture.finish("REFUSED", f"{type(exc).__name__}: {exc}")
    else: (OUT/"capture.json").write_text(json.dumps({"verdict":"REFUSED","reason":repr(exc)})+"\n")
    gdb.execute("kill",to_string=True)
