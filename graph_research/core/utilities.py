"""General helpers adapted from MyTools/MyUtility, with explicit inputs."""
import functools
import itertools
import random
import re
import string
import numpy as np
from graph_research._lazy import sympy as sp


def var_list(name, size): return list(sp.symbols(f"{name}0:{size}"))
def shortLex(a, b): return (len(a), a) <= (len(b), b)
def quickSort(values): return sorted(values, key=lambda value: (len(value), value))


def Majorization_Comp(a, b):
    if len(a) != len(b): return "lNon"
    a, b = sorted(a, reverse=True), sorted(b, reverse=True)
    comparisons = [sum(a[:k]) >= sum(b[:k]) for k in range(1, len(a)+1)]
    return "Non" if len(set(comparisons)) > 1 else (comparisons[0] if comparisons else True)


def subd_list(values, sizes):
    if any(type(s) is not int or s < 0 for s in sizes) or sum(sizes) > len(values):
        raise ValueError("Invalid block sizes")
    blocks = []
    for size in sizes:
        blocks.append(values[:size]); del values[:size]
    return blocks


def multiple_replace(mapping, text):
    if not mapping: return text
    pattern = re.compile("|".join(re.escape(key) for key in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match.group()], text)


def Gensubs(expression, substitutions):
    return expression.subs(substitutions, simultaneous=True)


def round_with_eps(value, eps=1e-10):
    return round(value) if abs(round(value)-value) <= eps else value


def matrix_round(matrix, ndigits=8, eps=1e-10):
    def rounded(value):
        candidate = round(float(value), ndigits)
        if abs(candidate-float(value)) > eps: return value
        return int(candidate) if candidate.is_integer() else candidate
    if isinstance(matrix, sp.MatrixBase): return matrix.applyfunc(rounded)
    return np.vectorize(rounded)(np.asarray(matrix))


def map_round(values, ndigits=8, eps=1e-10):
    def rounded(value):
        candidate = round(float(value),ndigits)
        return int(candidate) if candidate.is_integer() else candidate
    if isinstance(values,sp.MatrixBase): return values.applyfunc(rounded)
    return np.vectorize(rounded)(np.asarray(values))


def random_string(length, seed=None):
    return "".join(random.Random(seed).sample(string.ascii_lowercase+string.digits, length))


def reshape(values, dims, flat=True, fil=0):
    values = np.asarray(values).ravel().tolist() if flat else list(values)
    size = int(np.prod(dims))
    values = (values+[fil]*size)[:size]
    return np.array(values).reshape(dims).tolist()


def GroupBy(values, method):
    result = {}
    for value in values: result.setdefault(method(value), []).append(value)
    return list(result.values())


def seq_iter(n, f, x0):
    """Return the nth iterate, matching the original Sage helper."""
    value = x0
    for _ in range(max(0,n)): value = f(value)
    return value


def poly2sr(coefficients, variable=None):
    x = sp.Symbol("x") if variable is None else variable
    return sum(value*x**i for i, value in enumerate(coefficients))


def Expr_add(values): return "".join(map(str, values))


def tab2tex(table):
    """Return LaTeX text; does not read/write the system clipboard."""
    return sp.latex(sp.Matrix(table))


def parse_latex_matrix(text):
    body = re.sub(r"\\(?:begin|end)\{(?:array|matrix|pmatrix|bmatrix)\}(?:\{[clr|]+\})?", "", text)
    rows = [[sp.sympify(cell.strip()) for cell in row.split("&")]
            for row in body.strip().split(r"\\") if row.strip()]
    return sp.Matrix(rows)


def power_operator(function, n):
    def composed(value):
        for _ in range(n): value = function(value)
        return value
    return composed


def diff_op(function): return lambda x: function(x+1)-function(x)
