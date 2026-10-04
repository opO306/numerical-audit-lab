import json
from fractions import Fraction
from pathlib import Path
ROOT=Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo\runtime_trace\regular_2step\artifacts\derived")

def p2(k):
    return Fraction(1<<k,1) if k>=0 else Fraction(1,1<<(-k))

def bits_fraction(s):
    b=int(s,16); sign=-1 if b>>63 else 1
    exp=(b>>52)&0x7ff; frac=b&((1<<52)-1)
    if exp==0x7ff: raise ValueError("nonfinite")
    if exp==0:
        m=frac
        v=Fraction(m,1)*p2(-1074)
    else:
        m=(1<<52)|frac
        v=Fraction(m,1)*p2(exp-1023-52)
    return sign*v

def round_even(x):
    assert x>=0
    q,r=divmod(x.numerator,x.denominator)
    twice=r*2
    if twice<x.denominator: return q
    if twice>x.denominator: return q+1
    return q if q%2==0 else q+1

def encode_rne(x):
    signbit=0
    if x<0: signbit=1<<63; x=-x
    if x==0: return signbit
    e=x.numerator.bit_length()-x.denominator.bit_length()
    while x<p2(e): e-=1
    while x>=p2(e+1): e+=1
    if e>=-1022:
        q=round_even(x/p2(e-52))
        if q==(1<<53):
            q=1<<52; e+=1
        if e>1023: return signbit | (0x7ff<<52)
        exp=e+1023
        return signbit | (exp<<52) | (q-(1<<52))
    q=round_even(x/p2(-1074))
    if q==0: return signbit
    if q>=(1<<52):
        return signbit | (1<<52) | (q-(1<<52))
    return signbit | q

for case in ("known","fresh"):
    d=json.loads((ROOT/case/"numeric_ir.json").read_text(encoding="utf-8"))
    bad=[]
    counts={}
    for op in d["operations"]:
        kind=op["operation_kind"]; counts[kind]=counts.get(kind,0)+1
        a=bits_fraction(op["input0_raw_bits"]); b=bits_fraction(op["input1_raw_bits"])
        if kind=="ADD_BINARY64": exact=a+b
        elif kind=="SUB_BINARY64": exact=a-b
        elif kind=="MUL_BINARY64": exact=a*b
        else: raise AssertionError(kind)
        got=encode_rne(exact)
        expected=int(op["output_raw_bits"],16)
        if got!=expected:
            bad.append((op["ir_sequence"],kind,hex(got),hex(expected)))
    print(case,"ops",len(d["operations"]),"counts",counts,"exact_rne_mismatches",bad)
    assert not bad
print("INDEPENDENT_EXACT_BINARY64=PASS")
