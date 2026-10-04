import json, re
from pathlib import Path

ROOT = Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo")
MASK = (1 << 64) - 1

REG32 = {
    "eax":"rax","ebx":"rbx","ecx":"rcx","edx":"rdx","esi":"rsi","edi":"rdi",
    "ebp":"rbp","esp":"rsp",
    **{f"r{i}d":f"r{i}" for i in range(8,16)}
}
MEM_RE = re.compile(r"(?:%(?:fs|gs):)?(?:[-+]?(?:0x[0-9a-fA-F]+|\d+))?\([^)]*\)|%(?:fs|gs):(?:[-+]?(?:0x[0-9a-fA-F]+|\d+))")

def val(text):
    return int(text, 0)

def reg_value(name, pre, row):
    name = name.lstrip("%")
    if name in ("eiz","riz"):
        return 0
    if name == "rip":
        code = bytes.fromhex(row.get("instruction_bytes", row.get("bytes", "")))
        return (row["pc"] + len(code)) & MASK
    if name in REG32:
        return int(pre["gpr"][REG32[name]], 16) & 0xffffffff
    return int(pre["gpr"][name], 16)

def ea(expr, pre, row):
    expr = expr.strip().lstrip("*")
    seg = None
    m = re.match(r"^%(fs|gs):(.*)$", expr)
    if m:
        seg, expr = m.group(1), m.group(2)
    base_addr = 0
    if "(" in expr:
        disp, inside = expr.split("(", 1)
        inside = inside[:-1]
        parts = [p.strip() for p in inside.split(",")]
        while len(parts) < 3:
            parts.append("")
        base, index, scale = parts[:3]
        if disp:
            base_addr += val(disp)
        if base:
            base_addr += reg_value(base, pre, row)
        if index:
            base_addr += reg_value(index, pre, row) * (int(scale,0) if scale else 1)
    else:
        base_addr += val(expr) if expr else 0
    if seg:
        base_addr += int(pre["segment_bases"][seg + "_base"], 16)
    return base_addr & MASK

def asm_memory_operands(assembly):
    return MEM_RE.findall(assembly)

def check_case(case):
    cdir = ROOT / "runtime_trace" / "regular_2step" / "artifacts" / case
    cap = json.loads((cdir / "capture.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (cdir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    cor = cap["caller_corridor"]
    caller = rows[cor["start_seq"]:cor["end_seq"]]
    read_checked = write_checked = 0
    errors = []
    unsupported = []
    recomputed_writes = []

    for row in caller:
        pre = row["pre"]
        for obs in row.get("pre_memory_observations", []):
            try:
                got = ea(obs["operand"], pre, row)
            except Exception as exc:
                unsupported.append(("read", row["seq"], row["assembly"], obs["operand"], repr(exc)))
                continue
            if got != obs["address"]:
                errors.append(("read_ea", row["seq"], row["assembly"], obs["operand"], got, obs["address"]))
            read_checked += 1

        for wr in row.get("possible_memory_writes", []):
            kind = wr["kind"]
            try:
                if kind in ("CALL_STACK", "PUSH_STACK"):
                    got = (int(pre["gpr"]["rsp"],16) - 8) & MASK
                elif kind == "EXPLICIT":
                    candidates = [(x, ea(x, pre, row)) for x in asm_memory_operands(row["assembly"])]
                    hits = [(x,a) for x,a in candidates if a == wr["address"]]
                    if len(hits) != 1:
                        errors.append(("write_candidate", row["seq"], row["assembly"], candidates, wr["address"]))
                        continue
                    got = hits[0][1]
                else:
                    unsupported.append(("write", row["seq"], row["assembly"], kind))
                    continue
            except Exception as exc:
                unsupported.append(("write", row["seq"], row["assembly"], kind, repr(exc)))
                continue
            if got != wr["address"]:
                errors.append(("write_ea", row["seq"], row["assembly"], got, wr["address"]))
            recomputed_writes.append((row["seq"], got, wr["size"], kind, wr))
            write_checked += 1

    step1 = cap["regions"][1]
    protected = {}
    for role in ("q","full_v","latent"):
        p = step1["pointers"][role]
        protected[role] = (p, p + 16)
    overlaps = []
    for seq, addr, size, kind, wr in recomputed_writes:
        for role,(lo,hi) in protected.items():
            if addr < hi and lo < addr + size:
                overlaps.append((seq,role,addr,size,kind))

    gradient = cap["regions"][2]["pointers"]["gradient"]
    grad_writes = [(seq,addr,size,wr.get("before_bits"),wr.get("after_bits"),wr.get("value_changed"))
                   for seq,addr,size,kind,wr in recomputed_writes
                   if addr < gradient+16 and gradient < addr+size]

    result = {
        "case":case,
        "caller_rows":len(caller),
        "read_checked":read_checked,
        "write_checked":write_checked,
        "unsupported":unsupported,
        "errors":errors,
        "protected_overlaps":overlaps,
        "gradient_pointer":gradient,
        "gradient_writes":grad_writes,
    }
    print(json.dumps(result, sort_keys=True))
    if unsupported or errors or overlaps:
        raise SystemExit(2)

for case in ("known-03","fresh-03"):
    check_case(case)
