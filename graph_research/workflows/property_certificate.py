"""Independent Fraction-only verification of small graph property certificates."""
from fractions import Fraction
import hashlib
import json


def rational(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)) or len(str(value)) > 64:
        raise ValueError('矩阵系数须为有限有理数，字符串长度不超过64。')
    result = Fraction(str(value))
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > 128:
        raise ValueError('有理数系数超过128位限制。')
    return result


def matrix_data(graph, matrix='A', alpha=0, a=1, d=0):
    if not isinstance(graph, dict) or set(graph)-{'kind', 'n', 'edges'}:
        raise ValueError('仅支持明确的无向无权简单图参数。')
    n = graph.get('n')
    if type(n) is not int or not 1 <= n <= 12:
        raise ValueError('精确图性质工具支持1至12顶点。')
    kind = graph.get('kind')
    if kind == 'edges':
        edges = graph.get('edges', [])
    elif 'edges' in graph:
        raise ValueError('edges仅用于kind=edges。')
    elif kind == 'path':
        edges = [[i, i+1] for i in range(n-1)]
    elif kind == 'cycle' and n >= 3:
        edges = [[i, (i+1) % n] for i in range(n)]
    elif kind == 'star':
        edges = [[0, i] for i in range(1, n)]
    elif kind == 'complete':
        edges = [[i, j] for i in range(n) for j in range(i+1, n)]
    elif kind == 'empty':
        edges = []
    else:
        raise ValueError('不支持该图类型。')
    if not isinstance(edges, list) or len(edges) > n*(n-1)//2:
        raise ValueError('边表超出简单图范围。')
    pairs = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2 or any(type(v) is not int or not 0 <= v < n for v in edge) or edge[0] == edge[1]:
            raise ValueError('边必须连接两个不同的已有顶点。')
        pairs.append(tuple(sorted(edge)))
    if len(set(pairs)) != len(pairs):
        raise ValueError('重复边不属于简单图输入。')
    edges = sorted(pairs)
    alpha, a, d = rational(alpha), rational(a), rational(d)
    if matrix == 'A':
        a, d = Fraction(1), Fraction(0)
    elif matrix == 'L':
        a, d = Fraction(-1), Fraction(1)
    elif matrix == 'Q':
        a, d = Fraction(1), Fraction(1)
    elif matrix == 'alpha' and 0 <= alpha <= 1:
        a, d = 1-alpha, alpha
    elif matrix != 'U' or not a:
        raise ValueError('矩阵为A、L、Q=D+A、alpha或U=aA+dD；U要求a非零。')
    values = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    for u, v in edges:
        values[u][v] = values[v][u] = a
        values[u][u] += d
        values[v][v] += d
    spec = {'graph': {'kind': 'edges', 'n': n, 'edges': [list(e) for e in edges]},
            'matrix': {'kind': matrix, 'adjacency_coefficient': str(a), 'degree_coefficient': str(d)}}
    identity = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return values, spec, identity


def characteristic(values):
    """Faddeev-LeVerrier, independently of the primary SymPy charpoly routine."""
    n = len(values)
    b = [[Fraction(i == j) for j in range(n)] for i in range(n)]
    coefficients = [Fraction(1)]
    for k in range(1, n+1):
        b = [[sum(values[i][r]*b[r][j] for r in range(n)) for j in range(n)] for i in range(n)]
        coefficient = -sum(b[i][i] for i in range(n))/k
        coefficients.append(coefficient)
        for i in range(n):
            b[i][i] += coefficient
    return coefficients


def polynomial_gcd(left, right):
    left, right = list(left), list(right)
    while right and any(right):
        while left and len(left) >= len(right):
            factor = left[0]/right[0]
            left = [v-factor*w for v, w in zip(left[:len(right)], right)]+left[len(right):]
            while left and not left[0]:
                left.pop(0)
        left, right = right, left
    return [str(v/left[0]) for v in left] if left else []


def walk_rank(values):
    n = len(values)
    vector = [Fraction(1)]*n
    columns = []
    for _ in range(n):
        columns.append(vector)
        vector = [sum(row[j]*vector[j] for j in range(n)) for row in values]
    rows = [list(row) for row in zip(*columns)]
    rank = 0
    for col in range(n):
        pivot = next((i for i in range(rank, n) if rows[i][col]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        leading = rows[rank][col]
        rows[rank] = [v/leading for v in rows[rank]]
        for i in range(rank+1, n):
            factor = rows[i][col]
            rows[i] = [v-factor*w for v, w in zip(rows[i], rows[rank])]
        rank += 1
    return rank


def graph_property_verify(graph, certificate, matrix='A', alpha=0, a=1, d=0):
    values, spec, identity = matrix_data(graph, matrix, alpha, a, d)
    n = len(values)
    p = characteristic(values)
    derivative = [v*(n-i) for i, v in enumerate(p[:-1])]
    gcd = polynomial_gcd(p, derivative)
    rank = walk_rank(values)
    vertex_gcds = []
    for v in range(n):
        minor = [[values[i][j] for j in range(n) if j != v] for i in range(n) if i != v]
        vertex_gcds.append(polynomial_gcd(p, characteristic(minor)))
    expected = {'format': 'graph-property-certificate/1', 'scope_sha256': identity, 'matrix_spec': spec['matrix'],
                'characteristic_coefficients': [str(v) for v in p], 'multiplicity_gcd': gcd, 'walk_rank': rank,
                'vertex_gcds': vertex_gcds,
                'properties': {'simple_spectrum': len(gcd) == 1, 'controllable': rank == n,
                               'has_wronskian_vertex': any(len(g) == 1 for g in vertex_gcds)}}
    return {'passed': certificate == expected, 'scope_sha256': identity, 'properties': expected['properties'],
            'walk_rank': rank, 'wronskian_vertices': [v for v, g in enumerate(vertex_gcds) if len(g) == 1],
            'verification_method': 'independent_fraction_characteristic_gcd_and_krylov_rank',
            'arithmetic': 'exact_rational', 'scope': 'this_graph_and_explicit_matrix_only'}
