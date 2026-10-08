"""GDB acquisition for init plus two actual native leapfrog step bodies.

The original Capture definition is loaded from a hash-pinned source prefix via
AST.  Its top-level one-step execution block is never compiled or executed.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

import gdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.caller_transition.read_effects import ReadsRefused, required_reads
from runtime_trace.caller_transition.write_effects_reads import possible_writes
from runtime_trace.regular_2step.acquire import definition_only_nodes, supplemental_required_reads

OUT = Path(os.environ["RT_OUTPUT"])
CASE = os.environ["RT2_CASE"]
BASE_SOURCE = ROOT / "runtime_trace/gdb_capture.py"
CALLER_SOURCE = ROOT / "runtime_trace/caller_transition/gdb_acquire_reads.py"
STEP_SYMBOL = "_ZL66__pyx_f_4gala_9integrate_13cyintegrators_8leapfrog_c_leapfrog_stepP11_CPotentialmiddPdS1_S1_S1_"
INIT_SYMBOL = "_ZL66__pyx_f_4gala_9integrate_13cyintegrators_8leapfrog_c_init_velocityP11_CPotentialmiddPdS1_S1_S1_"


def load_definition(path, class_name, module_name):
    source = path.read_text(encoding="utf-8")
    selected = definition_only_nodes(source, class_name)
    namespace = {"__file__": str(path), "__name__": module_name}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


BASE = load_definition(BASE_SOURCE, "Capture", "runtime_trace._definition_only_gdb_capture")
CALLER = load_definition(CALLER_SOURCE, "Acquisition",
                         "runtime_trace.caller_transition._definition_only_gdb_acquire_reads")
BaseCapture = BASE["Capture"]
CallerAcquisition = CALLER["Acquisition"]
Refused = BASE["Refused"]
check_mxcsr = BASE["check_mxcsr"]
hx = BASE["hx"]


class EnrichingStream:
    def __init__(self, capture, raw):
        self.capture, self.raw = capture, raw

    @property
    def closed(self):
        return self.raw.closed

    def close(self):
        return self.raw.close()

    def flush(self):
        return self.raw.flush()

    def write(self, text):
        row = json.loads(text)
        row.pop("chain", None)
        extras = self.capture.row_extras
        writes = []
        for item in extras["possible_memory_writes"]:
            after = bytes(gdb.selected_inferior().read_memory(item["address"], item["size"]))
            writes.append({**item, "after_hex": after.hex()})
        row.update({"occurrence": extras["occurrence"],
                    "pre_memory_observations": extras["pre_memory_observations"],
                    "possible_memory_writes": writes})
        chain = hashlib.sha256(bytes.fromhex(self.capture.augmented_chain) +
                               json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        row["chain"] = chain
        self.capture.augmented_chain = chain
        self.capture.chain = chain
        return self.raw.write(json.dumps(row, separators=(",", ":")) + "\n")


class CorridorTraceBridge:
    def __init__(self, capture):
        self.capture = capture

    def flush(self):
        self.capture.stream.raw.flush()

    def write(self, text):
        row = json.loads(text)
        row.update({"seq": self.capture.count,
                    "pid": self.capture.process_identity["pid"],
                    "ptid": row["thread_ptid"], "occurrence": "caller12"})
        unsigned = {key: value for key, value in row.items() if key != "chain"}
        chain = hashlib.sha256(bytes.fromhex(self.capture.augmented_chain) +
                               json.dumps(unsigned, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
        row["chain"] = chain
        self.capture.augmented_chain = chain
        self.capture.chain = chain
        self.capture.stream.raw.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.capture.stream.raw.flush()
        self.capture.count += 1
        opcode = row["assembly"].split()[0]
        self.capture.histogram[opcode] = self.capture.histogram.get(opcode, 0) + 1
        return len(text)


class Regular2StepCapture(BaseCapture):
    def __init__(self):
        super().__init__()
        self.stream = EnrichingStream(self, self.stream)
        self.augmented_chain = "0" * 64
        self.row_extras = None
        self.process_identity = None
        self.harness_completed_normally = False
        self.gdb_exit_event = None
        self.pre_memory_observation_count = 0
        self.possible_memory_write_count = 0
        self.corridor = None

    def context(self, extras=()):
        result = super().context(extras)
        frame = gdb.newest_frame()
        result["segment_bases"] = {
            "fs_base": f"0x{int(frame.read_register('fs_base')) & ((1 << 64) - 1):016x}",
            "gs_base": f"0x{int(frame.read_register('gs_base')) & ((1 << 64) - 1):016x}",
        }
        return result

    @staticmethod
    def _numeric_registers(context):
        result = {name: int(value, 16) for name, value in context["gpr"].items()}
        result["eflags"] = context["eflags"]
        return result

    def one(self, phase):
        frame = gdb.newest_frame()
        pc = int(frame.read_register("rip"))
        instruction = frame.architecture().disassemble(pc, count=1)[0]
        if "length" not in instruction:
            raise Refused("GDB disassembly omitted instruction length")
        length, assembly = int(instruction["length"]), instruction["asm"]
        context = self.context()
        registers = self._numeric_registers(context)
        segments = {name: int(value, 16) for name, value in context["segment_bases"].items()}
        module, _ = self.module_at(pc)
        instruction_bytes = bytes(gdb.selected_inferior().read_memory(pc, length))
        site = {"module_sha256": module["sha256"], "elf_address": pc - module["load_base"],
                "bytes": instruction_bytes.hex()}
        observations = []
        try:
            descriptors = required_reads(assembly, registers, segments, pc, length)
        except ReadsRefused:
            descriptors = supplemental_required_reads(assembly, registers, pc, length, site)
        for descriptor in descriptors:
            raw = bytes(gdb.selected_inferior().read_memory(descriptor["address"], descriptor["size"]))
            observations.append({**descriptor, "timing": "PRE_INSTRUCTION",
                                 "bytes_hex": raw.hex(), "status": "OK"})
        writes = []
        for descriptor in possible_writes(assembly, registers, segments, pc, length):
            raw = bytes(gdb.selected_inferior().read_memory(descriptor["address"], descriptor["size"]))
            writes.append({**descriptor, "before_hex": raw.hex()})
        self.pre_memory_observation_count += len(observations)
        self.possible_memory_write_count += len(writes)
        self.row_extras = {"occurrence": phase, "pre_memory_observations": observations,
                           "possible_memory_writes": writes}
        try:
            return super().one(phase)
        finally:
            self.row_extras = None

    def component_state(self, pointers):
        return {name: [hx(bytes(gdb.selected_inferior().read_memory(address + offset, 8)))
                       for offset in (0, 8)] for name, address in pointers.items()}

    def region(self, occurrence, symbol):
        frame = gdb.newest_frame()
        pc = int(frame.read_register("rip"))
        if symbol not in gdb.execute(f"info symbol {pc:#x}", to_string=True):
            wanted = "c_init_velocity" if occurrence == "init" else "c_leapfrog_step"
            if wanted not in (frame.name() or ""):
                raise Refused("incorrect function entry")
        selected = gdb.selected_thread().ptid
        if self.owner is not None and selected != self.owner:
            raise Refused("different numerical thread")
        self.owner = selected
        gdb.execute("set scheduler-locking on")
        self.refresh_maps()
        before = self.context()
        if self.process_identity is None:
            pid = gdb.selected_inferior().pid
            stat_tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            self.process_identity = {"linux_boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                                     "pid": pid, "proc_stat_start_time_ticks": int(stat_tail[19])}
        if int(before["gpr"]["rsi"], 16) != 1 or int(before["gpr"]["rdx"], 16) != 2:
            raise Refused("only one orbit / two coordinates supported")
        rsp = int(before["gpr"]["rsp"], 16)
        memory = lambda address, size=8: bytes(gdb.selected_inferior().read_memory(address, size))
        return_pc = int.from_bytes(memory(rsp), "little")
        pointers = {"q": int(before["gpr"]["rcx"], 16),
                    "full_v": int(before["gpr"]["r8"], 16),
                    "latent": int(before["gpr"]["r9"], 16),
                    "gradient": int.from_bytes(memory(rsp + 8), "little")}
        state = self.component_state(pointers)
        if occurrence == "init":
            if state["q"] != ["0x0000000000000000"] * 2 or state["full_v"] != [
                    "0x3fd0000000000000", "0x3fc0000000000000"]:
                raise Refused("only frozen regular initial state supported")
        else:
            previous = self.regions[-1]
            for name in ("q", "full_v", "latent"):
                if state[name] != previous["end_state"][name]:
                    raise Refused(f"{previous['occurrence']} endpoint to {occurrence} input mismatch: {name}")
        allowed_memory = {address + index for address in pointers.values() for index in range(16)}
        for key in list(self.known):
            if key[0] == "mem" and key[1] not in allowed_memory:
                self.known.pop(key)
        if self.register_bytes(before, "xmm1", 8) != struct.pack("<d", 1 / 64):
            raise Refused("dt changed")
        for name, address in pointers.items():
            raw = memory(address, 16)
            for index, byte in enumerate(raw):
                self.known[("mem", address + index)] = (byte, f"boundary:{occurrence}:{name}:{index}", True)
        for name in ("xmm0", "xmm1"):
            raw = self.register_bytes(before, name, 8)
            for index, byte in enumerate(raw):
                self.known[("reg", "vector" + name[3:], index)] = (
                    byte, f"boundary:{occurrence}:{name}:{index}", True)
        for key in list(self.known):
            if key[0] == "reg" and not (key[1] in {"vector0", "vector1"} and key[2] < 8):
                self.known.pop(key)
        check_mxcsr(before["mxcsr"])
        region = {"occurrence": occurrence, "entry_pc": pc, "return_pc": return_pc,
                  "start_seq": self.count, "pointers": pointers, "start_state": state,
                  "t_bits": hx(self.register_bytes(before, "xmm0", 8)),
                  "dt_bits": hx(self.register_bytes(before, "xmm1", 8)),
                  "entry_stack_observations": {"return_pc": {"address": rsp, "size": 8,
                      "bytes_hex": memory(rsp).hex(), "status": "OK", "timing": "FUNCTION_ENTRY"},
                      "gradient_pointer": {"address": rsp + 8, "size": 8,
                      "bytes_hex": memory(rsp + 8).hex(), "status": "OK", "timing": "FUNCTION_ENTRY"}},
                  "mxcsr": before["mxcsr"], "ptid": list(self.owner),
                  "scheduler_locking": gdb.execute("show scheduler-locking", to_string=True).strip()}
        while int(gdb.newest_frame().read_register("rip")) != return_pc:
            self.one(occurrence)
        region.update({"end_seq": self.count, "end_state": self.component_state(pointers)})
        self.regions.append(region)

    def caller_corridor(self, step_pc):
        corridor = CallerAcquisition.__new__(CallerAcquisition)
        corridor.started = self.started
        corridor.inferior_pid = self.process_identity["pid"]
        corridor.owner = self.owner
        corridor.maps = []
        corridor.map_snapshots = []
        corridor.modules = {}
        corridor.records = 0
        corridor.chain = "0" * 64
        corridor.trace = CorridorTraceBridge(self)
        corridor.first_step_entry = None
        corridor.first_step_return = None
        corridor.second_step_entry = None
        corridor.opcodes = {}
        corridor.rows = []
        corridor.pre_memory_observation_count = 0
        corridor.pre_memory_observation_failures = []
        corridor.possible_write_count = 0
        corridor.same_value_write_count = 0
        corridor.indirect_control_count = 0
        corridor.return_count = 0
        corridor.pop_count = 0
        corridor.leave_count = 0
        corridor.process_identity = self.process_identity
        corridor.refresh_maps("step1-return-post")
        start_seq = self.count
        start_pc = int(gdb.newest_frame().read_register("rip"))
        start_context = corridor.context()
        protected_pointers = self.regions[-1]["pointers"]
        start_state = corridor.component_state(protected_pointers)
        while int(gdb.newest_frame().read_register("rip")) != step_pc:
            corridor.one("caller")
        corridor.refresh_maps("step2-entry")
        entry_abi = corridor.abi()
        argument_sources = {
            "t": corridor.argument_source("xmm0", entry_abi["t_bits"]),
            "dt": corridor.argument_source("xmm1", entry_abi["dt_bits"]),
        }
        end_state = corridor.component_state(protected_pointers)
        for path, module in corridor.modules.items():
            if path not in self.modules:
                self.modules[path] = {"path": path, "sha256": module["sha256"],
                    "load_base": module["load_base"], "segments": module["segments"],
                    "wheel_member": None, "_raw": module["_raw"]}
        self.pre_memory_observation_count += corridor.pre_memory_observation_count
        self.possible_memory_write_count += corridor.possible_write_count
        self.corridor = {
            "schema": "regular-2step-caller-corridor-v1",
            "occurrence": "caller12", "start_seq": start_seq, "end_seq": self.count,
            "start_pc": start_pc, "end_pc": int(gdb.newest_frame().read_register("rip")),
            "entry_abi": entry_abi, "argument_sources": argument_sources,
            "start_context": start_context, "start_component_bits": start_state,
            "end_component_bits": end_state, "owner_ptid": list(self.owner),
            "protected_role_pointers": {name: protected_pointers[name]
                for name in ("q", "full_v", "latent")},
            "local_record_count": corridor.records, "local_final_chain": corridor.chain,
            "opcode_histogram": corridor.opcodes,
            "counts": {"pre_memory_observations": corridor.pre_memory_observation_count,
                       "possible_memory_writes": corridor.possible_write_count,
                       "same_value_writes": corridor.same_value_write_count,
                       "indirect_memory_controls": corridor.indirect_control_count,
                       "returns": corridor.return_count, "pops": corridor.pop_count,
                       "leaves": corridor.leave_count},
            "map_snapshots": corridor.map_snapshots,
            "definition_only_reuse": {"source_path": str(CALLER_SOURCE),
                "source_sha256": hashlib.sha256(CALLER_SOURCE.read_bytes()).hexdigest(),
                "top_level_execution_loaded": False, "reused_class": "Acquisition"},
        }

    def run(self):
        self.started = time.perf_counter()
        init_breakpoint = gdb.Breakpoint(INIT_SYMBOL, internal=True)
        step_breakpoint = gdb.Breakpoint(STEP_SYMBOL, internal=True)
        gdb.execute("run", to_string=True)
        init_breakpoint.enabled = False
        self.region("init", INIT_SYMBOL)
        gdb.execute("continue", to_string=True)
        self.region("step1", STEP_SYMBOL)
        step_pc = self.regions[-1]["entry_pc"]
        actual_return_post_pc = int(gdb.newest_frame().read_register("rip"))
        if actual_return_post_pc != self.regions[-1]["return_pc"]:
            raise Refused("step1 RET did not reach recorded caller return PC")
        self.caller_corridor(step_pc)
        self.region("step2", STEP_SYMBOL)
        init_breakpoint.delete()
        step_breakpoint.delete()
        gdb.execute("set scheduler-locking off")
        inferior_pid = gdb.selected_inferior().pid
        event_record = {"observed": False, "inferior_pid": inferior_pid, "exit_code": None}
        def record_exit(event):
            event_record["observed"] = True
            event_record["exit_code"] = getattr(event, "exit_code", None)
        gdb.events.exited.connect(record_exit)
        try:
            gdb.execute("continue", to_string=True)
        finally:
            gdb.events.exited.disconnect(record_exit)
        if not (OUT / "harness_output.json").is_file():
            raise Refused("harness did not complete")
        event_record["selected_inferior_pid_after_exit"] = gdb.selected_inferior().pid
        if (event_record["observed"] is not True or event_record["exit_code"] != 0 or
                event_record["selected_inferior_pid_after_exit"] != 0):
            raise Refused("GDB did not observe normal zero-code inferior exit")
        self.gdb_exit_event = event_record
        self.harness_completed_normally = True

    def result(self, verdict, reason=None):
        if not self.stream.closed:
            self.stream.close()
        trace_path = OUT / "trace.jsonl"
        return {"schema": "gala-regular-2step-runtime-trace-v1", "verdict": verdict,
                "reason": reason, "case": CASE, "record_count": self.count,
                "scalar_fp_count": self.fp_count, "opcode_histogram": self.histogram,
                "regions": self.regions,
                "modules": {path: {key: value for key, value in item.items() if key != "_raw"}
                            for path, item in self.modules.items()},
                "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                "final_chain": self.augmented_chain,
                "capture_wall_seconds": time.perf_counter() - self.started if self.started else None,
                "gdb_version": gdb.VERSION, "gdb_python": sys.version,
                "wheel_sha256": BASE["EXPECTED_WHEEL"],
                "process_identity": self.process_identity,
                "caller_corridor": self.corridor,
                "harness_completed_normally": self.harness_completed_normally,
                "gdb_exit_event": self.gdb_exit_event,
                "pre_memory_observation_count": self.pre_memory_observation_count,
                "possible_memory_write_count": self.possible_memory_write_count,
                "definition_only_reuse": {"source_path": str(BASE_SOURCE),
                    "source_sha256": hashlib.sha256(BASE_SOURCE.read_bytes()).hexdigest(),
                    "top_level_execution_loaded": False, "reused_class": "Capture"},
                "machine_mapping_read_by_tracer": False,
                "scope": "regular init plus actual step1 and step2 bodies through normal harness completion"}


gdb.execute("set pagination off")
gdb.execute("set confirm off")
gdb.execute("set breakpoint pending on")
gdb.execute("set disassembly-flavor att")
gdb.execute("set print symbol-filename on")
gdb.execute("set debuginfod enabled off")
gdb.execute("set non-stop off")
capture = None
try:
    capture = Regular2StepCapture()
    capture.run()
    result = capture.result("CAPTURED")
except Exception as exc:
    if capture is not None:
        result = capture.result("REFUSED", f"{type(exc).__name__}: {exc}")
    else:
        result = {"schema": "gala-regular-2step-runtime-trace-v1", "verdict": "REFUSED",
                  "reason": f"{type(exc).__name__}: {exc}", "case": CASE}
    try:
        if gdb.selected_inferior().pid:
            gdb.execute("kill", to_string=True)
    except Exception:
        pass
(OUT / "capture.pending.json").write_text(
    json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
