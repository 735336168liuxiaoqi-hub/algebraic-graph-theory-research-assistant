"""Exact combinatorial helpers adapted from myCombinatorics.sage."""
from collections import Counter
from functools import lru_cache
from itertools import combinations, product
import math
import networkx as nx
from graph_research._lazy import sympy as sp


@lru_cache(maxsize=None)
def Partition_Number(n, k):
    if n == k == 0: return 1
    if n < 0 or k <= 0 or k > n: return 0
    return Partition_Number(n-1, k-1)+Partition_Number(n-k, k)


def divMatrix(n):
    return sp.Matrix(n, n, lambda i, j: int((i+1)%(j+1) == 0))


def mobuisMatrix(n):
    return sp.Matrix(n, n, lambda i, j: sp.mobius((i+1)//(j+1)) if (i+1)%(j+1) == 0 else 0)


def BD_incidence_matrix(vertices, blocks):
    return sp.Matrix([[int(v in edge) for edge in blocks] for v in vertices])


def zeta_mat(vertices):
    values = list(vertices)
    if len(values) > 12: raise ValueError("Subset incidence matrix grows exponentially; limit is12")
    subsets = [frozenset(c) for size in range(len(values)+1) for c in combinations(values, size)]
    return sp.Matrix([[int(a <= b) for b in subsets] for a in subsets])


def num_cycletype(parts):
    counts = Counter(parts)
    return math.factorial(sum(parts))//math.prod(math.factorial(multiplicity)*length**multiplicity
                                                for length, multiplicity in counts.items())


def Equivs(classes, k):
    representatives = []
    for counts in product(*(range(len(c)+1) for c in classes)):
        if sum(counts) == k:
            representatives.append([v for c, count in zip(classes, counts) for v in c[:count]])
    return representatives


def matching_generating_function(g, variable=None):
    """sum m_k*x**k using a deletion recurrence (unweighted simple graphs)."""
    if len(g) > 24: raise ValueError("Exact matching recurrence limited to24 vertices")
    nodes = list(g)
    index = {v: i for i, v in enumerate(nodes)}
    neighbors = [sum(1 << index[u] for u in g[v]) for v in nodes]
    @lru_cache(maxsize=None)
    def counts(mask):
        if not mask: return (1,)
        v = (mask & -mask).bit_length()-1
        remainder = mask & ~(1 << v)
        result = list(counts(remainder))
        choices = neighbors[v] & remainder
        while choices:
            u = (choices & -choices).bit_length()-1
            subset = counts(remainder & ~(1 << u))
            if len(result) < len(subset)+1: result += [0]*(len(subset)+1-len(result))
            for k, value in enumerate(subset): result[k+1] += value
            choices &= choices-1
        return tuple(result)
    x = sp.Symbol("x") if variable is None else variable
    return sp.Poly(sum(value*x**k for k, value in enumerate(counts((1 << len(nodes))-1))), x)


def rook_polynomial(matrix):
    board = sp.Matrix(matrix)
    graph = nx.Graph()
    graph.add_nodes_from(("r", i) for i in range(board.rows))
    graph.add_nodes_from(("c", j) for j in range(board.cols))
    graph.add_edges_from((("r", i), ("c", j)) for i in range(board.rows)
                         for j in range(board.cols) if board[i, j] != 0)
    return matching_generating_function(graph)


def cycle_index_polynomial(permutations):
    """Standard normalized cycle index; permutations use zero-based images."""
    group = [list(p) for p in permutations]
    if not group: raise ValueError("Empty permutation collection")
    n = len(group[0]); variables = sp.symbols(f"x1:{n+1}")
    result = 0
    for permutation in group:
        if sorted(permutation) != list(range(n)): raise ValueError("Invalid permutation")
        seen, monomial = set(), sp.Integer(1)
        for start in range(n):
            if start in seen: continue
            v, length = start, 0
            while v not in seen:
                seen.add(v); length += 1; v = permutation[v]
            monomial *= variables[length-1]
        result += monomial
    return sp.expand(result/len(group))

from .groups import getCycleIndex,getCycleIndex1
_VISUAL_NAMES={'gridPath','getGridPath','lattice_path','rectangle','chess_board'}

def __getattr__(name):
    if name not in _VISUAL_NAMES:raise AttributeError(name)
    from graph_research.rendering import lattice
    return getattr(lattice,name)

def __dir__():return sorted(set(globals())|_VISUAL_NAMES)
