"""Mutate the actual capture; rehash to exercise checks beyond integrity hashes."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform

import pytest

from runtime_trace.correspondence import AuditError, check, disassembly_for_rows, verify_flow

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"runtime_trace/artifacts/attempt-05"
pytestmark=pytest.mark.skipif(platform.system()!="Linux",reason="real captured ELF modules are in the WSL environment")


def load():
    return json.loads((OUT/"capture.json").read_text()),[json.loads(x) for x in (OUT/"trace.jsonl").read_text().splitlines()]


def rehash(capture,rows,out):
    chain="0"*64
    for row in rows:
        row.pop("chain",None)
        chain=hashlib.sha256(bytes.fromhex(chain)+json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        row["chain"]=chain
    stream="".join(json.dumps(row,separators=(",",":"))+"\n" for row in rows).encode()
    capture.update(trace_sha256=hashlib.sha256(stream).hexdigest(),final_chain=chain,
                   record_count=len(rows),scalar_fp_count=sum(r["kind"] in {"ADD","SUB","MUL"} for r in rows),
                   opcode_histogram=dict(Counter(r["opcode"] for r in rows)))
    (out/"trace.jsonl").write_bytes(stream)
    (out/"capture.json").write_text(json.dumps(capture))
    (out/"harness_output.json").write_bytes((OUT/"harness_output.json").read_bytes())


def test_real_capture_positive():
    assert check(OUT,ROOT)["verdict"]=="PASS"


@pytest.mark.parametrize("mutation,reason",[
    ("missing","missing/reordered machine instruction"),("duplicate","missing/reordered machine instruction"),
    ("reorder","missing/reordered machine instruction"),("operand","memory/register def-use bits"),
    ("result","scalar result rounding"),("address","effective address"),
    ("instruction_bytes","executed instruction byte correspondence"),("module_hash","record module hash identity"),
    ("mxcsr","MXCSR control condition"),("thread","thread changed"),
    ("endpoint","buffer endpoint not explained"),("fixture_output","harness output vs traced"),
    ("boundary_pointer","boundary pointer vs actual ABI register"),
    ("routing_width","integer extension operand widths"),
])
def test_actual_trace_mutations_refuse_pass(tmp_path,mutation,reason):
    capture,rows=load()
    index=next(i for i,r in enumerate(rows) if r["phase"]=="step" and r["opcode"]=="mulsd" and int(r["operands"][0]["raw_bits"],16)!=0)
    row=rows[index]
    if mutation=="missing": rows.pop(index)
    elif mutation=="duplicate": rows.insert(index,deepcopy(row))
    elif mutation=="reorder":
        rows[index],rows[index+1]=rows[index+1],rows[index]
        for i,r in enumerate(rows):r["seq"]=i
    elif mutation=="operand":row["operands"][0]["raw_bits"]=hex(int(row["operands"][0]["raw_bits"],16)^1)
    elif mutation=="result":row["result_bits"]=hex(int(row["result_bits"],16)^1)
    elif mutation=="address":row["operands"][0]["address"]+=0x10000000
    elif mutation=="instruction_bytes":row["bytes"]="00"+row["bytes"][2:]
    elif mutation=="module_hash":row["module_sha256"]="0"*64
    elif mutation=="mxcsr":
        # Change the whole region to keep linkage valid, then test its controls.
        for r in rows:
            for context in [r["pre"],r["post"]]:context["mxcsr"]|=1<<15
    elif mutation=="thread":row["ptid"][1]+=1
    elif mutation=="endpoint":capture["regions"][-1]["end_state"]["q"]="0x0"
    elif mutation=="boundary_pointer":
        capture["regions"][1]["pointers"]["latent"]+=0x10000000
    elif mutation=="routing_width":
        bad=next(r for r in rows if r["opcode"]=="movslq" and r["operands"][0]["kind"]=="memory")
        bad["operands"][0]["width"]=8
    if mutation in {"missing","duplicate"}:
        # Keep count/sequence metadata self-consistent so actual PC linkage must
        # detect the removed/duplicated occurrence rather than a hash/count check.
        for i,r in enumerate(rows):r["seq"]=i
        capture["regions"][-1]["end_seq"]=len(rows)
    rehash(capture,rows,tmp_path)
    if mutation=="fixture_output":
        harness=json.loads((tmp_path/"harness_output.json").read_text())
        harness["output_bits"][0]="0x0"
        (tmp_path/"harness_output.json").write_text(json.dumps(harness))
    with pytest.raises(AuditError,match=reason):check(tmp_path,ROOT)


def test_actual_numeric_source_requires_known_bytes():
    capture,rows=load()
    decoded=disassembly_for_rows(rows,capture["modules"])
    # At the byte-flow checker layer, remove the legitimate latent root. The
    # existing execution data must then be refused at its first dependent FP op.
    del capture["regions"][1]["pointers"]["latent"]
    with pytest.raises(AuditError,match="unknown numerical input source"):
        verify_flow(rows,capture,decoded)
