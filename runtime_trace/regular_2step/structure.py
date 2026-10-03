"""Independent structural checks for regular two-step captures.

This module never imports the GDB acquisition module.  It consumes sealed bytes,
resolves modules only through the repository's frozen-binary manifest, and asks
the system objdump to decode the packaged ELF independently of GDB.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


REQUIRED_SOURCE_PATHS = {
    "runtime_trace/harness.py",
    "runtime_trace/harness_nsteps2.py",
    "runtime_trace/semantics.py",
    "runtime_trace/gdb_capture.py",
    "runtime_trace/caller_transition/read_effects.py",
    "runtime_trace/caller_transition/write_effects.py",
    "runtime_trace/caller_transition/write_effects_reads.py",
    "runtime_trace/caller_transition/gdb_acquire_reads.py",
    "runtime_trace/caller_transition/module_resolver.py",
    "runtime_trace/caller_transition/frozen_modules/manifest.json",
    "runtime_trace/regular_2step/__init__.py",
    "runtime_trace/regular_2step/acquire.py",
    "runtime_trace/regular_2step/gdb_acquire.py",
    "runtime_trace/regular_2step/structure.py",
    "runtime_trace/regular_2step/CONTRACT.md",
}
SEALED_FILES = {"trace.jsonl", "capture.json", "execution.json", "source_pinset.json",
                "harness_output.json", "gdb.log"}
FINAL_FILES = SEALED_FILES | {"acquisition_seal.json", "structure_report.json"}


class StructureRefused(ValueError):
    """The supplied evidence does not satisfy the sealed structure contract."""


def _require(condition, reason):
    if not condition:
        raise StructureRefused(reason)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def check_harness_output(harness, capture):
    binding = capture.get("harness_binding", {})
    _require(capture.get("verdict") == "CAPTURED", "capture verdict")
    _require(harness.get("orbit") == "regular", "regular harness orbit")
    _require(harness.get("dt_bits") == "0x3f90000000000000", "regular harness dt")
    output = harness.get("output_bits")
    _require(isinstance(output, list) and len(output) == 4 and
             all(isinstance(item, str) and re.fullmatch(r"0x[0-9a-f]{16}", item)
                 for item in output),
             "malformed harness output bits")
    step2 = next((region for region in capture.get("regions", [])
                  if region.get("occurrence") == "step2"), None)
    _require(step2 is not None and output == step2.get("end_state", {}).get("q", []) +
             step2.get("end_state", {}).get("full_v", []), "step2 final endpoint")
    _require(binding.get("exact_one_token_n_steps_change") is True,
             "exact n_steps source-token proof")
    _require(binding.get("executed_native_step_calls") == 2,
             "two observed native step calls")
    _require(binding.get("harness_completed_normally") is True,
             "normal harness completion")
    # The protected exact sibling changes only the call token.  Its emitted
    # n_steps=1 field is inherited stale metadata, so it is accepted only when
    # the source proof and two actual native calls above independently hold.
    _require(harness.get("n_steps") == 1 and
             binding.get("inherited_stale_n_steps_metadata") is True,
             "stale inherited metadata must be declared")
    return {"validated": True, "raw_n_steps_metadata": 1,
            "executed_native_step_calls": 2}


def check_process_local_handoff(capture):
    acquisition_id = capture.get("acquisition_id")
    handoff = capture.get("process_local_handoff", {})
    _require(isinstance(acquisition_id, str) and acquisition_id, "acquisition identity")
    _require(handoff.get("from_acquisition_id") == acquisition_id and
             handoff.get("to_acquisition_id") == acquisition_id,
             "cross-acquisition handoff is forbidden even for equal bits")
    _require(handoff.get("same_process") is True, "handoff must be process-local")
    _require(handoff.get("from_occurrence") == "step1-return" and
             handoff.get("to_occurrence") == "step2-entry", "handoff occurrence labels")
    roles = handoff.get("roles", {})
    _require(set(roles) == {"q", "full_v", "latent"}, "handoff role set")
    for name, item in roles.items():
        _require(item.get("equal") is True and item.get("from_bits") == item.get("to_bits"),
                 f"process-local {name} bits")
        _require(item.get("from_pointer") == item.get("to_pointer"),
                 f"process-local {name} pointer")
    gradient = handoff.get("gradient_boundary", {})
    pointer = gradient.get("pointer")
    observation = gradient.get("entry_stack_observation", {})
    _require(gradient.get("exact_zero") is True and
             gradient.get("to_bits") == ["0x0000000000000000"] * 2 and
             gradient.get("caller_reset_write_required") is True,
             "process-local gradient exact zero")
    _require(pointer == gradient.get("step1_pointer") and isinstance(pointer, int) and
             observation.get("status") == "OK" and
             observation.get("timing") == "FUNCTION_ENTRY" and
             observation.get("size") == 8 and
             observation.get("bytes_hex") == pointer.to_bytes(8, "little").hex(),
             "process-local gradient pointer provenance")
    return {"validated": True, "roles": sorted(roles)}


def _post_target(row):
    if "post_elf_address" in row:
        return row["post_elf_address"]
    if isinstance(row.get("post_pc"), int) and isinstance(row.get("module_load_base"), int):
        return row["post_pc"] - row["module_load_base"]
    return None


def _memory_role(address, width, row, region):
    for name, base in region.get("pointers", {}).items():
        if base <= address and address + width <= base + 16:
            return ["component", name, address - base, width]
    pre = row.get("pre", {}).get("gpr", {})
    if "rsp" in pre:
        rsp = int(pre["rsp"], 16)
        if abs(address - rsp) <= 4096:
            return ["stack", address - rsp, width]
    for module in (row.get("mapping"),):
        if module and module.get("start", 1) <= address < module.get("end", 0):
            return ["mapped", module.get("perms"), address - module["start"], width]
    return ["other", address, width]


def _operand_topology(row, region):
    result = []
    for operand in row.get("operands", []):
        kind = operand.get("kind")
        if kind == "memory":
            role = _memory_role(operand["address"], operand["width"], row, region)
        elif kind == "register":
            role = ["register", operand.get("register"), operand.get("width")]
        elif kind == "code_address":
            role = ["code", operand.get("width")]
        else:
            role = [kind, operand.get("width")]
        result.append([operand.get("access"), role])
    return result


def compare_step_structures(first_rows, second_rows, first_region, second_region):
    instruction_first = [(row.get("module_sha256"), row.get("elf_address"), row.get("bytes"),
                          row.get("opcode"), row.get("kind")) for row in first_rows]
    instruction_second = [(row.get("module_sha256"), row.get("elf_address"), row.get("bytes"),
                           row.get("opcode"), row.get("kind")) for row in second_rows]
    _require(instruction_first == instruction_second, "instruction/byte sequence differs")

    control_first = [(index, row.get("elf_address"), row.get("opcode"), _post_target(row))
                     for index, row in enumerate(first_rows) if row.get("kind") == "CONTROL"]
    control_second = [(index, row.get("elf_address"), row.get("opcode"), _post_target(row))
                      for index, row in enumerate(second_rows) if row.get("kind") == "CONTROL"]
    _require(control_first == control_second, "control-flow sequence differs")

    topology_first = [_operand_topology(row, first_region) for row in first_rows]
    topology_second = [_operand_topology(row, second_region) for row in second_rows]
    _require(topology_first == topology_second, "memory-role topology differs")

    arithmetic = {"ADD", "SUB", "MUL"}
    arithmetic_indices = [index for index, row in enumerate(first_rows)
                          if row.get("kind") in arithmetic]
    helper_sequence = [(row.get("module_sha256"), row.get("symbol")) for row in first_rows
                       if row.get("kind") == "CONTROL" or
                       (row.get("symbol") and "leapfrog_step" not in row.get("symbol", ""))]
    return {
        "reusable": True,
        "instruction_count": len(first_rows),
        "instruction_sequence_sha256": hashlib.sha256(_canonical(instruction_first)).hexdigest(),
        "control_sequence_sha256": hashlib.sha256(_canonical(control_first)).hexdigest(),
        "memory_role_topology_sha256": hashlib.sha256(_canonical(topology_first)).hexdigest(),
        "arithmetic_indices": arithmetic_indices,
        "helper_sequence_sha256": hashlib.sha256(_canonical(helper_sequence)).hexdigest(),
    }


def compare_caller_corridor(new_rows, old_rows, protected_ranges):
    overlaps = []
    for row_index, row in enumerate(new_rows):
        for write_index, write in enumerate(row.get("possible_memory_writes", [])):
            write_start = write["address"]
            write_end = write_start + write["size"]
            for role, (start, end) in protected_ranges.items():
                if write_start < end and start < write_end:
                    overlaps.append({"row": row_index, "write": write_index, "role": role,
                                     "address": write_start, "size": write["size"],
                                     "value_changed": write.get("value_changed")})
    _require(not overlaps, "caller corridor protected component overlap")

    def signature(row):
        instruction = (row.get("module_sha256"), row.get("elf_address"),
                       row.get("instruction_bytes"),
                       normalize_decoded_instruction(row.get("assembly", ""),
                                                     row.get("load_base", 0)))
        reads = [(item.get("kind"), item.get("size"), item.get("operand"))
                 for item in row.get("pre_memory_observations", [])]
        writes = [(item.get("kind"), item.get("size"), item.get("value_changed"))
                  for item in row.get("possible_memory_writes", [])]
        return instruction, reads, writes

    new_signature = [signature(row) for row in new_rows]
    old_signature = [signature(row) for row in old_rows]
    _require(new_signature == old_signature, "caller corridor effect sequence differs")
    same_value = sum(not write.get("value_changed") for row in new_rows
                     for write in row.get("possible_memory_writes", []))
    return {"equivalent": True, "row_count": len(new_rows),
            "effect_sequence_sha256": hashlib.sha256(_canonical(new_signature)).hexdigest(),
            "possible_memory_writes": sum(len(row.get("possible_memory_writes", []))
                                           for row in new_rows),
            "same_value_writes": same_value, "protected_write_overlaps": overlaps}


def validate_receipt_files(capture_dir):
    capture_dir = Path(capture_dir)
    seal_path = capture_dir / "acquisition_seal.json"
    _require(seal_path.is_file(), "acquisition seal missing")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    _require(seal.get("schema") == "regular-2step-acquisition-seal-v1",
             "acquisition seal schema")
    sealed = seal.get("sealed_files")
    _require(isinstance(sealed, dict) and set(sealed) == SEALED_FILES,
             "exact six sealed files")
    _require(seal.get("sealed_file_name_set") == sorted(SEALED_FILES),
             "sealed file exact name set")
    _require(seal.get("final_required_file_name_set") == sorted(FINAL_FILES),
             "final exact eight file names")
    actual = {item.name for item in capture_dir.iterdir() if item.is_file()}
    _require(actual in (FINAL_FILES, FINAL_FILES - {"structure_report.json"}),
             "capture directory exact final file set")
    for name, digest in sealed.items():
        _require(Path(name).name == name, "sealed file name")
        path = capture_dir / name
        _require(path.is_file(), f"sealed file missing: {name}")
        _require(_sha(path) == digest, f"sealed file hash mismatch: {name}")
    return {"validated": True, "sealed_file_count": len(sealed)}


def _elf_file_offset(raw, address, length):
    _require(raw[:6] == b"\x7fELF\x02\x01", "frozen module is not ELF64 little endian")
    phoff = struct.unpack_from("<Q", raw, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", raw, 54)
    for index in range(phcount):
        kind, _, offset, vaddr, _, filesz, _, _ = struct.unpack_from(
            "<IIQQQQQQ", raw, phoff + index * phsize)
        if kind == 1 and vaddr <= address and address + length <= vaddr + filesz:
            return offset + address - vaddr
    raise StructureRefused("instruction outside frozen ELF file segment")


def _frozen_modules(root):
    manifest_path = root / "runtime_trace/frozen_binaries/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("schema") == "runtime-trace-frozen-binaries-v1",
             "frozen binary manifest schema")
    result = {}
    for digest, relative in manifest.get("modules", {}).items():
        path = (root / relative).resolve()
        _require(path.is_file() and root in path.parents, "frozen module path")
        raw = path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == digest, "frozen module hash")
        result[digest] = (path, raw)
    caller_manifest_path = root / "runtime_trace/caller_transition/frozen_modules/manifest.json"
    caller_manifest = json.loads(caller_manifest_path.read_text(encoding="utf-8"))
    _require(caller_manifest.get("schema") == "caller-transition-module-resolver-v1",
             "caller frozen module manifest schema")
    for digest, relative in caller_manifest.get("modules", {}).items():
        path = (caller_manifest_path.parent / relative).resolve()
        _require(path.is_file() and root in path.parents, "caller frozen module path")
        raw = path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == digest, "caller frozen module hash")
        result[digest] = (path, raw)
    return result


def _normalize_assembly(text):
    return re.sub(r"\s+", " ", re.sub(r"\s+<[^>]*>", "", text.split("#", 1)[0])).strip()


def normalize_decoded_instruction(text, module_load_base):
    normalized = _normalize_assembly(text)
    opcode, separator, operands = normalized.partition(" ")
    if separator and (opcode in {"call", "callq"} or opcode.startswith("j")):
        target = operands.split(",", 1)[0].strip()
        if re.fullmatch(r"(?:0x)?[0-9a-fA-F]+", target):
            value = int(target, 16)
            if module_load_base and value >= module_load_base:
                value -= module_load_base
            suffix = operands[len(target):]
            return f"{opcode} {value:x}{suffix}"
    return normalized


def _verify_elf_and_objdump(rows, root):
    frozen = _frozen_modules(root)
    grouped = {}
    for row in rows:
        digest = row.get("module_sha256")
        _require(digest in frozen, f"unregistered frozen module: {digest}")
        grouped.setdefault(digest, []).append(row)
    decoded_count = 0
    for digest, occurrences in grouped.items():
        path, raw = frozen[digest]
        wanted = {row["elf_address"] for row in occurrences}
        start = min(wanted)
        end = max(row["elf_address"] + len(bytes.fromhex(
            row.get("bytes", row.get("instruction_bytes", "")))) for row in occurrences)
        process = subprocess.run(
            ["objdump", "-d", "--no-show-raw-insn", f"--start-address={start}",
             f"--stop-address={end}", str(path)], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False)
        _require(process.returncode == 0, f"objdump failed for {digest}: {process.stderr.strip()}")
        decoded = {}
        for line in process.stdout.splitlines():
            match = re.match(r"\s*([0-9a-f]+):\s+(.+)", line)
            if match and int(match.group(1), 16) in wanted:
                decoded[int(match.group(1), 16)] = _normalize_assembly(match.group(2))
        for row in occurrences:
            encoded = bytes.fromhex(row.get("bytes", row.get("instruction_bytes", "")))
            _require(1 <= len(encoded) <= 15, "instruction byte length")
            offset = _elf_file_offset(raw, row["elf_address"], len(encoded))
            _require(offset == row.get("elf_file_offset", row.get("file_offset")) and
                     raw[offset:offset + len(encoded)] == encoded,
                     "frozen ELF instruction bytes")
            _require(row["elf_address"] in decoded, "objdump missing instruction")
            instruction = row.get("instruction", row.get("assembly", ""))
            load_base = row.get("module_load_base", row.get("load_base"))
            _require(normalize_decoded_instruction(instruction, load_base) ==
                     normalize_decoded_instruction(decoded[row["elf_address"]], 0),
                     "independent objdump decode")
            decoded_count += 1
    return decoded_count


def _load_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    _require(rows, "empty trace")
    _require([row.get("seq") for row in rows] == list(range(len(rows))),
             "trace sequence missing, duplicated, or reordered")
    chain = "0" * 64
    for row in rows:
        unsigned = {key: value for key, value in row.items() if key != "chain"}
        chain = hashlib.sha256(bytes.fromhex(chain) + _canonical(unsigned)).hexdigest()
        _require(row.get("chain") == chain, "trace hash chain")
    return rows, chain


def _check_observations(rows):
    reads = writes = implicit = 0
    for row in rows:
        observations = row.get("pre_memory_observations")
        possible_writes = row.get("possible_memory_writes")
        _require(isinstance(observations, list) and isinstance(possible_writes, list),
                 "actual PRE observations and writes are required")
        for item in observations:
            _require(item.get("status") == "OK" and item.get("timing") == "PRE_INSTRUCTION",
                     "PRE memory observation")
            _require(len(item.get("bytes_hex", "")) == 2 * item.get("size", -1),
                     "PRE memory observation width")
            implicit += item.get("kind") in {"IMPLICIT_RET", "IMPLICIT_POP", "IMPLICIT_LEAVE",
                                                     "INDIRECT_CONTROL"}
        for item in possible_writes:
            before = item.get("before_hex")
            after = item.get("after_hex")
            if before is None and isinstance(item.get("before_bits"), str):
                before = int(item["before_bits"], 16).to_bytes(item["size"], "little").hex()
            if after is None and isinstance(item.get("after_bits"), str):
                after = int(item["after_bits"], 16).to_bytes(item["size"], "little").hex()
            _require(len(before or "") == 2 * item.get("size", -1) and
                     len(after or "") == 2 * item.get("size", -1),
                     "memory write observation width")
            implicit += item.get("kind") in {"CALL_STACK", "PUSH_STACK"}
        reads += len(observations)
        writes += len(possible_writes)
    _require(implicit > 0, "implicit control observations missing")
    return {"pre_memory_observations": reads, "possible_memory_writes": writes,
            "implicit_control_observations": implicit}


def _pc_fields(row):
    if row.get("schema") == "gala-caller-transition-instruction-v2":
        return row.get("pc"), row.get("next_pc"), row.get("load_base"), "caller"
    return row.get("runtime_pc"), row.get("post_pc"), row.get("module_load_base"), "body"


def _validate_row_addresses(rows, corridor, regions):
    """Bind every row's claimed ELF site to its actual PRE/POST PCs and mappings."""
    snapshots = corridor.get("map_snapshots", [])
    caller_maps = [mapping for snapshot in snapshots for mapping in snapshot.get("maps", [])]
    for row in rows:
        pc, next_pc, load_base, kind = _pc_fields(row)
        _require(isinstance(pc, int) and isinstance(next_pc, int) and
                 isinstance(load_base, int) and isinstance(row.get("elf_address"), int),
                 "row PC fields")
        _require(pc == load_base + row["elf_address"],
                 "runtime PC/load base/ELF address")
        _require(int(row.get("pre", {}).get("gpr", {}).get("rip", "-1"), 16) == pc,
                 f"{kind} PRE rip/runtime PC")
        _require(int(row.get("post", {}).get("gpr", {}).get("rip", "-1"), 16) == next_pc,
                 f"{kind} POST rip/next PC")
        if kind == "body":
            mapping = row.get("mapping", {})
            _require(mapping.get("start", 1) <= pc < mapping.get("end", 0) and
                     "x" in mapping.get("perms", "") and
                     mapping.get("path") == row.get("module_path"),
                     "body executable mapping membership")
        else:
            matches = [mapping for mapping in caller_maps
                       if mapping.get("start", 1) <= pc < mapping.get("end", 0) and
                       "x" in mapping.get("perms", "") and
                       mapping.get("path") == row.get("captured_module_path")]
            _require(bool(matches), "caller executable mapping membership")

    continuous_ranges = [(region["start_seq"], region["end_seq"]) for region in regions]
    continuous_ranges.append((corridor["start_seq"], corridor["end_seq"]))
    for start, end in continuous_ranges:
        for index in range(start, end - 1):
            _require(_pc_fields(rows[index])[1] == _pc_fields(rows[index + 1])[0],
                     "row-to-row execution continuity")
    _require(_pc_fields(rows[regions[1]["end_seq"] - 1])[1] ==
             _pc_fields(rows[corridor["start_seq"]])[0] and
             _pc_fields(rows[corridor["end_seq"] - 1])[1] ==
             _pc_fields(rows[regions[2]["start_seq"]])[0],
             "cross-module step1/caller/step2 continuity")
    return len(rows)


