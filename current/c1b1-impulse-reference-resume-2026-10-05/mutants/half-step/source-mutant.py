"""Independent point reference producer. Runtime entry is fail-closed."""
from dataclasses import dataclass
from fractions import Fraction as Q
from .contracts import validate_input, ContractFailure
from .domain import admit
from .identity import bind
from .spec import load_spec
from .interval import point, neg, mul, reciprocal
from .sqrt_enclosure import sqrt_enclosure
from .potential import evaluate_terms
from .derivative import derivative
from .rounding import decide_scaled
from .resource import ResourceLimit
from .wire import canonical_bytes, decimal, WireFailure, HASH_RE
from .certificate import construct
from .attempt import INITIAL_DIGEST, append_attempt


@dataclass(frozen=True)
class PrivateResult:
    layers: dict
    raw: tuple | None = None
    opposite: tuple | None = None
    certificate: bytes | None = None
    failure: bytes | None = None
    scaled_intervals: tuple | None = None
    account: dict | None = None


def layers(producer='NOT_STARTED'):
    return {'producer':producer,'rechecker':'NOT_RUN','executor_comparison':'NOT_RUN',
            'arithmetic':'NOT_RUN','publication':'NOT_PUBLISHED','execution':'STOP'}


def failure(reason,phase,kind=None,binding=None,spec_hash=None,producer='REFUSED',attempt_digest=None):
    wire=load_spec().wire
    if type(reason) is not str or reason not in wire['reasons'] or phase not in wire['phases']:
        raise ValueError('invalid failure reason/phase')
    resource=reason in ('RESOURCE_CAP','ARTIFACT_LIMIT','HOST_SERIALIZATION_LIMIT')
    if (resource and kind not in wire['resource_kinds']) or (not resource and kind is not None):
        raise ValueError('invalid failure resource kind')
    if producer not in ('NOT_STARTED','RESOLVED','UNPROVED','REFUSED','ERROR'):
        raise ValueError('invalid failure producer')
    state=layers(producer);b=binding or {}
    record={'schema':'LAB_C1B1_IMPULSE_FAILURE_V1','status':state,'phase':phase,'reason':reason,
            'resource_kind':kind,'spec_sha256':spec_hash,'state_sha256':b.get('full_state_sha256'),
            'occurrence_sha256':b.get('occurrence_sha256'),'budget_sha256':b.get('budget_sha256'),
            'attempt_count':None,'attempt_digest':attempt_digest}
    for key in ('spec_sha256','state_sha256','occurrence_sha256','budget_sha256','attempt_digest'):
        v=record[key]
        if v is not None and (type(v) is not str or not HASH_RE.fullmatch(v)):
            raise ValueError('invalid failure hash')
    return PrivateResult(state,failure=canonical_bytes(record,4096))


def decide_vector(intervals):
    if len(intervals)!=3:raise ValueError('three lanes required')
    decisions=tuple(decide_scaled(x) for x in intervals)
    for reason in ['RAW_UNREPRESENTABLE','OPPOSITE_RAW_UNREPRESENTABLE','ROUNDING_UNPROVED']:
        if any(d.reason==reason for d in decisions):return None,reason
    return tuple(d.raw for d in decisions),None


def opposite_vector(raw):
    return tuple(-v for v in raw)


def check_refinements(old,new):
    for a,b in zip(old,new):
        if max(a.lo,b.lo)>min(a.hi,b.hi):
            raise ValueError('conflicting sound enclosures')
        da,db=decide_scaled(a),decide_scaled(b)
        if da.raw is not None and db.raw is not None and da.raw!=db.raw:
            raise ValueError('conflicting raw claims')


def prepared(data):
    spec=load_spec();parsed=validate_input(data,spec);binding=bind(parsed.obj,spec)
    reason=admit(parsed.q,spec)
    return spec,parsed,binding,reason


def produce(data):
    """No active numeric instance/worker is registered by this implementation."""
    try:
        spec,parsed,binding,reason=prepared(data)
        if reason:return failure(reason,'PHYSICAL_DOMAIN',binding=binding,spec_hash=spec.sha256)
        return failure('POLICY_UNBOUND','POLICY',binding=binding,spec_hash=spec.sha256)
    except ContractFailure as err:return failure(err.reason,err.phase,err.kind)
    except Exception:return failure('PROGRAMMING_ANOMALY','BINDING',producer='ERROR')


