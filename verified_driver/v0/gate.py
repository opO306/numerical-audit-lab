"""Strict authority predicate over controller-bound fresh Runtime Trace evidence."""
import os
from pathlib import Path
from .model import CandidateState, GateDecision, GENESIS_BITS, HARNESS_SHA, canonical_bytes, content_id, digest_bytes, strict_json

APPROVED_RT_PINSET_SHA='c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3'
STAGES=('acquisition','derivation','independent_check')

def file_bytes(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>1048576: raise ValueError('bounded nonaliased evidence required')
    return path.read_bytes()

def file_json(path): return strict_json(file_bytes(path))

def file_sha(path):
    import hashlib
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def source_snapshot(root):
    root=Path(root).resolve(); runtime={}
    for base,dirs,files in os.walk(root/'runtime_trace'):
        dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
        for name in files:
            if name.endswith('.py'):
                path=Path(base)/name; runtime[str(path.relative_to(root))]=file_sha(path)
    for name in ('lab/v2_bound.py','independent_checker/oracle.py'): runtime[name]=file_sha(root/name)
    driver={str(p.relative_to(root)):file_sha(p) for p in (root/'verified_driver').glob('*.py')}
    driver.update({str(p.relative_to(root)):file_sha(p) for p in (root/'verified_driver/v0').glob('*.py')})
    return {'runtime':runtime,'driver':driver}

def candidate_from_evidence(transaction_id,predecessor_id,evidence_dir):
    evidence=Path(evidence_dir).resolve()
    binding=file_bytes(evidence/'driver_binding.json')
    parsed=strict_json(binding)
    if parsed.get('transaction_id')!=transaction_id or parsed.get('predecessor_id')!=predecessor_id or parsed.get('evidence_dir')!=str(evidence):
        raise ValueError('candidate transaction/run locator binding')
    harness=file_json(evidence/'capture/harness_output.json')
    return CandidateState(transaction_id,predecessor_id,str(evidence),tuple(harness['output_bits']),binding)

def _evaluate(candidate,predecessor,repo_root):
    root=Path(repo_root).resolve(); evidence=Path(candidate.evidence_dir).resolve()
    binding=strict_json(candidate.binding_bytes)
    if file_bytes(evidence/'driver_binding.json')!=candidate.binding_bytes: raise ValueError('controller binding changed')
    if binding.get('schema')!='DRIVER_V0_RUN_BINDING_V1': raise ValueError('controller run binding required')
    if binding.get('transaction_id')!=candidate.transaction_id or binding.get('predecessor_id')!=candidate.predecessor_id or binding.get('evidence_dir')!=str(evidence):
        raise ValueError('same candidate transaction required')
    if predecessor.generation!=0 or predecessor.state_bits!=GENESIS_BITS or predecessor.source_binding!=HARNESS_SHA:
        raise ValueError('V0 supports regular genesis predecessor only')
    if predecessor.content_hash!=candidate.predecessor_id or binding.get('predecessor_bits')!=list(predecessor.state_bits):
        raise ValueError('certified predecessor/input binding')
    source=source_snapshot(root)
    if binding.get('source_start')!=source: raise ValueError('source changed during transaction')
    pins_path=evidence/'integration_source_pinset.json'; pins=file_json(pins_path)
    pin_sha=file_sha(pins_path)
    if pin_sha!=APPROVED_RT_PINSET_SHA or pins!=source['runtime'] or pins.get('runtime_trace/harness.py')!=HARNESS_SHA:
        raise ValueError('approved Runtime Trace source/harness binding')
    run=file_json(evidence/'run_result.json'); fresh=file_json(evidence/'fresh_checker_report.json')
    completion=file_json(evidence/'derived/completion.json'); harness=file_json(evidence/'capture/harness_output.json')
    if binding.get('fresh_report_sha256')!=file_sha(evidence/'fresh_checker_report.json') or binding.get('run_result_sha256')!=file_sha(evidence/'run_result.json') or binding.get('observed_report')!=fresh:
        raise ValueError('fresh controller-observed checker report mismatch')
    n=binding.get('requested_steps')
    if type(n) is not int or not 1<=n<=100: raise ValueError('strict supported segment request')
    for report in (run,fresh,completion):
        if report.get('verdict')!='CHECKER_PASS' or type(report.get('requested_steps')) is not int or type(report.get('checked_steps')) is not int or report['requested_steps']!=n or report['checked_steps']!=n or report.get('requested_complete') is not True:
            raise ValueError('fresh complete independent verification required')
        if report.get('init_to_step1')!='UNTRACED' or report.get('post_terminal_frontier')!='UNTRACED' or report.get('formal_certification') is not False:
            raise ValueError('retained Runtime Trace boundary required')
    digest=completion.get('completion_sha256')
    body={k:v for k,v in completion.items() if k!='completion_sha256'}
    if digest!=content_id(body) or run.get('completion_sha256')!=digest or fresh.get('completion_sha256')!=digest:
        raise ValueError('checked completion digest mismatch')
    if run.get('integration_source_pinset_sha256')!=pin_sha: raise ValueError('run source receipt mismatch')
    if harness.get('orbit')!='regular' or type(harness.get('n_steps')) is not int or harness['n_steps']!=n or harness.get('dt_bits')!='0x3f90000000000000':
        raise ValueError('approved regular input/harness binding')
    endpoints=completion.get('final_endpoint',[]); bits=[]
    for component,offset in [('q',0),('q',8),('full_v',0),('full_v',8)]:
        matches=[x for x in endpoints if x.get('component')==component and type(x.get('byte_offset')) is int and x['byte_offset']==offset]
        if len(matches)!=1: raise ValueError('unique checked terminal lane required')
        item=matches[0]
        if item.get('acquisition_id')!=completion.get('acquisition_id') or item.get('occurrence')!='step'+str(n):
            raise ValueError('same dynamic checked terminal required')
        bits.append(item['center_bits'])
    if tuple(bits)!=candidate.state_bits or harness.get('output_bits')!=bits:
        raise ValueError('candidate bytes differ from checked terminal output')
    hashes=run.get('stage_receipts')
    if not isinstance(hashes,list) or len(hashes)!=3: raise ValueError('all resource receipts required')
    for stage,want,module in zip(STAGES,hashes,('acquire','producer','checker')):
        path=evidence/stage/'execution.json'; receipt=file_json(path)
        if file_sha(path)!=want or receipt.get('verdict')!='EXECUTED' or receipt.get('resource_failure') is not None or type(receipt.get('return_code')) is not int or receipt['return_code']!=0:
            raise ValueError('successful exact resource receipt required')
        command=receipt.get('command',[])
        if command[1:3]!=['-m','runtime_trace.regular_nstep.'+module] or receipt.get('cwd')!=str(root):
            raise ValueError('approved stage invocation binding')
        if stage=='independent_check':
            if '--report' not in command or command[command.index('--report')+1]!=str(evidence/'fresh_checker_report.json'):
                raise ValueError('fresh same-transaction independent checker required')
        for flag,want_path in ([('--out',evidence/'capture')] if stage=='acquisition' else
            [('--capture',evidence/'capture'),('--root',root)]+([('--out',evidence/'derived')] if stage=='derivation' else [('--derived',evidence/'derived')])):
            if flag not in command or command[command.index(flag)+1]!=str(want_path): raise ValueError('same candidate stage locator required')
    acceptance={'schema':'DRIVER_V0_ACCEPTANCE_V1','verdict':'ACCEPT','transaction_id':candidate.transaction_id,
        'predecessor_id':candidate.predecessor_id,'candidate_id':candidate.content_hash,
        'controller_binding_sha256':digest_bytes(candidate.binding_bytes),'source_pinset_sha256':pin_sha,
        'completion_sha256':digest,'acquisition_id':completion['acquisition_id'],
        'requested_steps':n,'checked_steps':n,'requested_complete':True,'output_bits':bits,
        'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED','formal_certification':False}
    return GateDecision('ACCEPT','exact fresh candidate accepted',canonical_bytes(acceptance))

def evaluate_candidate(candidate,predecessor,repo_root):
    try: return _evaluate(candidate,predecessor,repo_root)
    except (ValueError,OSError,KeyError,TypeError,IndexError) as exc: return GateDecision('REFUSE',str(exc))
