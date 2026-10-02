"""Gate 2C.1: binary-aware certification feasibility, sealed before implementation.

python run_gate2c1.py --out reports/gate2c1-measured-2026-10-02
Uses existing frozen fixtures; never installs, imports, or edits gala or A.
"""
import argparse
import hashlib
import json
import math
import platform
import sys
from lab.gate2c1_artifacts import snapshot, save, encoded, forms_bits
import time
from pathlib import Path

from benchmarks.gate2a.henon_heiles import Binary64Stepper, OUT as LAB_OUT, STATE as LAB_STATE, structure
from benchmarks.gate2c1.binary_replay import BinaryReplay
from lab.gate2b_fixture import load
from lab.gate2c1_checks import BinBound, LATENT_OUT, OUTPUT, cross_check, exact_window, output_status, verify_seals
from lab.independence import loaded_a_modules, static_violations
from lab.v2_bound import rebase, step_forms, zero_forms
from run_gate2a import peak_rss_bytes

ROOT=Path(__file__).resolve().parent
MARKS=(10,100,1000,10000,50000,100000)


def remember_first(first,j,reason):
    return first if first is not None else {'step':j,'reason':reason}


def audit_orbit(name,n,deadline,evidence_dir=None):
    t0=time.perf_counter()
    rows=load(name+'_forward')
    t=BinaryReplay()
    initial=[rows[c][0] for c in range(4)]
    init=t.init(*initial)
    if evidence_dir:
        save(evidence_dir/'traces'/f'{name}_init.json',{'phase':'init','operations':t.trace('init',init),'v2_input_forms':forms_bits(zero_forms())})
    st=(initial[0],initial[1],init['vhx'],init['vhy'])
    bound=BinBound(t.init_structure,t.step_structure)
    bin_dead=lab_dead=None
    try:
        bound.init(init)
    except (ArithmeticError,ValueError,StopIteration,IndexError) as exc:
        bin_dead={'step':0,'reason':f'{type(exc).__name__}: {exc}'}
    lab=Binary64Stepper()
    lab_struct=structure()
    lst=dict(zip(LAB_STATE,initial))
    lf=zero_forms()
    first_bin=bin_dead
    first_cross=None
    counts={'PASS':0,'FAIL':0,'REFUSED':0}
    violations=[]
    raw_count=0
    worst_ratio=0.
    replay_first=None
    points=[]
    k=min(8,n)
    window_starts={0,n//2,n-k} if n<100000 else {0,50000,99992}
    kept={0:st}
    done=0
    abort=None
    refusal_ranges=[]
    last_refusal={}
    segment_prev_hash=None
    segments=[]
    segment_start=snapshot(0,st,lst,bound.forms,lf,first_bin,first_cross,bin_dead,lab_dead)
    segment_digest=hashlib.sha256()
    def record_refusal(kind,j,why):
        prior=last_refusal.get(kind)
        if prior is not None and prior['reason']==why and prior['end']==j-1:
            prior['end']=j
        else:
            entry={'kind':kind,'start':j,'end':j,'reason':why}
            refusal_ranges.append(entry)
            last_refusal[kind]=entry
    for j in range(1,n+1):
        if time.perf_counter()>=deadline:
            abort={'step':j,'reason':'COST_BUDGET (60 min wall)'}
            first_bin=remember_first(first_bin,j,abort['reason'])
            break
        try:
            trace_input_forms=forms_bits(bound.forms)
            regs=t.step(*st)
            if j==1 and evidence_dir:
                save(evidence_dir/'traces'/f'{name}_step1.json',{'phase':'step','operations':t.trace('step',regs),'v2_input_forms':trace_input_forms})
            lr=lab.step(lst)
        except (RuntimeError,ValueError,ArithmeticError) as exc:
            abort={'step':j,'reason':f'EXECUTION: {type(exc).__name__}: {exc}'}
            first_bin=remember_first(first_bin,j,abort['reason'])
            break
        a=[regs[s] for s in OUTPUT]
        b=[lr[LAB_OUT[s]] for s in LAB_STATE]
        for c,v in enumerate(a):
            if replay_first is None and v!=rows[c][j]:
                replay_first={'step':j,'component':c,'replay_bits':f'{v:016x}','fixture_bits':f'{rows[c][j]:016x}'}
        E=F=None
        if bin_dead is None:
            try:
                E=bound.step(regs)
            except (ArithmeticError,ValueError,StopIteration,IndexError) as exc:
                bin_dead={'step':j,'reason':f'{type(exc).__name__}: {exc}'}
        if lab_dead is None:
            try:
                forms=step_forms(lab_struct,lr,dict(zip(LAB_STATE,lf)))
                F=[forms[LAB_OUT[s]].rad() for s in LAB_STATE]
                lf,internal_F=rebase([forms[LAB_OUT[s]] for s in LAB_STATE])
                if any(not math.isfinite(v) or v<0 for v in F+internal_F):
                    lab_dead={'step':j,'reason':'nonfinite Lab bound'}
                    F=None
            except (ArithmeticError,ValueError,StopIteration,IndexError) as exc:
                lab_dead={'step':j,'reason':f'{type(exc).__name__}: {exc}'}
        v,why=output_status(a,E)
        if replay_first is not None:
            v,why='REFUSED','replay does not match frozen external execution'
        if v=='REFUSED':
            record_refusal('V2',j,why if bin_dead is None else bin_dead['reason'])
            first_bin=remember_first(first_bin,j,why if bin_dead is None else bin_dead['reason'])
        cross=cross_check(a,b,E,F)
        if cross['raw_enclosure_violations']:
            raw_count+=len(cross['raw_enclosure_violations'])
            if len(violations)<20:
                violations.append({'step':j,'components':cross['raw_enclosure_violations']})
        if replay_first is not None:
            cross['verdict'],cross['reason']='REFUSED','external execution replay mismatch'
        counts[cross['verdict']]+=1
        if cross['verdict']=='REFUSED':
            record_refusal('CROSS',j,cross['reason'])
            first_cross=remember_first(first_cross,j,cross['reason'])
        if cross.get('max_residual_over_bound') is not None:
            worst_ratio=max(worst_ratio,cross['max_residual_over_bound'])
        if j in MARKS or (first_bin and first_bin['step']==j) or (first_cross and first_cross['step']==j) or (bin_dead and bin_dead['step']==j) or (lab_dead and lab_dead['step']==j):
            points.append({'step':j,'external_bound':E,'lab_bound':F,'external_status':v,'external_reason':why,'cross':cross})
        segment_digest.update(encoded({'step':j,'bin':a,'lab':b,'E':[x.hex() for x in E] if E else None,'F':[x.hex() for x in F] if F else None,'v2':v,'cross':cross['verdict']}))
        st=tuple(regs[s] for s in LATENT_OUT)
        lst=dict(zip(LAB_STATE,b))
        if j in window_starts:
            kept[j]=st
        done=j
        if j%1000==0 or j==n:
            endpoint=snapshot(j,st,lst,bound.forms,lf,first_bin,first_cross,bin_dead,lab_dead)
            block={'start':segment_start,'end':endpoint,'previous_segment_sha256':segment_prev_hash,
                   'decision_digest':segment_digest.hexdigest(),'coverage':[segment_start['step']+1,j]}
            if evidence_dir:
                block_path=evidence_dir/'segments'/name/f'{j:06d}.json'
                segment_prev_hash=save(block_path,block)
                segments.append({'path':block_path.relative_to(evidence_dir).as_posix(),'sha256':segment_prev_hash,'coverage':block['coverage']})
            segment_start=endpoint
            segment_digest=hashlib.sha256()
        if j%1000==0:
            print(f'{name} step={j}/{n} wall={time.perf_counter()-t0:.1f}s first_refused={first_bin} cross={counts}',flush=True)
    windows={}
    for n0 in sorted(window_starts):
        if n0 not in kept or n0+k>done or time.perf_counter()>=deadline:
            windows[str(n0)]={'verdict':'REFUSED','reason':'window not measured or COST_BUDGET'}
        else:
            print(f'{name} exact local window n0={n0} length={k}',flush=True)
            try:
                result=exact_window(t,kept[n0],k)
                records=result.pop('records')
                if evidence_dir:
                    path=evidence_dir/'exact'/f'{name}_{n0}_8step.json'
                    result['artifact']={'path':path.relative_to(evidence_dir).as_posix(),'sha256':save(path,{'orbit':name,'n0':n0,'start_latent':[f'{v:016x}' for v in kept[n0]],'result':result.copy(),'records':records})}
                windows[str(n0)]=result
            except (ArithmeticError,ValueError,RuntimeError) as exc:
                windows[str(n0)]={'verdict':'REFUSED','reason':f'{type(exc).__name__}: {exc}'}
    d={'N':n,'steps_measured':done,'replay':{'label':'KNOWN_PREREQUISITE_NOT_BLIND_SUCCESS','first_mismatch':replay_first,'steps_checked':done},
       'first_refused':first_bin,'certified_prefix':max(0,min(done,(first_bin['step']-1 if first_bin else done))),
       'bin_bound_unavailable_from':bin_dead,'lab_bound_unavailable_from':lab_dead,'abort':abort,
       'cross':{'counts':counts,'first_refused':first_cross,'raw_enclosure_violation_count':raw_count,
                'violation_examples':violations,'max_residual_over_bound_finite':worst_ratio},
       'exact_local_windows':windows,'marks':points,'segments':segments,'refused_ranges':refusal_ranges}
    return d,time.perf_counter()-t0


def gate_verdict(orbits,n,independence):
    if independence['static_violations'] or independence['A_modules_loaded']:
        return 'FAIL'
    if any(o['cross']['raw_enclosure_violation_count'] or any(w.get('violations',0) for w in o['exact_local_windows'].values()) for o in orbits.values()):
        return 'FAIL'
    if any(o['steps_measured']!=n or o['replay']['first_mismatch'] is not None or o['abort'] or
           any(w.get('verdict')=='REFUSED' for w in o['exact_local_windows'].values()) for o in orbits.values()):
        return 'REFUSED'
    return 'PASS'


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--n',type=int,default=100000)
    ap.add_argument('--out',default='reports/gate2c1-measured-2026-10-02')
    args=ap.parse_args(argv)
    if not 1<=args.n<=100000:
        ap.error('--n must be in 1..100000')
    if args.n==100000 and not (ROOT/'audit/gate2c1/code_seal.json').exists():
        ap.error('full run requires committed code seal')
    out=Path(args.out)
    if not out.is_absolute():
        out=ROOT/out
    if (out/'gate2c1_report.json').exists():
        ap.error('output report already exists; use a new --out directory to preserve evidence')
    seal_failures=[]
    try:
        before=verify_seals()
    except (RuntimeError,OSError,ValueError) as exc:
        before={'inputs':'FAILED'}
        seal_failures.append({'phase':'before','reason':f'{type(exc).__name__}: {exc}'})
    t0=time.perf_counter()
    deadline=t0+3600
    det={'plan':'docs/GATE2C1_PLAN.md','seal':before,'N':args.n,
         'scope':'FULL_FROZEN_FORWARD_EXPERIMENT' if args.n==100000 else 'DEVELOPMENT_SHORT_RUN',
         'known_matching_replay':'post-diagnostic knowledge from Gate 2B; not blind or independent discovery',
         'certification_scope':'roundoff layer of same exact discrete map only',
         'independent_audit':'NOT_PERFORMED','seal_failures':seal_failures,'orbits':{}}
    costs={}
    if not seal_failures:
        for name in ('regular','chaotic'):
            det['orbits'][name],costs[name]=audit_orbit(name,args.n,deadline,out/'evidence')
        try:
            verify_seals()
        except (RuntimeError,OSError,ValueError) as exc:
            seal_failures.append({'phase':'after','reason':f'{type(exc).__name__}: {exc}'})
    det['independence']={'static_violations':static_violations(),'A_modules_loaded':loaded_a_modules()}
    det['gate_verdict']='FAIL' if seal_failures else gate_verdict(det['orbits'],args.n,det['independence'])
    reg=det['orbits'].get('regular',{}).get('certified_prefix',0)
    det['utility']='LONG_REGULAR_PREFIX' if reg>=17790 else 'LIMITED_HORIZON'
    digest=hashlib.sha256(json.dumps(det,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    report={'deterministic_digest':digest,'deterministic':det,'costs_seconds':costs,
            'total_wall_seconds':time.perf_counter()-t0,'peak_rss_bytes':peak_rss_bytes(),
            'machine':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()}}
    out.mkdir(parents=True,exist_ok=True)
    (out/'gate2c1_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(f"Gate 2C.1 {det['gate_verdict']} {det['utility']} digest={digest}",flush=True)
    return 0 if det['gate_verdict']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