def _validate_argument_source(name, source, corridor_rows, corridor_start, expected_bits):
    local_sequence = source.get("instruction_sequence")
    _require(isinstance(local_sequence, int) and 0 <= local_sequence < len(corridor_rows),
             f"{name} source instruction sequence")
    row = corridor_rows[local_sequence]
    _require(row.get("seq") == corridor_start + local_sequence and
             row.get("assembly") == source.get("assembly"), f"{name} source instruction")
    observations = row.get("pre_memory_observations", [])
    matching = [item for item in observations
                if item.get("address") == source.get("source_memory_address") and
                item.get("operand") == source.get("source_operand") and
                item.get("size") == 8 and item.get("status") == "OK" and
                item.get("timing") == "PRE_INSTRUCTION"]
    _require(len(matching) == 1 and matching[0].get("bytes_hex") ==
             int(expected_bits, 16).to_bytes(8, "little").hex() and
             source.get("source_bits") == expected_bits and
             source.get("destination_register") == ("xmm0" if name == "t" else "xmm1"),
             f"{name} actual source/provenance")


def _validate_gradient_reset(corridor_rows, pointer, from_bits):
    writes = []
    for row in corridor_rows:
        for item in row.get("possible_memory_writes", []):
            start, size = item.get("address"), item.get("size")
            if isinstance(start, int) and isinstance(size, int) and start < pointer + 16 and pointer < start + size:
                writes.append((row, item))
    _require(writes, "gradient reset write provenance")
    changed = [(row, item) for row, item in writes if item.get("value_changed")]
    _require(changed and any(item.get("address") == pointer and item.get("size") == 16 and
             item.get("before_bits") == "0x" + "".join(value[2:] for value in reversed(from_bits)) and
             item.get("after_bits") == "0x" + "0" * 32 for _, item in changed),
             "gradient reset changed-write bits")
    _require(writes[-1][1].get("address") == pointer and writes[-1][1].get("size") == 16 and
             writes[-1][1].get("after_bits") == "0x" + "0" * 32,
             "gradient reset final write exact zero")
    return {"write_count": len(writes), "changed_write_count": len(changed),
            "sequences": [row["seq"] for row, _ in writes]}


