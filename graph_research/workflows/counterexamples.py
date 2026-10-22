"""Bounded simple-graph search; floating screening never certifies a witness."""
import itertools
import math
import random
from fractions import Fraction

import networkx as nx
import numpy as np
from .graph_spectral_certificate import MAX_ORDER, MAX_EDGES, POLYNOMIAL_ORDER, edge_list_digest


STRATEGIES = ('enumerate', 'edge_move', 'rewire', 'random')
MAX_VISITED = 512


def _graph(spec):
    from graph_research.graphs import make_graph
    if not isinstance(spec, dict) or set(spec)-{'kind', 'n', 'edges'}:
        raise ValueError('Only explicit unweighted undirected simple graph specifications are supported')
    n = spec.get('n')
    if type(n) is not int or not 2 <= n <= MAX_ORDER:
        raise ValueError(f'Counterexample search supports 2..{MAX_ORDER} vertices')
    if spec.get('kind') == 'edges':
        seen = set()
        for edge in spec.get('edges', []):
            if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                raise ValueError('Each edge needs exactly two vertices')
            u, v = edge
            if type(u) is not int or type(v) is not int or not 0 <= u < n or not 0 <= v < n or u == v:
                raise ValueError('Loops, unknown vertices and noninteger labels are not accepted')
            key = tuple(sorted((u, v)))
            if key in seen:
                raise ValueError('Repeated edges are not accepted')
            seen.add(key)
    graph = make_graph(**spec)
    if graph.number_of_edges() > MAX_EDGES:
        raise ValueError(f'Counterexample search supports at most {MAX_EDGES} edges')
    if len(graph) != n or set(graph) != set(range(n)) or graph.is_directed() or nx.number_of_selfloops(graph):
        raise ValueError('The graph must have exactly the declared vertices 0..n-1')
    if not nx.is_connected(graph):
        raise ValueError('The graph must be connected')
    return graph


def _spec(graph):
    return {'kind': 'edges', 'n': len(graph), 'edges': [list(e) for e in sorted(tuple(sorted(e)) for e in graph.edges)]}


def _key(graph):
    return edge_list_digest(len(graph), graph.edges)


def _score(graph):
    matrix = nx.to_numpy_array(graph, nodelist=range(len(graph)), dtype=float)
    values, vectors = np.linalg.eigh(matrix)
    return float(values[-1]), np.abs(vectors[:, -1])


def validate_problem(problem):
    """Semantic preflight, also called before a durable search task is registered."""
    graph = _graph(problem['reference'])
    n, m = len(graph), graph.number_of_edges()
    return {'n': n, 'm': m, 'connected': True, 'directed': False, 'weighted': False,
            'objective': 'maximize_adjacency_spectral_radius', 'reference': _spec(graph),
            'uninterpreted_text_is_not_a_constraint': True}


