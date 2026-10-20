"""Univariate polynomial computations over SymPy exact domains."""
from graph_research._lazy import sympy as sp


def _poly(f):
    if isinstance(f, sp.Poly):
        return f
    expression = sp.sympify(f)
    variables = sorted(expression.free_symbols, key=str)
    if len(variables) != 1:
        raise ValueError("Provide a univariate SymPy expression or Poly")
    return sp.Poly(expression, variables[0])


def num_chg(coefs):
    signs = [sp.sign(value) for value in coefs if value != 0]
    if any(s not in (-1, 1) for s in signs):
        raise ValueError("Coefficient signs must be decidable real signs")
    return sum(a != b for a, b in zip(signs, signs[1:]))


def num_chg_of_polynomail(f):
    return num_chg(_poly(f).all_coeffs())


def strum_seq(f):
    p = _poly(f)
    return [sp.Poly(value, p.gen) for value in sp.sturm(p.as_expr(), p.gen)]


def num_realroots(f, a, b):
    """Distinct real roots in the CLOSED interval [a,b], including endpoints."""
    return int(_poly(f).sqf_part().count_roots(a, b))


def find_all_roots(f, a, b, eps=1e-10):
    if eps <= 0 or a > b:
        raise ValueError("Invalid interval or accuracy")
    p = _poly(f).sqf_part()
    result = []
    for interval, multiplicity in sp.polys.polytools.intervals(p, eps=sp.Rational(str(eps)), inf=a, sup=b):
        left, right = interval
        result.append(float((left+right)/2))
    return sorted(result)