def _validate_antecedent_boundary(capture, antecedent_capture, antecedent_path,
                                  corridor_rows, regions):
    binding = capture.get("antecedent_binding", {})
    _require(binding.get("schema") == "regular-2step-antecedent-binding-v1",
             "antecedent binding schema")
    _require(_sha(antecedent_path) == binding.get("antecedent_capture_sha256"),
             "antecedent capture hash")
    _require(antecedent_capture.get("schema") == "gala-caller-transition-capture-v2" and
             antecedent_capture.get("verdict") == "CONTROLLED_STOP",
             "antecedent caller capture schema/verdict")
    _require(binding.get("antecedent_process_identity") ==
             antecedent_capture.get("process_identity") and
             binding.get("new_process_identity") == capture.get("process_identity") and
             binding.get("processes_distinct") is True and
             binding.get("antecedent_process_identity") != binding.get("new_process_identity") and
             binding.get("old_capture_continuation_claimed") is False,
             "antecedent/new process identity boundary")
    old_entry = antecedent_capture.get("second_step_entry", {})
    old_abi = old_entry.get("abi", {})
    corridor = capture["caller_corridor"]
    new_abi = corridor.get("entry_abi", {})
    step2 = regions[2]
    roles = binding.get("roles", {})
    _require(set(roles) == {"q", "full_v", "latent", "gradient"},
             "antecedent boundary role set")
    for name in roles:
        old_bits = old_abi.get("component_bits", {}).get(name)
        new_bits = new_abi.get("component_bits", {}).get(name)
        item = roles[name]
        _require(old_bits == new_bits == step2.get("start_state", {}).get(name) and
                 item.get("antecedent_bits") == old_bits and
                 item.get("new_process_bits") == new_bits and item.get("equal") is True and
                 item.get("address_equality_claimed") is False,
                 f"antecedent/corridor/step2 role bits: {name}")
    _require(step2.get("start_state", {}).get("gradient") ==
             ["0x0000000000000000"] * 2, "step2 gradient exact zero")
    _require(new_abi.get("pointers") == step2.get("pointers"),
             "corridor/step2 process-local pointers")
    gradient_observation = step2.get("entry_stack_observations", {}).get("gradient_pointer", {})
    gradient_pointer = step2.get("pointers", {}).get("gradient")
    _require(isinstance(gradient_pointer, int) and
             gradient_observation == new_abi.get("stack_argument_observations", {}).get("gradient") and
             gradient_observation.get("bytes_hex") == gradient_pointer.to_bytes(8, "little").hex(),
             "gradient actual pointer provenance")
    provenance_binding = binding.get("gradient_pointer_provenance", {})
    _require(provenance_binding.get("antecedent") ==
             old_abi.get("stack_argument_observations", {}).get("gradient") and
             provenance_binding.get("new_process") == gradient_observation and
             provenance_binding.get("new_process_pointer") == gradient_pointer and
             provenance_binding.get("address_equality_claimed") is False,
             "antecedent gradient pointer provenance")
    _require(corridor.get("start_component_bits", {}).get("gradient") ==
             regions[1].get("end_state", {}).get("gradient") and
             corridor.get("end_component_bits", {}).get("gradient") ==
             step2.get("start_state", {}).get("gradient"),
             "step1/corridor/step2 gradient states")
    _validate_gradient_reset(corridor_rows, gradient_pointer,
                             regions[1].get("end_state", {}).get("gradient"))
    for name in ("t", "dt"):
        bits = step2.get(f"{name}_bits")
        source = corridor.get("argument_sources", {}).get(name, {})
        old_source = old_entry.get("argument_sources", {}).get(name, {})
        item = binding.get("arguments", {}).get(name, {})
        _require(bits == new_abi.get(f"{name}_bits") == old_abi.get(f"{name}_bits") and
                 old_source.get("source_bits") == bits and item.get("antecedent") == old_source and
                 item.get("new_entry_bits") == bits and item.get("equal") is True,
                 f"antecedent/corridor/step2 {name} bits/provenance")
        _validate_argument_source(name, source, corridor_rows, corridor["start_seq"], bits)