def graph_counterexample_round(reference, strategy='edge_move', candidates=12, seed=42,
                               incumbent=None, seen=None, cursor=0):
    """Generate and screen one bounded round; all comparisons here are numerical."""
    graph = _graph(reference)
    if strategy not in STRATEGIES or type(candidates) is not int or not 1 <= candidates <= 24:
        raise ValueError('Invalid strategy or candidate budget')
    if type(seed) is not int or not 0 <= seed < 2**32 or type(cursor) is not int or not 0 <= cursor <= 20000:
        raise ValueError('Invalid seed or enumeration cursor')
    n, m = len(graph), graph.number_of_edges()
    best = _graph(incumbent) if incumbent is not None else graph.copy()
    if len(best) != n or best.number_of_edges() != m:
        raise ValueError('Incumbent must satisfy the same n/m/connected constraints')
    seen = list(seen or [])
    if len(seen) > MAX_VISITED or any(not isinstance(k, str) or len(k) != 64 or any(c not in '0123456789abcdef' for c in k) for k in seen):
        raise ValueError('Invalid visited graph records')
    visited = dict.fromkeys(seen)
    visited[_key(graph)] = None
    evictions = 0
    if len(visited) > MAX_VISITED:
        del visited[next(iter(visited))]
        evictions += 1
    baseline, _ = _score(graph)
    best_score, vector = _score(best)
    rng = random.Random(seed)
    possible = list(itertools.combinations(range(n), 2))
    total = math.comb(len(possible), m)
    if strategy == 'enumerate' and total > 20000:
        raise ValueError('Labelled enumeration is limited to 20000 combinations; use a heuristic strategy')
    records = []
    generated = 0
    enumeration_complete = False
    iterator = itertools.islice(itertools.combinations(possible, m), cursor, None) if strategy == 'enumerate' else None
    for _ in range(max(64, candidates*16)):
        if len(records) >= candidates:
            break
        if iterator is not None:
            edges = next(iterator, None)
            if edges is None:
                enumeration_complete = True
                break
            cursor += 1
            candidate = nx.empty_graph(n)
            candidate.add_edges_from(edges)
        elif strategy == 'random':
            candidate = nx.empty_graph(n)
            candidate.add_edges_from(rng.sample(possible, m))
        else:
            candidate = best.copy()
            edges, missing = list(candidate.edges), list(nx.non_edges(candidate))
            if not missing:
                break
            if strategy == 'edge_move':
                edges.sort(key=lambda e: vector[e[0]]*vector[e[1]])
                missing.sort(key=lambda e: vector[e[0]]*vector[e[1]], reverse=True)
                remove = rng.choice(edges[:min(4, len(edges))])
                add = rng.choice(missing[:min(4, len(missing))])
            else:
                remove, add = rng.choice(edges), rng.choice(missing)
            candidate.remove_edge(*remove)
            candidate.add_edge(*add)
        generated += 1
        key = _key(candidate)
        if key in visited:
            continue
        visited[key] = None
        if len(visited) > MAX_VISITED:
            del visited[next(iter(visited))]
            evictions += 1
        if not nx.is_connected(candidate):
            continue
        score, candidate_vector = _score(candidate)
        records.append({'graph6': nx.to_graph6_bytes(candidate, nodes=range(n), header=False).decode('ascii').strip(),
                        'graph_sha256': key, 'rho_estimate': score})
        if score > best_score:
            best, best_score, vector = candidate, score, candidate_vector
    margin = 1e-10*max(1, abs(baseline))
    return {'status': 'screening_only', 'strategy': strategy, 'seed': seed,
            'n': n, 'm': m, 'reference_rho_estimate': baseline, 'best_rho_estimate': best_score,
            'best_graph': _spec(best), 'promising': best_score > baseline+margin,
            'generated_attempts': generated, 'evaluated_candidates': len(records), 'evaluations': records,
            'seen': list(visited), 'cursor': cursor, 'visited_cache_evictions': evictions,
            'visited_identity_format': 'sha256_labelled_edges', 'visited_cache_capacity': MAX_VISITED,
            'labelled_enumeration_complete': enumeration_complete or (strategy == 'enumerate' and cursor >= total),
            'counterexample_verified': False, 'mathematical_proof': False,
            'limitations': ['Only n, m and connected simple-graph constraints are checked.',
                            'Visited identities are labelled edge-list SHA256, not isomorphism classes; older entries may be evicted.',
                            'Finite or exhausted numerical screening does not prove optimality.']}


def _certificate(graph, digits):
    from graph_research._lazy import sympy as sp
    from graph_research.workflows.energy import energy_interval, verify_energy_interval
    matrix = sp.Matrix(nx.to_numpy_array(graph, nodelist=range(len(graph)), dtype=int).tolist())
    polynomial = matrix.charpoly(sp.Symbol('x')).as_poly()
    intervals = energy_interval(polynomial, digits)
    if not verify_energy_interval(polynomial, intervals):
        raise ArithmeticError('Independent root-count verification failed')
    return {'coefficients_descending': [str(v) for v in polynomial.all_coeffs()],
            'polynomial': str(polynomial.as_expr()), 'rho_interval': intervals['root_intervals'][-1]['interval'],
            'all_root_intervals': intervals['root_intervals'], 'root_counts_verified': True}


