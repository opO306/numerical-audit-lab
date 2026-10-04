"""Author static clarification checker. No producer/V2/physical execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re

FIELDS={'t','N','P','producer','rechecker','reason'}
INTEGER=re.compile(r'(?:0|[1-9][0-9]*)\Z',re.ASCII)
PRODUCERS=('NOT_STARTED','RESOLVED','UNPROVED','REFUSED','ERROR')
RECHECKERS=('NOT_RUN','ACCEPTED','REJECTED','NOT_PROVED','ERROR')
RELATIONS={
    ('RESOLVED','NOT_RUN'):[None],
    ('RESOLVED','ACCEPTED'):[None],
    ('RESOLVED','NOT_PROVED'):['RECHECK_UNPROVED'],
    ('RESOLVED','REJECTED'):['RECHECK_REJECTED'],
    ('RESOLVED','ERROR'):['PROGRAMMING_ANOMALY'],
    ('UNPROVED','NOT_RUN'):['ROUNDING_UNPROVED','RESOURCE_CAP'],
    ('REFUSED','NOT_RUN'):['SCHEMA_INVALID','BINDING_MISMATCH','POLICY_UNBOUND',
        'SINGULAR_SEPARATION','PHYSICAL_DOMAIN','RAW_UNREPRESENTABLE','OPPOSITE_RAW_UNREPRESENTABLE'],
    ('ERROR','NOT_RUN'):['PROGRAMMING_ANOMALY'],
}


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')


def validate_attempt(attempt,wire):
    if type(attempt) is not dict or set(attempt)!=FIELDS:
        return False
    for key in ('t','N','P'):
        value=attempt[key]
        if type(value) is not str or not INTEGER.fullmatch(value) or len(value)>4096:
            return False
    if attempt['N']=='0' or attempt['P']=='0' or (len(attempt['P'])==1 and attempt['P']<'8'):
        return False
    if type(attempt['producer']) is not str or type(attempt['rechecker']) is not str:
        return False
    reason=attempt['reason']
    if reason is not None and (type(reason) is not str or reason not in wire['reasons']):
        return False
    matches=[row for row in wire['attempt_tuple_contract']['compatibility_table']
             if (row['producer'],row['rechecker'])==(attempt['producer'],attempt['rechecker'])]
    return len(matches)==1 and reason in matches[0]['allowed_reasons']


def rolling_step(previous,attempt,wire):
    if type(previous) is not bytes or len(previous)!=32 or not validate_attempt(attempt,wire):
        raise ValueError('invalid attempt tuple or previous digest')
    return hashlib.sha256(previous+canonical(attempt)).digest()


def valid_failure_reason(reason,wire):
    return type(reason) is str and reason in wire['reasons']


def check_package(new,old):
    new,old=Path(new),Path(old)
    checks=[]
    def require(ok,label):
        if not ok:raise AssertionError(label)
        checks.append(label)
    load=lambda p:json.loads(p.read_text(encoding='ascii'))
    files=sorted(p.name for p in old.glob('*.json'))
    require(files==sorted(p.name for p in new.glob('*.json')),'package members unchanged')
    hashes={name:hashlib.sha256((new/name).read_bytes()).hexdigest() for name in files}
    prior_hashes={name:hashlib.sha256((old/name).read_bytes()).hexdigest() for name in files}
    parsed={name:load(new/name) for name in files}
    edges=[]
    for name in files:
        data=(new/name).read_bytes();obj=parsed[name]
        require(canonical(obj)==data,'canonical bytes: '+name)
        require((new/(name+'.sha256')).read_bytes()==(hashes[name]+'  '+name+'\n').encode(), 'sidecar: '+name)
        for key,value in obj.get('dependencies',{}).items():
            old_value=load(old/name)['dependencies'][key]
            targets=[f for f,h in prior_hashes.items() if h==old_value]
            if targets:
                target=targets[0]
                require(value==hashes[target],'dependency: '+name+' -> '+target)
                edges.append([name,target])
            else:require(value==old_value,'external dependency unchanged: '+name+' '+key)
    for name in ['constants.json','physical-domain.json']:
        require((new/name).read_bytes()==(old/name).read_bytes(),'byte-preserved: '+name)
        require((new/(name+'.sha256')).read_bytes()==(old/(name+'.sha256')).read_bytes(),'sidecar byte-preserved: '+name)
    w=parsed['proof-wire.json'];prior=load(old/'proof-wire.json')
    for key,value in prior.items():
        if key!='attempt_digest_rule':require(w[key]==value,'wire field unchanged: '+key)
    require(set(w)-set(prior)=={'attempt_tuple_contract'},'only attempt contract added')
    suffix='; attempt reason is required: canonical JSON null only for RESOLVED+NOT_RUN or RESOLVED+ACCEPTED; all other permitted tuples require the applicable non-null closed reason in attempt_tuple_contract; missing/undefined tuples are invalid; Failure.reason remains required non-null'
    require(w['attempt_digest_rule']==prior['attempt_digest_rule']+suffix,'digest rule narrowly clarified')
    require(w['attempt_tuple_contract']['exact_keys']==['t','N','P','producer','rechecker','reason'],'required reason key')
    rows=w['attempt_tuple_contract']['compatibility_table']
    require(len(rows)==25,'complete 25-row table')
    seen={}
    for row in rows:
        require(set(row)=={'producer','rechecker','allowed_reasons'},'closed compatibility row')
        pair=(row['producer'],row['rechecker'])
        require(pair not in seen,'unique compatibility pair')
        seen[pair]=row['allowed_reasons']
    require(seen=={(p,r):RELATIONS.get((p,r),[]) for p in PRODUCERS for r in RECHECKERS},'closed relation matches proposal')
    require(w['reasons']==prior['reasons'],'no new success reason')
    require(all(valid_failure_reason(v,w) for v in w['reasons']) and not valid_failure_reason(None,w),'Failure reason non-null')
    for name in ['finite-policy.json','acquisition-identity.json','status-composition.json','rechecker-lineage.json','semantic-bundle.json']:
        a,b=parsed[name].copy(),load(old/name)
        a.pop('dependencies');b.pop('dependencies')
        require(a==b,'only dependency identifiers changed: '+name)
    package=parsed['package-manifest.json'];old_package=load(old/'package-manifest.json')
    require(package['semantic_bundle_sha256']==hashes['semantic-bundle.json'],'manifest bundle identity')
    allowed={'dependencies','semantic_bundle_sha256','review_state','revision','historical_approved_antecedent',
             'implementation_may_start','runtime_activation_allowed','implementation'}
    require({k:v for k,v in package.items() if k not in allowed}==
            {k:v for k,v in old_package.items() if k not in allowed},'manifest unaffected fields preserved')
    require(package['review_state']=='ATTEMPT-REASON-NULL clarification / INDEPENDENT RECHECK PENDING','independent recheck pending')
    require(package['runtime_activation_allowed']=='false' and package['implementation_may_start']=='false','boundary continuation and activation disabled')
    require(package['revision']['id']=='ATTEMPT-REASON-NULL-2026-10-05','separate revision identifier')
    old_changed=[prior_hashes[n] for n in files if prior_hashes[n]!=hashes[n]]
    for name in files:
        current=(new/name).read_text(encoding='ascii')
        if name=='package-manifest.json':
            data=parsed[name].copy();data.pop('historical_approved_antecedent')
            current=canonical(data).decode('ascii')
        require(all(h not in current for h in old_changed),'no stale dependency hash: '+name)
    return {'schema':'C1B1_ATTEMPT_REASON_STATIC_CHECKS_V1','result':'PASS','level':'AUTHOR STATIC SPEC CHECKS ONLY',
            'checks':checks,'check_count':len(checks),'canonical_hashes':hashes,'dependency_edges':edges,
            'compatibility_pairs':25,'valid_status_pairs':len(RELATIONS),
            'null_success_pairs':[['RESOLVED','NOT_RUN'],['RESOLVED','ACCEPTED']],
            'Failure_schema_unchanged':True,'Failure_reason_nullable':False,
            'producer_or_V2_executed':False,'runtime_activation_allowed':False,
            'review_status':'INDEPENDENT RECHECK PENDING','J_status':'J_NOT_VERIFIED','certification':'NotCertified'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    result=check_package(root/'specs/c1b1-independent-impulse-v1-attempt-reason-null',root/'specs/c1b1-independent-impulse-v1')
    args.output.write_bytes((json.dumps(result,indent=2)+'\n').encode('ascii'))
    print('PASS:',result['check_count'],'static checks; 25 closed status pairs; Failure unchanged; producer/V2 not executed')