def evaluate_reference(data,policy):
    """AUTHOR REFERENCE EVALUATION ONLY; produces no public proof/activation.

    Controls must match the supplied synthetic Budget payload, whose hashes
    are data identities only. No approval registry or capture authenticity is
    asserted. This method is deliberately separate from produce().
    """
    binding=None;spec_hash=None;resolved=False
    digest=INITIAL_DIGEST;active_attempt=None
    try:
        spec,parsed,binding,reason=prepared(data);spec_hash=spec.sha256
        if reason:return failure(reason,'PHYSICAL_DOMAIN',binding=binding,spec_hash=spec_hash)
        if any(parsed.budget[k]!=v for k,v in vars(policy).items()):
            return failure('BINDING_MISMATCH','POLICY',binding=binding,spec_hash=spec_hash)
        c=policy.account();old=None
        r2=sum((x*x for x in parsed.q),Q(0)) # Fixed signed96/FX48 input bound.
        for t,n,p in policy.attempts():
            active_attempt=(t,n,p)
            radius=sqrt_enclosure(r2,n,c)
            reason='ROUNDING_UNPROVED';scaled=None
            if radius.lo>0:
                terms=evaluate_terms(spec,radius,p,policy.exp_order_max,c)
                vp=derivative(terms,c)
                force_over_r=mul(neg(vp),reciprocal(radius,c),c)
                scaled=tuple(point(0) if q==0 else
                    mul(mul(force_over_r,point(q),c),point(Q(40*(1<<80))),c) for q in parsed.q)
                if old is not None:check_refinements(old,scaled)
                old=scaled
                raw,reason=decide_vector(scaled)
            else:raw=None
            state='RESOLVED' if reason is None else ('UNPROVED' if reason=='ROUNDING_UNPROVED' else 'REFUSED')
            digest=append_attempt(digest,{'t':decimal(t),'N':decimal(n),'P':decimal(p),
                'producer':state,'rechecker':'NOT_RUN','reason':reason})
            active_attempt=None
            if reason in ['RAW_UNREPRESENTABLE','OPPOSITE_RAW_UNREPRESENTABLE']:
                return failure(reason,'COMPUTE',binding=binding,spec_hash=spec_hash,attempt_digest=digest.hex())
            if raw is not None:
                resolved=True
                cert=construct(spec,binding,raw,radius,n,p,t,t+1,digest.hex(),policy,c,parsed.q_raw)
                candidate=canonical_bytes(cert,policy.private_certificate_bytes)
                # Ensure a complete artifact could fit; no artifact is published.
                canonical_bytes({'schema':'LAB_C1B1_IMPULSE_ARTIFACT_V1','input':parsed.obj,
                    'certificate':cert,'status':layers('RESOLVED'),'publication_kind':'POINT_PROOF'})
                return PrivateResult(layers('RESOLVED'),raw,opposite_vector(raw),candidate,None,scaled,
                    {'mathematical_work':c.work,'operations':c.operations,'peak_integer_bits':c.peak_integer_bits,
                     'predicted_live_bytes':c.predicted_live_bytes,'peak_temporary_bytes':c.peak_temporary_bytes,
                     'allocation_basis':'AUTHOR_FIXTURE_MODEL_UNVALIDATED'})
        return failure('ROUNDING_UNPROVED','COMPUTE',binding=binding,spec_hash=spec_hash,
                       producer='UNPROVED',attempt_digest=digest.hex())
    except ContractFailure as err:return failure(err.reason,err.phase,err.kind)
    except ResourceLimit as err:
        if active_attempt is not None:
            t,n,p=active_attempt
            digest=append_attempt(digest,{'t':decimal(t),'N':decimal(n),'P':decimal(p),
                'producer':'UNPROVED','rechecker':'NOT_RUN','reason':'RESOURCE_CAP'})
        return failure('RESOURCE_CAP','PUBLICATION' if resolved else 'COMPUTE',err.kind,binding,spec_hash,
                       'RESOLVED' if resolved else 'UNPROVED',digest.hex())
    except WireFailure as err:
        return failure(err.reason,'PUBLICATION' if resolved else 'COMPUTE',err.kind,binding,spec_hash,
                       'RESOLVED' if resolved else 'UNPROVED',digest.hex())
    except MemoryError:
        return failure('RESOURCE_CAP','COMPUTE','HARD_MEMORY',binding,spec_hash,'UNPROVED',digest.hex())
    except Exception:
        return failure('PROGRAMMING_ANOMALY','COMPUTE',binding=binding,spec_hash=spec_hash,
                       producer='ERROR',attempt_digest=digest.hex())
