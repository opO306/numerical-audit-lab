"""Compact private reconstruction candidate; never a rechecked publication."""
import hashlib
from pathlib import Path
from fractions import Fraction as Q
from .wire import canonical_bytes, decimal
from .resource import ResourceLimit


def source_identity():
    # A multifile source identity is the hash of this exact sorted inventory.
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(Path(__file__).parent.glob('*.py'))}
    return hashlib.sha256(canonical_bytes(files)).hexdigest()


def construct(spec,binding,raw,radius,n,p,t,count,attempt_digest,policy,c,q_raw):
    if n>policy.legacy_sqrt_bits_max or p>policy.legacy_work_bits_max:
        raise ResourceLimit('BIT')
    guard=c.qadd(radius.hi,c.fraction(1,c.shift(1,n)))
    plan=[]
    for rate_id in spec.wire['rate_order']:
        if rate_id.endswith('_ETA'):
            key='eta_'+rate_id[:-4]
        else:
            family,_,idx=rate_id.split('_');key=f'alpha_{family}_{idx}'
        rate=spec.constants[key]
        basis=c.qadd(c.qmul(Q(4),c.qmul(rate,guard)),Q(1))
        floor,rem=c.divmod(basis.numerator,basis.denominator)
        ceiling=c.add(floor,int(rem!=0))
        # Compare before constructing the potentially large scheduled order.
        if ceiling>policy.legacy_order_max >> t:
            raise ResourceLimit('ORDER')
        order=c.shift(ceiling,t)
        plan.append({'rate_id':rate_id,'rate':{'n':decimal(rate.numerator),'d':decimal(rate.denominator)},
                     'mode':'FULL','order':decimal(order)})
    cert={'schema':'LAB_C1B1_IMPULSE_CERT_V1','spec_sha256':spec.sha256,'binding':binding,
          'producer_source_sha256':source_identity(),'rechecker_source_sha256':spec.rechecker_sha256,
          'method':'LAB_POINT_PRODUCER_V1_AND_PINNED_V2','raw_J':[decimal(x) for x in raw],
          'proof':{'sqrt_bits':decimal(n),'work_bits':decimal(p),'exp_plan':plan,
                   'lane_kinds':['EXACT_ZERO_AXIS' if q==0 else 'NONLINEAR_V2' for q in q_raw]},
          'attempt_count':decimal(count),'attempt_digest':attempt_digest}
    return cert
