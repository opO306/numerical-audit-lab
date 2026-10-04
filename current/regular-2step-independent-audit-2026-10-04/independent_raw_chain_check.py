import hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo")
BASE=ROOT/"runtime_trace"/"regular_2step"

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

old=(ROOT/"runtime_trace"/"harness.py").read_bytes()
new=(ROOT/"runtime_trace"/"harness_nsteps2.py").read_bytes()
token_old=b"n_steps=1"
token_new=b"n_steps=2"
assert old.count(token_old)==1, old.count(token_old)
assert old.replace(token_old,token_new,1)==new
print("HARNESS_ONE_TOKEN_CHANGE=PASS")

summaries=[]
for case,derived_name in (("known-03","known"),("fresh-03","fresh")):
    cdir=BASE/"artifacts"/case
    cap=json.loads((cdir/"capture.json").read_text(encoding="utf-8"))
    raw=(cdir/"trace.jsonl").read_bytes()
    rows=[json.loads(x) for x in raw.splitlines()]
    assert sha_bytes(raw)==cap["trace_sha256"]
    assert len(rows)==cap["record_count"]==1428
    assert [r["seq"] for r in rows]==list(range(1428))
    ch="0"*64
    for r in rows:
        unsigned={k:v for k,v in r.items() if k!="chain"}
        ch=hashlib.sha256(bytes.fromhex(ch)+canon(unsigned)).hexdigest()
        assert r["chain"]==ch, ("chain",case,r["seq"])
    assert ch==cap["final_chain"]

    regs=cap["regions"]
    assert [r["occurrence"] for r in regs]==["init","step1","step2"]
    init,step1,step2=regs
    cor=cap["caller_corridor"]
    assert (init["start_seq"],init["end_seq"])==(0,191)
    assert (step1["start_seq"],step1["end_seq"])==(191,446)
    assert (cor["start_seq"],cor["end_seq"])==(446,1173)
    assert (step2["start_seq"],step2["end_seq"])==(1173,1428)
    assert len(rows[step1["start_seq"]:step1["end_seq"]])==255
    assert len(rows[step2["start_seq"]:step2["end_seq"]])==255
    assert len(rows[cor["start_seq"]:cor["end_seq"]])==727

    def body_sig(r):
        return (r["module_sha256"],r["elf_address"],r.get("bytes",r.get("instruction_bytes")),r["opcode"],r["kind"])
    assert [body_sig(r) for r in rows[step1["start_seq"]:step1["end_seq"]]] == [body_sig(r) for r in rows[step2["start_seq"]:step2["end_seq"]]]

    hand=cap["process_local_handoff"]
    assert hand["same_process"] is True
    assert hand["from_acquisition_id"]==hand["to_acquisition_id"]==cap["acquisition_id"]
    for role in ("q","full_v","latent"):
        bits=step1["end_state"][role]
        ptr=step1["pointers"][role]
        hr=hand["roles"][role]
        assert bits==hr["from_bits"]==cor["start_component_bits"][role]==cor["end_component_bits"][role]==hr["to_bits"]==step2["start_state"][role]
        assert ptr==hr["from_pointer"]==cor["protected_role_pointers"][role]==cor["entry_abi"]["pointers"][role]==hr["to_pointer"]==step2["pointers"][role]

    assert step1["end_state"]["gradient"]==cor["start_component_bits"]["gradient"]
    assert cor["end_component_bits"]["gradient"]==step2["start_state"]["gradient"]==["0x0000000000000000"]*2
    assert hand["gradient_boundary"]["from_bits"]==step1["end_state"]["gradient"]
    assert hand["gradient_boundary"]["to_bits"]==["0x0000000000000000"]*2
    assert hand["gradient_boundary"]["pointer"]==step2["pointers"]["gradient"]
    assert hand["gradient_boundary"]["step1_pointer"]==step1["pointers"]["gradient"]

    corridor_rows=rows[cor["start_seq"]:cor["end_seq"]]
    for name,reg in (("t","xmm0"),("dt","xmm1")):
        src=cor["argument_sources"][name]
        ix=src["instruction_sequence"]
        rr=corridor_rows[ix]
        assert rr["seq"]==cor["start_seq"]+ix
        assert rr["assembly"]==src["assembly"]
        matches=[o for o in rr["pre_memory_observations"] if
                 o["address"]==src["source_memory_address"] and
                 o["operand"]==src["source_operand"] and
                 o["size"]==8 and o["status"]=="OK" and
                 o["timing"]=="PRE_INSTRUCTION"]
        assert len(matches)==1
        expected=step2[f"{name}_bits"]
        assert src["source_bits"]==expected
        assert src["destination_register"]==reg
        assert matches[0]["bytes_hex"]==int(expected,16).to_bytes(8,"little").hex()

    hout=json.loads((cdir/"harness_output.json").read_text(encoding="utf-8"))
    assert hout["n_steps"]==1
    assert cap["harness_binding"]["inherited_stale_n_steps_metadata"] is True
    assert cap["harness_binding"]["executed_native_step_calls"]==2
    assert cap["harness_binding"]["source_proof"]["replacement_count"]==1
    expected_out=step2["end_state"]["q"]+step2["end_state"]["full_v"]
    assert hout["output_bits"]==expected_out

    ddir=BASE/"artifacts"/"derived"/derived_name
    ir=json.loads((ddir/"numeric_ir.json").read_text(encoding="utf-8"))
    v2=json.loads((ddir/"v2_correspondence.json").read_text(encoding="utf-8"))
    ep=json.loads((ddir/"endpoint.json").read_text(encoding="utf-8"))
    chain=json.loads((ddir/"chain.json").read_text(encoding="utf-8"))
    kinds=Counter(o["operation_kind"] for o in ir["operations"])
    assert len(ir["operations"])==22
    assert kinds==Counter({"ADD_BINARY64":7,"SUB_BINARY64":5,"MUL_BINARY64":10})
    assert len(ir["values"])==151
    assert len(v2["operations"])==22
    assert len(v2["state_bindings"])==107
    assert sum(x["binding_kind"]=="CARRIED" for x in v2["state_bindings"])==6
    assert len(v2["boundaries"])==6
    assert len(ep)==8
    endpoint_bits={(x["component"],x["byte_offset"]):x["center_bits"] for x in ep}
    for role in ("q","full_v","latent","gradient"):
        assert endpoint_bits[(role,0)]==step2["end_state"][role][0]
        assert endpoint_bits[(role,8)]==step2["end_state"][role][1]
    assert chain["final_boundary"]==ep
    assert chain["acquisition_id"]==cap["acquisition_id"]
    assert chain["audit_status"]=="INDEPENDENT AUDIT PENDING"
    assert chain["init_return_to_step1_entry"].startswith("UNTRACED")

    summaries.append({
      "case":case,
      "acquisition_id":cap["acquisition_id"],
      "process_identity":cap["process_identity"],
      "trace_sha256":cap["trace_sha256"],
      "final_chain":cap["final_chain"],
      "record_count":len(rows),
      "step_rows":255,
      "caller_rows":727,
      "ops":dict(kinds),
      "values":len(ir["values"]),
      "state_bindings":len(v2["state_bindings"]),
      "carried":sum(x["binding_kind"]=="CARRIED" for x in v2["state_bindings"]),
      "endpoint_lanes":len(ep),
      "harness_endpoint_match":True,
      "stale_harness_metadata_detected":True,
    })

assert summaries[0]["acquisition_id"]!=summaries[1]["acquisition_id"]
assert summaries[0]["process_identity"]!=summaries[1]["process_identity"]
assert summaries[0]["trace_sha256"]!=summaries[1]["trace_sha256"]
print("RAW_CHAIN_RECONSTRUCTION=PASS")
for s in summaries: print(json.dumps(s,sort_keys=True))
