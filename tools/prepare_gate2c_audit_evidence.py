"""Read-only producer export for the Gate 2C independent audit.

NOT an independent checker. No audit verdicts or horizon recomputation.
Executes only init + one binary step and eight exact steps at n0=0 per orbit.
Existing reports supply horizon/cross summaries; missing historical latent checkpoints stay missing.
"""
import argparse
import hashlib
import json
import struct
import sys
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from benchmarks.gate2c.binary_replay import BinaryReplay
from lab.gate2b_fixture import load, fval
from lab.gate2c_checks import BinBound, LATENT_OUT, OUTPUT, verify_seals
from lab.v2_bound import zero_forms


def write_json(out,name,data):
    p=out/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())


def qrecord(q):
    q=Fraction(q)
    return {'numerator_hex':hex(q.numerator),'denominator_hex':hex(q.denominator)}


def bits(v):
    return struct.unpack('>Q',struct.pack('>d',v))[0]


def forms_record(forms):
    return [{'coef_bits':[f'{bits(c):016x}' for c in f.coef],
             'box_bits':f'{bits(f.box):016x}'} for f in forms]


def trace_record(kind,structure,regs,input_forms):
    dst=[row[1] for row in structure]
    if len(dst)!=len(set(dst)):
        raise RuntimeError('export supports this frozen unique-destination graph only')
    rows=[]
    for i,(op,name,args,lit) in enumerate(structure):
        rows.append({'index':i,'op':op,'dst':name,'operands':list(args),'literal':lit,
                     'operand_bits':[f'{regs[a]:016x}' for a in args],
                     'result_bits':f'{regs[name]:016x}'})
    return {'schema':'gate2c-operation-trace-producer-v1','kind':kind,
            'label':'PRODUCER_OBSERVATION_NOT_INDEPENDENT_REFERENCE',
            'V2_structure':[list(row) for row in structure],
            'V2_registers_bits':{k:f'{v:016x}' for k,v in regs.items()},
            'V2_input_forms':input_forms,'operations':rows}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True)
    a=ap.parse_args(argv)
    out=Path(a.out).resolve()
    if out.exists():
        ap.error('use a new evidence output directory; do not overwrite observations')
    verify_seals()
    result_path=ROOT/'reports/gate2c-home-pc-2026-10-01-verified/gate2c_report.json'
    report=json.loads(result_path.read_text(encoding='utf-8'))
    actual=hashlib.sha256(json.dumps(report['deterministic'],sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if actual!='a796c32a5be379c2cdfdd93757963ed92d981bf83dbd4c5e784d45c863fa3acc':
        raise RuntimeError('frozen report digest differs')
    out.mkdir(parents=True)
    sys.set_int_max_str_digits(0)  # existing exact VM serializes rational registers as decimal text
    for orbit in ('regular','chaotic'):
        rows=load(orbit+'_forward')
        initial=[rows[c][0] for c in range(4)]
        t=BinaryReplay()
        regs=t.init(*initial)
        b=BinBound(t.init_structure,t.step_structure)
        write_json(out,f'traces/{orbit}_init.json',trace_record('init',t.init_structure,regs,
                   dict(zip(('x','y','vx','vy'),forms_record(zero_forms())))))
        b.init(regs)
        state=(initial[0],initial[1],regs['vhx'],regs['vhy'])
        input_forms=dict(zip(('x','y','vhx','vhy'),forms_record(b.forms)))
        sr=t.step(*state)
        record=trace_record('step_1',t.step_structure,sr,input_forms)
        record['producer_output_bound_bits']=[f'{bits(v):016x}' for v in b.step(sr)]
        record['fixture_output_bits']=[f'{rows[c][1]:016x}' for c in range(4)]
        write_json(out,f'traces/{orbit}_step_1.json',record)
        exact_t=BinaryReplay(exact=True)
        er=exact_t.init(*(Fraction(fval(v)) for v in initial))
        es=(Fraction(fval(initial[0])),Fraction(fval(initial[1])),er['vhx'],er['vhy'])
        exact_rows=[]
        for step in range(1,9):
            eo=exact_t.step(*es)
            exact_rows.append({'local_step':step,'output':{k:qrecord(eo[k]) for k in OUTPUT},
                               'latent':{k:qrecord(eo[k]) for k in LATENT_OUT}})
            es=tuple(eo[k] for k in LATENT_OUT)
        write_json(out,f'exact/{orbit}_n0_0_8step_producer.json',
                   {'schema':'gate2c-exact-vm-producer-fixture-v1',
                    'label':'EXISTING_VM_EXACT_OUTPUT_NOT_INDEPENDENT_REFERENCE',
                    'n0':0,'initial_full_state_bits':[f'{v:016x}' for v in initial],
                    'latent_start_bits':[f'{v:016x}' for v in state],
                    'scope':'n0=0 historical local window seed; no intermediate/end checkpoint reconstruction',
                    'rows':exact_rows})
        anchors=[]
        for n0 in (0,50000,99992):
            anchors.append({'n0':n0,'full_state_bits':[f'{rows[c][n0]:016x}' for c in range(4)],
                            'full_state_exact':[qrecord(Fraction(fval(rows[c][n0]))) for c in range(4)],
                            'historical_latent_start_bits':[f'{v:016x}' for v in state] if n0==0 else None,
                            'latent_availability':'AVAILABLE_INITIAL' if n0==0 else 'NOT_PERSISTED_REQUIRES_AUDITOR_RECONSTRUCTION'})
        write_json(out,f'anchors/{orbit}_frozen_full_state_anchors.json',anchors)
        o=report['deterministic']['orbits'][orbit]
        write_json(out,f'logs/{orbit}_horizon_saved_report.json',
                   {'label':'EXTRACTED_HISTORICAL_REPORT_NOT_FRESH_RECALCULATION',
                    'source_report_raw_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    'claimed_certified_prefix':o['certified_prefix'],'claimed_first_refused':o['first_refused'],
                    'bound_unavailable_from':o['bin_bound_unavailable_from'],
                    'saved_marks':o['marks'],'per_step_propagation_log_available':False,
                    'boundary_previous_step_forms_available':False})
        write_json(out,f'logs/{orbit}_cross_saved_report.json',
                   {'label':'EXTRACTED_HISTORICAL_REPORT_NOT_FRESH_RECALCULATION',
                    'cross_summary':o['cross'],'saved_marks':o['marks'],
                    'boundary_previous_step_forms_available':False})
    verify_seals()
    print('Prepared: 4 operation traces, 2 exact 8-step producer fixtures, 6 full-state anchors, historical report extracts.')
    print('No independent checker, no new audit verdict, no horizon recomputation, no 100000-step execution.')
    return 0


if __name__=='__main__':
    sys.exit(main())