def _validate_fresh_binding(capture, capture_dir, root):
    case = capture.get("case")
    _require(case in {"known", "fresh"}, "explicit acquisition role")
    if case == "known":
        _require("distinct_from" not in capture, "known distinct-from binding forbidden")
        return None
    binding = capture.get("distinct_from")
    _require(isinstance(binding, dict), "fresh distinct-from binding")
    other_path = Path(binding.get("capture_path", ""))
    if not other_path.is_absolute():
        other_path = (root / other_path).resolve()
    other_capture_path = other_path / "capture.json"
    _require(other_capture_path.is_file() and _sha(other_capture_path) ==
             binding.get("capture_sha256"), "fresh referenced known capture hash")
    other = json.loads(other_capture_path.read_text(encoding="utf-8"))
    _require(other.get("case") == "known" and binding.get("distinct") is True and
             binding.get("acquisition_id") == other.get("acquisition_id") and
             binding.get("process_identity") == other.get("process_identity") and
             binding.get("trace_sha256") == other.get("trace_sha256") and
             other.get("acquisition_id") != capture.get("acquisition_id") and
             other.get("process_identity") != capture.get("process_identity") and
             other.get("trace_sha256") != capture.get("trace_sha256"),
             "fresh/known distinct acquisition identity/process/trace")
    return other_path


