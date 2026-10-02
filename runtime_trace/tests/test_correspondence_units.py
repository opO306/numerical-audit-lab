from copy import deepcopy
import pytest

from runtime_trace.correspondence import AuditError, verify_scalar, verify_linkage


def multiplication():
    return {"opcode":"mulsd","operands":[
        {"kind":"memory","raw_bits":"0x3fd0000000000000","width":8},
        {"kind":"register","register":"xmm1","raw_bits":"0x3f90000000000000","width":8}],
        "result_bits":"0x3f70000000000000",
        "pre":{"xmm":{"xmm1":"0x00000000000000003f90000000000000"},"extra_vectors":{}},
        "post":{"xmm":{"xmm1":"0x00000000000000003f70000000000000"},"extra_vectors":{}}}


def test_exact_dyadic_scalar_check():
    verify_scalar(multiplication())


@pytest.mark.parametrize("mutation",["operand","result","upper","nonfinite"])
def test_scalar_mutation_is_rejected(mutation):
    record=multiplication()
    if mutation=="operand":record["operands"][0]["raw_bits"]="0x3fd0000000000001"
    elif mutation=="result":record["result_bits"]="0x3f70000000000001"
    elif mutation=="upper":record["post"]["xmm"]["xmm1"]="0x00000000000000013f70000000000000"
    else:record["operands"][0]["raw_bits"]="0x7ff0000000000000"
    with pytest.raises(AuditError):verify_scalar(record)


def example_linkage():
    rows=[]
    for seq,(pc,post,phase) in enumerate([(100,101,"init"),(101,200,"init"),(300,400,"step")]):
        pre={"gpr":{"rip":hex(pc)},"xmm":{},"mxcsr":0x1fa0,"eflags":0}
        after={**pre,"gpr":{"rip":hex(post)}}
        rows.append({"seq":seq,"phase":phase,"runtime_pc":pc,"post_pc":post,"ptid":[1,1,0],"pre":pre,"post":after})
    state={x:"0x0" for x in ["q","full_v","latent"]}
    regions=[{"phase":"init","entry_pc":100,"return_pc":200,"start_seq":0,"end_seq":2,"end_state":state},
             {"phase":"step","entry_pc":300,"return_pc":400,"start_seq":2,"end_seq":3,"start_state":state}]
    return rows,regions


def test_occurrence_linkage_positive():
    rows,regions=example_linkage();verify_linkage(rows,regions,3)


@pytest.mark.parametrize("mutation",["missing","duplicate","reorder","pc","thread","state"])
def test_missing_duplicate_reorder_and_boundary_mutations(mutation):
    rows,regions=example_linkage()
    if mutation=="missing":rows.pop(1)
    elif mutation=="duplicate":rows.insert(1,deepcopy(rows[0]))
    elif mutation=="reorder":rows[0],rows[1]=rows[1],rows[0]
    elif mutation=="pc":rows[1]["runtime_pc"]=102
    elif mutation=="thread":rows[1]["ptid"]=[1,2,0]
    else:regions[1]["start_state"]={**regions[1]["start_state"],"latent":"0x1"}
    with pytest.raises(AuditError):verify_linkage(rows,regions,3)
