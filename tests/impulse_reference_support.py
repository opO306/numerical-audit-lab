"""AUTHOR TEST CONTROLS ONLY. These are not approved runtime instances."""
import json
from fractions import Fraction as Q
from pathlib import Path

SPEC_ID='3c3773b306700b0cf2dced1a618ae73ad81c7dd4abbf36764fc6ec3191ff2bc1'


def input_object(q=(6,2,1)):
    state={'position_grid':{'kind':'FX','width':'96','frac_bits':'48'},
           'momentum_grid':{'kind':'FX','width':'96','frac_bits':'80'},'atoms':[]}
    for idx,pos in enumerate([(0,0,0),q]):
        state['atoms'].append({'atom_id':str(idx+1)*64,'species':'Ar40',
            'position_raw':[str(int(Q(x)*(1<<48))) for x in pos],
            'momentum_raw':['0','0','0']})
    fields=json.loads(Path('specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json').read_text())['required_instance_fields']
    budget={k:'1' for k in fields}
    budget.update(N0='128',P0='128',N_max='512',P_max='512',max_attempts='3',exp_order_max='512',
        integer_bit_max='100000',rational_num_bit_max='100000',rational_den_bit_max='100000',
        work_unit_max=str(10**40),input_parse_bytes='1048576',private_certificate_bytes='1048576',
        temporary_allocation_bytes=str(10**12),live_allocation_bytes=str(10**15),
        legacy_sqrt_bits_max='512',legacy_work_bits_max='512',legacy_order_max='1000000',
        basis_record_sha256='a'*64,issuer_sha256='b'*64,profile_version='1')
    return {'schema':'LAB_C1B1_IMPULSE_INPUT_V1','spec_sha256':SPEC_ID,'state':state,'budget':budget,
        'acquisition':{'record_id':'3'*64,'acquisition_id':'4'*64,'phase':'FIRST_HALF_KICK',
        'full_half':'HALF_OF_FULL_DT','executor_source_sha256':'5'*64,
        'acquisition_tool_sha256':'6'*64,'previous_occurrence_sha256':None}}


def encoded(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()


def reference_policy(obj):
    from independent_checker.c1b1.impulse.policy import ReferencePolicy
    return ReferencePolicy(**{k:int(obj['budget'][k]) for k in ReferencePolicy.__dataclass_fields__})


def nominal_diagnostic(R):
    """DIAGNOSTIC ONLY: mpmath V and numerical differentiation; no proof claim.

    Value expression uses direct sums and mpmath's differentiation, not the
    producer's derivative, exp or interval helpers.
    """
    import mpmath as mp
    records=json.loads(Path('specs/c1b1-independent-impulse-v1-attempt-reason-null/constants.json').read_text())['records']
    c={r['key']:mp.mpf(r['lab_canonical']['n'])/mp.mpf(r['lab_canonical']['d'])
       for r in records if r['role']=='NOMINAL_MODEL'}
    def value(r):
        numerator=1+mp.fsum(c[f'RET_A_{m}']*r**m for m in range(1,6))
        denominator=1+mp.fsum(c[f'RET_B_{m}']*r**m for m in range(1,7))
        result=mp.mpf(0)
        for family,start,end,klo,khi,kadd in [('BO',-1,2,3,8,1),('REL',0,2,2,4,0),('QED',0,2,3,4,0)]:
            for j in (1,2):
                poly=mp.fsum(c[f'a_{family}_{i}_{j}']*r**i for i in range(start,end+1))
                result+=mp.exp(-c[f'alpha_{family}_{j}']*r)*poly
            z=c[f'eta_{family}']*r
            for k in range(klo,khi+1):
                tail=mp.exp(-z)*mp.fsum(z**l/mp.factorial(l) for l in range(2*k+kadd+1))
                leading=numerator/denominator if family=='BO' and k==3 else (0 if family=='REL' and k==2 else 1)
                result-=c[f'C_{family}_{2*k}']*(leading-tail)/r**(2*k)
        return result
    return value(R),mp.diff(value,R)