def compare(capture_dir: Path, root: Path) -> dict:
    """Validate one sealed capture and prove or refuse step-template reuse."""
    capture_dir, root = Path(capture_dir).resolve(), Path(root).resolve()
    validate_receipt_files(capture_dir)
    seal = json.loads((capture_dir / "acquisition_seal.json").read_text(encoding="utf-8"))
    capture = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    execution = json.loads((capture_dir / "execution.json").read_text(encoding="utf-8"))
    harness = json.loads((capture_dir / "harness_output.json").read_text(encoding="utf-8"))
    source_pinset = json.loads((capture_dir / "source_pinset.json").read_text(encoding="utf-8"))
    _require(capture.get("schema") == "gala-regular-2step-runtime-trace-v1", "capture schema")
    _require(execution.get("schema") == "regular-2step-execution-v1", "execution schema")
    _require(execution.get("return_code") == 0 and
             execution.get("harness_completed_normally") is True, "execution receipt")
    _require(seal.get("acquisition_id") == capture.get("acquisition_id"),
             "seal/capture acquisition identity")
    _require(capture.get("execution_path") == "execution.json" and
             capture.get("execution_sha256") == _sha(capture_dir / "execution.json"),
             "capture execution receipt hash")
    _require(capture.get("source_pinset_path") == "source_pinset.json" and
             capture.get("source_pinset_sha256") == _sha(capture_dir / "source_pinset.json") and
             execution.get("source_pinset_path") == "source_pinset.json" and
             execution.get("source_pinset_sha256") == _sha(capture_dir / "source_pinset.json"),
             "capture/execution source pinset hash")
    _require(source_pinset.get("schema") == "regular-2step-source-pinset-v1", "source pinset schema")
    _require(set(source_pinset.get("files", {})) == REQUIRED_SOURCE_PATHS and
             source_pinset.get("exact_key_set") == sorted(REQUIRED_SOURCE_PATHS),
             "source pin exact key set")
    _require(execution.get("source_sha256_before_execution") == source_pinset["files"],
             "execution source pin redundant receipt")
    for relative, digest in source_pinset["files"].items():
        path = (root / relative).resolve()
        _require(path.is_file() and root in path.parents and _sha(path) == digest,
                 f"source pin mismatch: {relative}")
    rows, final_chain = _load_rows(capture_dir / "trace.jsonl")
    trace_sha = _sha(capture_dir / "trace.jsonl")
    _require(len(rows) == capture.get("record_count") and final_chain == capture.get("final_chain") and
             capture.get("trace_sha256") == trace_sha,
             "trace count or chain endpoint")
    expected_id = hashlib.sha256((_canonical({"case": capture.get("case"),
        "process_identity": capture.get("process_identity"), "trace_sha256": trace_sha}) +
        b"\n")).hexdigest()
    _require(capture.get("acquisition_id") == expected_id, "derived acquisition identity")
    identity = capture.get("process_identity", {})
    _require(identity == execution.get("process_identity") and
             all(row.get("pid") == identity.get("pid") for row in rows), "process identity receipt")
    regions = capture.get("regions", [])
    _require([region.get("occurrence") for region in regions] == ["init", "step1", "step2"],
             "init/step1/step2 region sequence")
    corridor = capture.get("caller_corridor", {})
    _require(regions[0].get("start_seq") == 0 and regions[-1].get("end_seq") == len(rows) and
             regions[0].get("end_seq") == regions[1].get("start_seq") and
             regions[1].get("end_seq") == corridor.get("start_seq") and
             corridor.get("end_seq") == regions[2].get("start_seq"), "region/corridor coverage")
    for region in regions:
        subset = rows[region["start_seq"]:region["end_seq"]]
        _require(subset and all(row.get("phase") == region["occurrence"] for row in subset),
                 "region occurrence assignment")
        _require(subset[0].get("runtime_pc") == region.get("entry_pc") and
                 subset[-1].get("post_pc") == region.get("return_pc"), "region entry/return")
    check_harness_output(harness, capture)
    check_process_local_handoff(capture)
    exit_event = capture.get("gdb_exit_event")
    _require(exit_event == execution.get("gdb_exit_event") and
             exit_event.get("observed") is True and exit_event.get("exit_code") == 0 and
             exit_event.get("inferior_pid") == identity.get("pid") and
             exit_event.get("selected_inferior_pid_after_exit") == 0 and
             re.search(r"\[Inferior \d+ \(process %d\) exited normally\]" % identity["pid"],
                       (capture_dir / "gdb.log").read_text(encoding="utf-8")) is not None,
             "sealed GDB normal exit event/transcript")
    observation_counts = _check_observations(rows)
    decoded = _verify_elf_and_objdump(rows, root)
    corridor_rows = rows[corridor["start_seq"]:corridor["end_seq"]]
    _require(corridor_rows and all(row.get("occurrence") == "caller12" and
                                   row.get("schema") == "gala-caller-transition-instruction-v2"
                                   for row in corridor_rows), "caller corridor row assignment")
    _require(rows[regions[1]["end_seq"] - 1].get("post_pc") == corridor.get("start_pc") and
             corridor_rows[0].get("pc") == corridor.get("start_pc") and
             corridor_rows[-1].get("next_pc") == regions[2].get("entry_pc"),
             "step1 RET / caller corridor / step2 entry seam")
    address_rows = _validate_row_addresses(rows, corridor, regions)
    antecedent_capture_path = Path(capture.get("antecedent_binding", {}).get(
        "antecedent_capture_path", ""))
    if not antecedent_capture_path.is_absolute():
        antecedent_capture_path = (root / antecedent_capture_path).resolve()
    _require(antecedent_capture_path.is_file(), "antecedent capture unavailable")
    antecedent_capture = json.loads(antecedent_capture_path.read_text(encoding="utf-8"))
    antecedent_trace_path = antecedent_capture_path.parent / "caller_trace.jsonl"
    _require(antecedent_trace_path.is_file() and _sha(antecedent_trace_path) ==
             antecedent_capture.get("trace_sha256"), "antecedent caller trace receipt")
    antecedent_rows = [json.loads(line) for line in
                       antecedent_trace_path.read_text(encoding="utf-8").splitlines()]
    antecedent_caller_rows = [row for row in antecedent_rows if row.get("phase") == "caller"]
    _validate_antecedent_boundary(capture, antecedent_capture, antecedent_capture_path,
                                  corridor_rows, regions)
    protected = {name: (regions[1]["pointers"][name], regions[1]["pointers"][name] + 16)
                 for name in ("q", "full_v", "latent")}
    corridor_proof = compare_caller_corridor(corridor_rows, antecedent_caller_rows, protected)
    for name in protected:
        _require(corridor.get("start_component_bits", {}).get(name) ==
                 corridor.get("end_component_bits", {}).get(name),
                 f"caller corridor component changed: {name}")
    step1 = rows[regions[1]["start_seq"]:regions[1]["end_seq"]]
    step2 = rows[regions[2]["start_seq"]:regions[2]["end_seq"]]
    reuse = compare_step_structures(step1, step2, regions[1], regions[2])
    known_path = _validate_fresh_binding(capture, capture_dir, root)
    value_differences = {
        "t_bits": [regions[1].get("t_bits"), regions[2].get("t_bits")],
        "dt_bits": [regions[1].get("dt_bits"), regions[2].get("dt_bits")],
        "gradient_start_bits": [regions[1].get("start_state", {}).get("gradient"),
                                regions[2].get("start_state", {}).get("gradient")],
        "final_endpoint_bits": regions[2].get("end_state"),
    }
    return {
        "schema": "regular-2step-structure-report-v1",
        "verdict": "REUSE_PROVEN",
        "acquisition_id": capture["acquisition_id"],
        "capture_sha256": _sha(capture_dir / "capture.json"),
        "trace_sha256": _sha(capture_dir / "trace.jsonl"),
        "acquisition_seal_sha256": _sha(capture_dir / "acquisition_seal.json"),
        "independent_objdump_decoded_rows": decoded,
        "address_validated_rows": address_rows,
        "observation_counts": observation_counts,
        "caller_corridor": corridor_proof,
        "reuse": reuse,
        "value_differences": value_differences,
        "claim_scope": "actual step1/step2 structural reuse in this acquisition only",
        "distinct_from_known_path": str(known_path) if known_path else None,
    }


def compare_pair(known_dir: Path, fresh_dir: Path, root: Path) -> dict:
    """Replay both acquisitions and require the fresh receipt to bind to known."""
    known = compare(known_dir, root)
    fresh = compare(fresh_dir, root)
    fresh_capture = json.loads((Path(fresh_dir) / "capture.json").read_text(encoding="utf-8"))
    binding = fresh_capture["distinct_from"]
    _require(binding["acquisition_id"] == known["acquisition_id"] and
             fresh["acquisition_id"] != known["acquisition_id"], "pair acquisition binding")
    return {"schema": "regular-2step-pair-replay-v1", "verdict": "PAIR_REUSE_PROVEN",
            "known": known, "fresh": fresh,
            "roles_compared": ["logical_role", "bits", "provenance"],
            "runtime_address_equality_required_across_processes": False}
