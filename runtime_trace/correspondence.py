"""Post-acquisition checker draft. No import from the GDB acquisition code.

Uses original module bytes + objdump, raw-state linkage, byte flow and Fraction
rounding. machine_mapping is opened only after acquisition and these checks.
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


class AuditError(ValueError):
    pass


def require(condition, reason):
    if not condition: raise AuditError(reason)


class FrozenBinaryResolver:
    """Resolve module hashes only within the evidence package, never runtime paths."""

    def __init__(self, root=None):
        self.root = (Path(root) if root is not None else Path(__file__).resolve().parents[1]).resolve()
        manifest_path = self.root / "runtime_trace/frozen_binaries/manifest.json"
        require(manifest_path.is_file(), "packaged module manifest missing")
        manifest = json.loads(manifest_path.read_text())
        require(manifest.get("schema") == "runtime-trace-frozen-binaries-v1", "packaged module manifest schema")
        self.modules = manifest["modules"]
        self.cache = {}

    def resolve(self, digest):
        require(digest in self.modules, f"unpackaged module SHA-256: {digest}")
        if digest not in self.cache:
            relative = Path(self.modules[digest])
            path = (self.root / relative).resolve()
            require(not relative.is_absolute() and path.is_relative_to(self.root), "packaged module path escapes root")
            require(path.is_file(), f"packaged module missing: {digest}")
            image = path.read_bytes()
            require(hashlib.sha256(image).hexdigest() == digest, f"packaged module raw hash: {digest}")
            self.cache[digest] = (path, image)
        return self.cache[digest]


def constant_image(origin, modules, resolver):
    digest = origin["module_sha256"]
    require(any(m["sha256"] == digest for m in modules.values()), "constant module absent from capture")
    return resolver.resolve(digest)[1]


def raw(text, width):
    return int(text,16).to_bytes(width,"little")


def register_raw(context, name, width):
    if name.startswith(("xmm","ymm","zmm")):
        text = context["xmm"].get(name,context["extra_vectors"].get(name))
        return raw(text,{"xmm":16,"ymm":32,"zmm":64}[name[:3]])[:width]
    if name in context["gpr"]: full = name
    elif re.fullmatch(r"r\d+[dwb]",name): full = name[:-1]
    elif name.startswith("e"): full = "r"+name[1:]
    elif name in {"al","bl","cl","dl"}: full = "r"+name[0]+"x"
    elif name in {"sil","dil","bpl","spl"}: full = "r"+name[:-1]
    else: full = "r"+name
    return raw(context["gpr"][full],8)[:width]


def operand_keys(operand):
    if operand["kind"] == "memory": return [("m",operand["address"]+i) for i in range(operand["width"])]
    if operand["kind"] != "register": return []
    name = operand["register"]
    if name.startswith(("xmm","ymm","zmm")): canonical = "v"+re.search(r"\d+",name)[0]
    elif re.fullmatch(r"r\d+[dwb]",name): canonical=name[:-1]
    elif name.startswith("e"): canonical="r"+name[1:]
    elif name in {"al","bl","cl","dl"}: canonical="r"+name[0]+"x"
    elif name in {"sil","dil","bpl","spl"}: canonical="r"+name[:-1]
    elif name.startswith("r"): canonical=name
    else: canonical="r"+name
    return [("r",canonical,i) for i in range(operand["width"])]


def verify_scalar(record):
    src,dst=record["operands"]
    for operand in [src,dst]:
        bits=int(operand["raw_bits"],16)
        require((bits>>52)&2047 != 2047,"nonfinite scalar input")
        if operand["kind"]=="register":
            require(register_raw(record["pre"],operand["register"],8)==raw(operand["raw_bits"],8),"pre operand register bits")
    x=struct.unpack("<d",raw(dst["raw_bits"],8))[0]
    y=struct.unpack("<d",raw(src["raw_bits"],8))[0]
    qx,qy=Fraction.from_float(x),Fraction.from_float(y)
    op=record["opcode"]
    if op=="addsd": q=qx+qy
    elif op=="subsd": q=qx-qy
    elif op=="mulsd": q=qx*qy
    else: raise AuditError("unsupported scalar opcode")
    if q==0:
        sx,sy=int(dst["raw_bits"],16)>>63,int(src["raw_bits"],16)>>63
        negative=(sx^sy) if op=="mulsd" else (sx and sy if op=="addsd" else sx and not sy) if qx==qy==0 else False
        expected=(int(bool(negative))<<63).to_bytes(8,"little")
    else: expected=struct.pack("<d",float(q))
    require(raw(record["result_bits"],8)==expected,"scalar result rounding / operand mutation")
    require(register_raw(record["post"],dst["register"],8)==expected,"post scalar register bits")
    require(register_raw(record["pre"],dst["register"],16)[8:]==register_raw(record["post"],dst["register"],16)[8:],"scalar arithmetic upper XMM lane")


def verify_linkage(rows, regions, count):
    require(len(rows)==count,"record count / missing occurrence")
    require([r["seq"] for r in rows]==list(range(count)),"sequence / duplicate / reorder")
    require([r["phase"] for r in regions]==["init","step"],"two required regions")
    require(regions[0]["start_seq"]==0 and regions[-1]["end_seq"]==count,"region coverage endpoints")
    require(regions[0]["end_seq"]==regions[1]["start_seq"],"region coverage gap/overlap")
    for region in regions:
        subset=rows[region["start_seq"]:region["end_seq"]]
        require(bool(subset),"empty region")
        require(subset[0]["runtime_pc"]==region["entry_pc"] and subset[-1]["post_pc"]==region["return_pc"],"entry/return occurrence coverage")
        for i,r in enumerate(subset):
            require(r["phase"]==region["phase"],"phase assignment")
            require(r["ptid"]==subset[0]["ptid"],"thread changed")
            require(r["runtime_pc"]==int(r["pre"]["gpr"]["rip"],16),"pre PC")
            require(r["post_pc"]==int(r["post"]["gpr"]["rip"],16),"post PC")
            if i:
                prev=subset[i-1]
                require(prev["post_pc"]==r["runtime_pc"],"missing/reordered machine instruction")
                for field in ["gpr","xmm","mxcsr","eflags"]:
                    require(prev["post"][field]==r["pre"][field],f"pre/post linkage: {field}")
    for name in ["q","full_v","latent"]:
        require(regions[0]["end_state"][name]==regions[1]["start_state"][name],"numerical state connection")


def file_offset(module_bytes, vaddr, length):
    phoff=struct.unpack_from("<Q",module_bytes,32)[0]
    size,count=struct.unpack_from("<HH",module_bytes,54)
    for i in range(count):
        kind,flags,offset,va,_,filesz,_,_=struct.unpack_from("<IIQQQQQQ",module_bytes,phoff+i*size)
        if kind==1 and va<=vaddr and vaddr+length<=va+filesz:return offset+vaddr-va
    raise AuditError("ELF instruction outside file-backed segment")


def disassembly_for_rows(rows, modules, root=None):
    decoded={}
    resolver=FrozenBinaryResolver(root)
    for path in {r["module_path"] for r in rows}:
        module=modules[path]
        packaged_path,image=resolver.resolve(module["sha256"])
        occurrences=[r for r in rows if r["module_path"]==path]
        first=min(r["elf_address"] for r in occurrences)
        end=max(r["elf_address"]+len(bytes.fromhex(r["bytes"])) for r in occurrences)
        listing=subprocess.check_output(["objdump","-d","--no-show-raw-insn",f"--start-address={first}",f"--stop-address={end}",str(packaged_path)],text=True)
        wanted={r["elf_address"] for r in occurrences}
        for line in listing.splitlines():
            m=re.match(r"\s*([0-9a-f]+):\s+(.+)",line)
            if m and int(m[1],16) in wanted:decoded[path,int(m[1],16)]=m[2].strip()
        for r in occurrences:
            bytecode=bytes.fromhex(r["bytes"])
            require(r["module_sha256"]==module["sha256"],"record module hash identity")
            require(1<=len(bytecode)<=15,"instruction length")
            require(r["runtime_pc"]-r["module_load_base"]==r["elf_address"],"runtime PC to ELF address")
            offset=file_offset(image,r["elf_address"],len(bytecode))
            require(offset==r["elf_file_offset"] and image[offset:offset+len(bytecode)]==bytecode,"executed instruction byte correspondence")
            mapping=r["mapping"]
            require(mapping["start"]<=r["runtime_pc"]<mapping["end"] and "x" in mapping["perms"],"PC executable map")
            candidates=[s for s in module["segments"] if s["file_offset"]&~4095==mapping["file_offset"]]
            require(any(mapping["start"]-(s["vaddr"]&~4095)==r["module_load_base"] for s in candidates),"ASLR load bias")
    return decoded


def split_att(assembly):
    text=re.sub(r"\s+<[^>]*>","",assembly.split("#")[0]).strip()
    words=text.split()
    while words and words[0] in {"cs","data16"}:words.pop(0)
    opcode=words[0]
    operands=" ".join(words[1:])
    result=[];depth=0;start=0
    for i,c in enumerate(operands):
        depth+=(c=="(")-(c==")")
        if c=="," and depth==0:result.append(operands[start:i].strip());start=i+1
    if operands:result.append(operands[start:].strip())
    return opcode,result


def ea(text, record):
    text=text.lstrip("*")
    m=re.fullmatch(r"([^()]*)\(([^()]*)\)",text)
    if not m:return int(text,0)
    displacement=int(m[1],0) if m[1] else 0
    parts=m[2].split(",")
    while len(parts)<3:parts.append("")
    base,index,scale=parts
    def value(reg):
        if not reg:return 0
        if reg=="%rip":return record["runtime_pc"]+len(bytes.fromhex(record["bytes"]))
        return int.from_bytes(register_raw(record["pre"],reg[1:],8),"little")
    return (displacement+value(base)+value(index)*int(scale or 1))&((1<<64)-1)


def verify_control_pc(record, reference):
    op,args=split_att(reference)
    pc=record["runtime_pc"];next_pc=pc+len(bytes.fromhex(record["bytes"]))
    flags=record["pre"]["eflags"]
    cf,zf,sf,of,pf=bool(flags&1),bool(flags&64),bool(flags&128),bool(flags&2048),bool(flags&4)
    if op in {"ret","retq"}:expected=int(record["operands"][0]["raw_bits"],16)
    elif op.startswith("j") or op in {"call","callq"}:
        if args[0].startswith("*"):target=int(record["operands"][0]["raw_bits"],16)
        else:target=record["module_load_base"]+int(args[0],16)
        predicates={"jmp":True,"je":zf,"jz":zf,"jne":not zf,"jnz":not zf,"jb":cf,"jae":not cf,
                    "ja":not cf and not zf,"jbe":cf or zf,"jl":sf!=of,"jge":sf==of,
                    "jg":not zf and sf==of,"jle":zf or sf!=of,"js":sf,"jns":not sf,"jp":pf,"jnp":not pf,
                    "call":True,"callq":True}
        require(op in predicates,"unverified branch condition")
        expected=target if predicates[op] else next_pc
    else:expected=next_pc
    require(record["post_pc"]==expected,"observed PC disagrees with instruction occurrence")


def verify_flow(rows, capture, decoded, root=None):
    modules=capture["modules"]
    resolver=FrozenBinaryResolver(root)
    for region in capture["regions"]:
        subset=rows[region["start_seq"]:region["end_seq"]]
        knowledge={}
        for name,address in region["pointers"].items():
            for i,byte in enumerate(raw(region["start_state"][name],16)):knowledge["m",address+i]=byte
        for name,index in [("xmm0",0),("xmm1",1)]:
            for i,byte in enumerate(register_raw(subset[0]["pre"],name,8)):knowledge["r",f"v{index}",i]=byte
        for record in subset:
            reference=decoded[record["module_path"],record["elf_address"]]
            opcode,args=split_att(reference)
            require(opcode==record["opcode"],"opcode independent decode")
            verify_control_pc(record,reference)
            kind=record["kind"];ops=record["operands"]
            if opcode in {"movslq","movzbl","movzwl"}:
                expected_widths={"movslq":[4,8],"movzbl":[1,4],"movzwl":[2,4]}[opcode]
                require([o["width"] for o in ops]==expected_widths,"integer extension operand widths")
                source=raw(ops[0]["raw_bits"],expected_widths[0])
                expected=int.from_bytes(source,"little",signed=opcode=="movslq")&((1<<(8*expected_widths[1]))-1)
                require(register_raw(record["post"],ops[1]["register"],expected_widths[1])==expected.to_bytes(expected_widths[1],"little"),"integer extension result bits")
            elif opcode in {"cmpb","testb","cmpl","testl","cmpq","testq"}:
                expected_width={"cmpb":1,"testb":1,"cmpl":4,"testl":4,"cmpq":8,"testq":8}[opcode]
                require(all(o["width"]==expected_width for o in ops),"integer memory operand width")
            elif opcode=="vpbroadcastb":
                require(ops[0]["width"]==1 and int(ops[0]["raw_bits"],16)==0,"zero fill source byte")
            for context in [record["pre"],record["post"]]:
                require(context["mxcsr"]&((3<<13)|(1<<15)|(1<<6))==0,"MXCSR control condition")
                require(context["mxcsr"]&0x1f80==0x1f80,"MXCSR exception masks")
            for operand in ops:
                data=raw(operand["raw_bits"],operand["width"])
                if operand["kind"]=="register":
                    require(data==register_raw(record["pre"],operand["register"],operand["width"]),"record operand vs pre raw register")
                if operand["access"] not in {"write","control"}:
                    for key,byte in zip(operand_keys(operand),data):
                        if key in knowledge:require(knowledge[key]==byte,"memory/register def-use bits")
            if kind in {"ADD","SUB","MUL","MOVE"}:
                require(len(args)==2 and len(ops)==2,"two-operand correspondence")
                for text,operand in zip(args,ops):
                    if text.startswith("%"):
                        require(operand["kind"]=="register" and operand["register"]==text[1:],"instruction register operand role")
                    elif not text.startswith("$"):
                        require(operand["kind"]=="memory" and operand["address"]==ea(text,record),"effective address / alias decode")
            if kind=="ROUTING":
                for text,operand in zip(args,ops):
                    if operand["kind"]=="memory":require(operand["address"]==ea(text,record),"routing effective address")
            if kind in {"ADD","SUB","MUL"}:
                require(opcode in {"addsd","subsd","mulsd"},"scalar instruction class")
                for operand in ops:
                    data=raw(operand["raw_bits"],8)
                    keys=operand_keys(operand)
                    if not all(key in knowledge for key in keys):
                        origin=operand.get("constant_origin")
                        require(origin is not None,"unknown numerical input source")
                        image=constant_image(origin,modules,resolver)
                        require(image[origin["file_offset"]:origin["file_offset"]+8]==data,"ELF constant source bytes")
                verify_scalar(record)
            destination=ops[-1] if kind in {"ADD","SUB","MUL","MOVE","STACK","ZERO","ZERO_FILL"} else None
            exempt=set()
            if destination:
                result=raw(record["result_bits"],destination["width"])
                if destination["kind"]=="register":
                    require(result==register_raw(record["post"],destination["register"],destination["width"]),"post destination bits")
                    exempt.add(operand_keys(destination)[0][1])
                if kind in {"MOVE","STACK"}:require(result==raw(ops[0]["raw_bits"],ops[0]["width"]),"copy bit preservation")
                if kind in {"ZERO","ZERO_FILL"}:require(not any(result),"zero source/output")
                src_keys=operand_keys(ops[0]);source_known=[key in knowledge for key in src_keys]
                if ops[0].get("constant_origin"):
                    origin=ops[0]["constant_origin"]
                    image=constant_image(origin,modules,resolver)
                    require(image[origin["file_offset"]:origin["file_offset"]+len(result)]==raw(ops[0]["raw_bits"],len(result)),"constant load bytes")
                    source_known=[True]*len(result)
                for i,(key,byte) in enumerate(zip(operand_keys(destination),result)):
                    if kind not in {"MOVE","STACK"} or i<len(source_known) and source_known[i]:knowledge[key]=byte
                    else:knowledge.pop(key,None)
                if destination["kind"]=="register":
                    name=destination["register"];keyname=operand_keys(destination)[0][1]
                    if name.startswith("xmm"):
                        if opcode in {"movq","vmovd"} or opcode=="movsd" and ops[0]["kind"]=="memory":
                            high=register_raw(record["post"],name,16)[destination["width"]:]
                            require(not any(high),"copy XMM upper zero")
                            for i in range(destination["width"],16):knowledge["r",keyname,i]=0
                        elif opcode=="movsd":
                            require(register_raw(record["pre"],name,16)[8:]==register_raw(record["post"],name,16)[8:],"register MOVSD high lane preserved")
                    elif destination["width"]==4:
                        require(not any(register_raw(record["post"],keyname,8)[4:]),"GPR zero extension")
                        for i in range(4,8):knowledge["r",keyname,i]=0
            if opcode=="xor" and len(args)==2 and args[0]==args[1] and ops:
                operand=ops[-1];data=register_raw(record["post"],operand["register"],operand["width"])
                require(not any(data),"integer xor zero")
                name=operand_keys(operand)[0][1];exempt.add(name)
                for i in range(8 if operand["width"]==4 else operand["width"]):knowledge["r",name,i]=0
            for name in record["pre"]["gpr"]:
                if name not in exempt and record["pre"]["gpr"][name]!=record["post"]["gpr"][name]:
                    for i in range(8):knowledge.pop(("r",name,i),None)
        for name,address in region["pointers"].items():
            for i,byte in enumerate(raw(region["end_state"][name],16)):
                require(knowledge.get(("m",address+i))==byte,"buffer endpoint not explained by captured writes")


def check(out,root):
    capture=json.loads((out/"capture.json").read_text())
    require(capture["verdict"]=="CAPTURED","acquisition REFUSED or incomplete")
    stream=(out/"trace.jsonl").read_bytes()
    require(hashlib.sha256(stream).hexdigest()==capture["trace_sha256"],"trace raw hash")
    rows=[json.loads(line) for line in stream.splitlines()]
    require(capture["scalar_fp_count"]==sum(r["kind"] in {"ADD","SUB","MUL"} for r in rows),"scalar count metadata")
    require(capture["opcode_histogram"]==dict(Counter(r["opcode"] for r in rows)),"opcode count metadata")
    chain="0"*64
    for record in rows:
        unsigned={k:v for k,v in record.items() if k!="chain"}
        chain=hashlib.sha256(bytes.fromhex(chain)+json.dumps(unsigned,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        require(chain==record["chain"],"record hash chain")
    require(chain==capture["final_chain"],"chain endpoint")
    verify_linkage(rows,capture["regions"],capture["record_count"])
    for region in capture["regions"]:
        entry=rows[region["start_seq"]]["pre"]["gpr"]
        for name,register in [("q","rcx"),("full_v","r8"),("latent","r9")]:
            require(region["pointers"][name]==int(entry[register],16),"boundary pointer vs actual ABI register")
    decoded=disassembly_for_rows(rows,capture["modules"],root)
    verify_flow(rows,capture,decoded,root)
    output=json.loads((out/"harness_output.json").read_text())["output_bits"]
    endpoint=capture["regions"][-1]["end_state"]
    endpoint_bits=[f"0x{struct.unpack_from('<Q',raw(endpoint[name],16),8*i)[0]:016x}" for name in ["q","full_v"] for i in range(2)]
    require(output==endpoint_bits,"harness output vs traced numerical endpoint")
    manifest=json.loads((root/"benchmarks/gate2b/fixtures/cloud-2026-10-01/manifest.json").read_text())
    fixture=gzip.decompress((root/"benchmarks/gate2b/fixtures/cloud-2026-10-01/regular_forward.u64.gz").read_bytes())
    require(hashlib.sha256(fixture).hexdigest()==manifest["files"]["regular_forward"]["sha256_raw"],"frozen fixture raw hash")
    shape=manifest["files"]["regular_forward"]["shape"]
    expected=[f"0x{struct.unpack_from('<Q',fixture,8*(i*shape[1]+1))[0]:016x}" for i in range(4)]
    require(output==expected,"one-step frozen output bits")
    # This is the FIRST mapping read: acquisition and all above checks already finished.
    mapping=json.loads((root/"audit/gate2c1/machine_mapping.json").read_text())
    comparison={}
    for phase in ["init","step"]:
        observed=[r for r in rows if r["phase"]==phase and r["kind"] in {"ADD","SUB","MUL"}]
        reference=[r for r in mapping["phases"][phase] if r["kind"]=="arithmetic"]
        require([(r["elf_address"],r["kind"]) for r in observed]==[(int(r["disassembly_address"],16),r["T_bin"][0]) for r in reference],"post-hoc machine mapping order")
        comparison[phase]={"runtime_scalar_occurrences":len(observed),"mapping_arithmetic_rows":len(reference),"order_address_kind_match":True}
    return {"verdict":"PASS","record_count":len(rows),"scalar_fp_count":sum(r["kind"] in {"ADD","SUB","MUL"} for r in rows),
            "opcode_histogram":dict(Counter(r["opcode"] for r in rows)),"mxcsr_values":sorted({c["mxcsr"] for r in rows for c in [r["pre"],r["post"]]}),
            "fixture_bits_match":True,"fixture_output_bits":expected,"machine_mapping_posthoc":comparison,
            "missing_occurrences":0,"duplicate_occurrences":0,"mapping_used_in_acquisition":False,
            "scope":"draft correspondence checks for this captured regular one-step; not a formal execution certificate"}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True)
    ap.add_argument("--report",default="correspondence.json");args=ap.parse_args()
    out=Path(args.out).resolve();root=Path(__file__).resolve().parents[1]
    require(Path(args.report).name==args.report,"report must be a filename in the artifact folder")
    checker_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:result=check(out,root)
    except Exception as exc:result={"verdict":"FAIL","reason":f"{type(exc).__name__}: {exc}"}
    result["checker_sha256"]=checker_hash
    path=out/args.report
    with path.open("x") as file:file.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
    return 0 if result["verdict"]=="PASS" else 1


if __name__=="__main__":raise SystemExit(main())
