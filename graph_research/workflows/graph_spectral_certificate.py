"""Exact edge-list bounds; no NumPy, eigensolver or polynomial solver needed.

For symmetric nonnegative adjacency A and positive x, Rayleigh gives a lower
bound and Collatz gives an upper bound. Fractions certify the stored vector,
not a claimed convergence tolerance or an approximate eigenvalue.
"""
from fractions import Fraction
import math
import hashlib

MAX_ORDER = 128
MAX_EDGES = 1024
POLYNOMIAL_ORDER = 12


def edge_list_digest(n, edges):
    canonical = sorted(tuple(sorted(edge)) for edge in edges)
    text = str(n)+';'+';'.join(f'{u},{v}' for u, v in canonical)
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def adjacency_bounds(n, edges, vector):
    """Reconstruct integer A*x from raw edges using exact rational arithmetic."""
    if type(n) is not int or not 2 <= n <= MAX_ORDER or not isinstance(edges, list) or not 1 <= len(edges) <= MAX_EDGES:
        raise ValueError('Adjacency certificate size outside supported range')
    if not isinstance(vector, list) or len(vector) != n:
        raise ValueError('Certificate vector must match vertices 0..n-1')
    for value in vector:
        if type(value) not in (int, float) or value <= 0:
            raise ValueError('Certificate vector must be strictly positive')
        if (type(value) is float and not math.isfinite(value)) or (type(value) is int and value.bit_length() > 4096):
            raise ValueError('Invalid certificate vector magnitude')
    x = list(map(Fraction, vector))
    action = [Fraction() for _ in range(n)]
    neighbors = [set() for _ in range(n)]
    seen = set()
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError('Each certificate edge needs two vertices')
        u, v = edge
        if type(u) is not int or type(v) is not int or not 0 <= u < n or not 0 <= v < n or u == v:
            raise ValueError('Invalid simple-graph certificate edge')
        key = tuple(sorted((u, v)))
        if key in seen:
            raise ValueError('Repeated certificate edge')
        seen.add(key)
        neighbors[u].add(v)
        neighbors[v].add(u)
        action[u] += x[v]
        action[v] += x[u]
    reached = {0}
    pending = [0]
    while pending:
        for v in neighbors[pending.pop()]-reached:
            reached.add(v)
            pending.append(v)
    if len(reached) != n:
        raise ValueError('Connected graph required for this certificate contract')
    ratios = [a/t for a, t in zip(action, x)]
    rayleigh = sum((a*t for a, t in zip(action, x)), Fraction())/sum((t*t for t in x), Fraction())
    lower = max(rayleigh, min(ratios), Fraction(2*len(edges), n))
    upper = min(max(ratios), Fraction(max(map(len, neighbors))))
    if lower > upper:
        raise ArithmeticError('Inconsistent exact adjacency bounds')
    return {'rho_interval': [str(lower), str(upper)], 'graph_sha256': edge_list_digest(n, edges), 'rayleigh_lower': str(rayleigh),
            'collatz_lower': str(min(ratios)), 'collatz_upper': str(max(ratios)),
            'independent': True, 'arithmetic': 'exact_rational_of_stored_vector'}


def verify_adjacency_certificate(n, edges, certificate):
    """Check a saved certificate without re-running any spectral solver."""
    if not isinstance(certificate, dict):
        raise ValueError('Expected an adjacency certificate object')
    checked = adjacency_bounds(n, edges, certificate.get('vector'))
    checked['passed'] = (certificate.get('rho_interval') == checked['rho_interval'] and
                         certificate.get('graph_sha256') == checked['graph_sha256'] and
                         certificate.get('rayleigh_lower') == checked['rayleigh_lower'] and
                         certificate.get('collatz_lower') == checked['collatz_lower'] and
                         certificate.get('collatz_upper') == checked['collatz_upper'])
    return checked
