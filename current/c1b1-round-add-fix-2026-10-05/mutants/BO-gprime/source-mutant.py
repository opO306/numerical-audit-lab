"""Approved BO/REL/QED value terms, with explicit retarded branches."""
from dataclasses import dataclass
from .interval import point, add, sub, mul, power, reciprocal
from .exp_enclosure import exp_enclosure


@dataclass(frozen=True)
class ShortTerm:
    exponential: object
    polynomial: object
    slope: object
    alpha: object


@dataclass(frozen=True)
class LongTerm:
    coefficient: object
    k: int
    damping: object
    damping_slope: object
    radius: object


@dataclass(frozen=True)
class Terms:
    short: tuple
    long: tuple
    exp_orders: tuple


def polynomial(spec, family, j, r, c):
    p,derivative=point(0),point(0)
    first=-1 if family=='BO' else 0
    for i in range(first,3):
        a=spec.constants[f'a_{family}_{i}_{j}']
        p=add(p,mul(point(a),power(r,i,c),c),c)
        if i:
            derivative=add(derivative,mul(point(c.qmul(a,point(i).lo)),power(r,i-1,c),c),c)
    return p,derivative


def retardation(spec,r,c):
    numerator=denominator=point(1);np=dp=point(0)
    for m in range(1,7):
        if m<=5:
            a=spec.constants[f'RET_A_{m}']
            numerator=add(numerator,mul(point(a),power(r,m,c),c),c)
            np=add(np,mul(point(c.qmul(a,point(m).lo)),power(r,m-1,c),c),c)
        b=spec.constants[f'RET_B_{m}']
        denominator=add(denominator,mul(point(b),power(r,m,c),c),c)
        dp=add(dp,mul(point(c.qmul(b,point(m).lo)),power(r,m-1,c),c),c)
    g=mul(numerator,reciprocal(denominator,c),c)
    gp=mul(sub(mul(np,denominator,c),mul(numerator,dp,c),c),power(denominator,-2,c),c)
    return g,gp


def evaluate_terms(spec,r,bits,order_max,c):
    short,long,orders=[],[],[]
    for family in ('BO','REL','QED'):
        for j in (1,2):
            alpha=spec.constants[f'alpha_{family}_{j}']
            e,n,_=exp_enclosure(mul(point(alpha),r,c),bits,order_max,c)
            p,pp=polynomial(spec,family,j,r,c)
            short.append(ShortTerm(e,p,pp,point(alpha)))
            orders.append((f'{family}_ALPHA_{j}',n))
    g,gp=retardation(spec,r,c)
    for family,klo,khi,kadd in [('BO',3,8,1),('REL',2,4,0),('QED',3,4,0)]:
        eta=point(spec.constants[f'eta_{family}']);x=mul(eta,r,c)
        e,n,_=exp_enclosure(x,bits,order_max,c);orders.append((f'{family}_ETA',n))
        for k in range(klo,khi+1):
            last=2*k+kadd;term=series=point(1)
            for l in range(1,last+1):
                term=mul(mul(term,x,c),point(c.fraction(1,l)),c);series=add(series,term,c)
            tail=mul(e,series,c)
            slope=mul(mul(eta,e,c),term,c)
            if family=='BO' and k==3:
                damping=sub(g,tail,c);slope=slope
            elif family=='REL' and k==2:
                damping=sub(point(0),tail,c)
            else:
                damping=sub(point(1),tail,c)
            long.append(LongTerm(point(spec.constants[f'C_{family}_{2*k}']),k,damping,slope,r))
    return Terms(tuple(short),tuple(long),tuple(orders))


def value(terms,c):
    result=point(0)
    for term in terms.short:
        result=add(result,mul(term.exponential,term.polynomial,c),c)
    for term in terms.long:
        result=sub(result,mul(mul(term.coefficient,term.damping,c),power(term.radius,-2*term.k,c),c),c)
    return result
