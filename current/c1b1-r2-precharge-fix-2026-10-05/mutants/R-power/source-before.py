"""Analytic dV/dR, separate from the value formula and primitive enclosure."""
from .interval import point, add, sub, mul, power


def derivative(terms,c):
    result=point(0)
    for term in terms.short:
        slope=sub(term.slope,mul(term.alpha,term.polynomial,c),c)
        result=add(result,mul(term.exponential,slope,c),c)
    for term in terms.long:
        first=mul(term.damping_slope,power(term.radius,-2*term.k,c),c)
        second=mul(mul(point(2*term.k),term.damping,c),power(term.radius,-2*term.k-1,c),c)
        result=sub(result,mul(term.coefficient,sub(first,second,c),c),c)
    return result
