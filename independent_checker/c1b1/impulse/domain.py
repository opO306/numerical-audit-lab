from fractions import Fraction as Q


def admit(q, spec):
    r2=sum((x*x for x in q),Q(0))
    if r2==0:return 'SINGULAR_SEPARATION'
    if r2<spec.r_min_squared:return 'PHYSICAL_DOMAIN'
    return None