def _rational_certificate(graph, refinement_steps):
    from .graph_spectral_certificate import adjacency_bounds, verify_adjacency_certificate
    degrees = [graph.degree(i) for i in range(len(graph))]
    if len(set(degrees)) == 1:
        vector = np.ones(len(graph))
    else:
        _, vector = _score(graph)
        vector = np.maximum(vector/vector.max(), 1e-15)
        neighbors = [list(graph[i]) for i in range(len(graph))]
        for _ in range(refinement_steps):
            vector = np.array([float(vector[i])+math.fsum(float(vector[j]) for j in neighbors[i]) for i in range(len(graph))])
            vector = np.maximum(vector/vector.max(), np.finfo(float).tiny)
    raw = vector.tolist()
    edges = _spec(graph)['edges']
    certificate = {'vector': raw, **adjacency_bounds(len(graph), edges, raw),
                   'level': 'exact_rational_rayleigh_collatz', 'refinement_steps': refinement_steps}
    if not verify_adjacency_certificate(len(graph), edges, certificate)['passed']:
        raise ArithmeticError('Independent rational adjacency certificate failed')
    return certificate


def graph_counterexample_verify(reference, candidate, digits=12):
    """Use exact polynomial roots for small graphs, rational spectral bounds above."""
    baseline = _graph(reference)
    other = _graph(candidate)
    if len(other) != len(baseline) or other.number_of_edges() != baseline.number_of_edges():
        raise ValueError('Candidate violates fixed n/m constraints')
    if type(digits) is not int or not 6 <= digits <= 24:
        raise ValueError('Initial root isolation precision must be 6..24 digits')
    small = len(baseline) <= POLYNOMIAL_ORDER
    stages = list(dict.fromkeys([digits, min(48, digits*2), 48])) if small else [0, 32, 128, 512]
    for precision in stages:
        builder = _certificate if small else _rational_certificate
        left, right = builder(baseline, precision), builder(other, precision)
        a, b = map(Fraction, left['rho_interval'])
        c, d = map(Fraction, right['rho_interval'])
        lo, hi = c-b, d-a
        if lo > 0:
            status = 'counterexample_found'
        elif hi <= 0 or _spec(baseline) == _spec(other) or (small and left['coefficients_descending'] == right['coefficients_descending']):
            status = 'not_counterexample'
        else:
            status = 'candidate_unverified'
        if status != 'candidate_unverified':
            break
    return {'status': status, 'counterexample_verified': status == 'counterexample_found',
            'constraints_verified': {'n': len(other), 'm': other.number_of_edges(), 'connected': True,
                                     'simple': True, 'undirected': True, 'unweighted': True},
            'reference': _spec(baseline), 'candidate': _spec(other),
            'reference_certificate': left, 'candidate_certificate': right,
            'difference_bounds': [str(lo), str(hi)], 'isolation_digits': precision if small else None,
            'vector_refinement_steps': None if small else precision,
            'verification_method': 'integer_adjacency_charpoly_rational_root_isolation_independent_sturm_counts' if small else 'exact_rational_rayleigh_collatz',
            'universal_optimality_proved': False,
            'interpretation': 'A verified strict improvement refutes only the stated n/m/connected adjacency claim; failure to find one is not a proof.'}


def tool_definitions(obj, graph_args):
    import copy
    graph = obj(copy.deepcopy(graph_args), ['kind', 'n'])
    graph['properties']['n'].update(minimum=2, maximum=MAX_ORDER)
    graph['properties']['edges']['maxItems'] = MAX_EDGES
    return [
        ('graph_counterexample_round', '连通简单图反例搜索轮次：仅数值筛选，不证明反例。', graph_counterexample_round,
         obj({'reference': graph, 'strategy': {'enum': list(STRATEGIES)},
              'candidates': {'type': 'integer', 'minimum': 1, 'maximum': 24},
              'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2**32-1}, 'incumbent': graph,
              'seen': {'type': 'array', 'maxItems': MAX_VISITED, 'uniqueItems': True,
                       'items': {'type': 'string', 'minLength': 64, 'maxLength': 64, 'pattern': '^[0-9a-f]{64}$'}},
              'cursor': {'type': 'integer', 'minimum': 0, 'maximum': 20000}}, ['reference'])),
        ('graph_counterexample_verify', '从原始边表独立核验邻接谱半径严格改进，输出精确根区间证据。', graph_counterexample_verify,
         obj({'reference': graph, 'candidate': graph,
              'digits': {'type': 'integer', 'minimum': 6, 'maximum': 24}}, ['reference', 'candidate']))]
