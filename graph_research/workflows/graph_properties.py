"""Paged graph-family experiments with exact predicates and bounded outputs."""
import hashlib
import json

import networkx as nx
import sympy as sp

from .property_certificate import matrix_data, graph_property_verify

PROPERTIES = ('simple_spectrum', 'controllable', 'has_wronskian_vertex')


def _certificate(graph, matrix, alpha, a, d):
    values, spec, identity = matrix_data(graph, matrix, alpha, a, d)
    m = sp.Matrix([[sp.Rational(v.numerator, v.denominator) for v in row] for row in values])
    x = sp.Symbol('x')
    p = m.charpoly(x).as_poly()
    gcd = sp.gcd(p, p.diff()).monic()
    vector = sp.ones(m.rows, 1)
    columns = []
    for _ in range(m.rows):
        columns.append(vector)
        vector = m*vector
    rank = sp.Matrix.hstack(*columns).rank()
    vertex_gcds = [list(map(str, sp.gcd(p, m.minor_submatrix(v, v).charpoly(x).as_poly()).monic().all_coeffs())) for v in range(m.rows)]
    certificate = {'format': 'graph-property-certificate/1', 'scope_sha256': identity, 'matrix_spec': spec['matrix'],
                   'characteristic_coefficients': list(map(str, p.all_coeffs())),
                   'multiplicity_gcd': list(map(str, gcd.all_coeffs())), 'walk_rank': rank, 'vertex_gcds': vertex_gcds,
                   'properties': {'simple_spectrum': gcd.degree() == 0, 'controllable': rank == m.rows,
                                  'has_wronskian_vertex': any(len(g) == 1 for g in vertex_gcds)}}
    return spec['graph'], certificate


def _source(source, orders, graphs):
    if source == 'provided':
        if orders is not None or not isinstance(graphs, list) or not 1 <= len(graphs) <= 128:
            raise ValueError('provided需要1至128张graphs，不同时指定orders。')
        result = [matrix_data(g)[1]['graph'] for g in graphs]
        return result, False
    if graphs is not None or source not in ('atlas', 'trees'):
        raise ValueError('请选择atlas、trees或provided，graphs仅用于provided。')
    orders = [6] if orders is None else orders
    if not isinstance(orders, list) or not orders or len(set(orders)) != len(orders) or any(type(n) is not int or not 1 <= n <= (7 if source == 'atlas' else 12) for n in orders):
        raise ValueError('atlas支持1至7阶；trees支持1至12阶，不得重复。')
    objects = [g for g in nx.graph_atlas_g() if len(g) in orders] if source == 'atlas' else [g for n in sorted(orders) for g in ([nx.empty_graph(1)] if n == 1 else nx.nonisomorphic_trees(n))]
    return [{'kind': 'edges', 'n': len(g), 'edges': [list(e) for e in sorted(g.edges())]} for g in objects], True


def graph_property_scan(source='atlas', orders=None, graphs=None, matrix='A', alpha=0, a=1, d=0, filters=None, select=None, cursor=0, source_id=None, batch_size=32):
    filters = {} if filters is None else filters
    select = {} if select is None else select
    if set(filters)-{'connected', 'bipartite', 'min_edges', 'max_edges', 'min_degree', 'max_degree'} or any(type(v) is not bool for k, v in filters.items() if k in ('connected', 'bipartite')) or any(type(v) is not int or v < 0 for k, v in filters.items() if k not in ('connected', 'bipartite')):
        raise ValueError('结构筛选条件无效。')
    if set(select)-set(PROPERTIES) or any(type(v) is not bool for v in select.values()):
        raise ValueError('性质选择只接受三种登记性质的布尔值。')
    if type(cursor) is not int or cursor < 0 or type(batch_size) is not int or not 1 <= batch_size <= 128:
        raise ValueError('cursor须非负，batch_size为1至128。')
    for lower, upper in (('min_edges', 'max_edges'), ('min_degree', 'max_degree')):
        if lower in filters and upper in filters and filters[lower] > filters[upper]:
            raise ValueError('筛选下限不能大于上限。')
    objects, nonisomorphic = _source(source, orders, graphs)
    matrix_data(objects[0], matrix, alpha, a, d)
    scope = {'source': source, 'orders': sorted(orders or ([6] if source != 'provided' else [])),
             'graphs': objects if source == 'provided' else None, 'matrix': matrix, 'alpha': str(alpha), 'a': str(a), 'd': str(d), 'filters': filters, 'select': select}
    identity = hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if cursor > len(objects) or (cursor and source_id != identity) or (source_id is not None and source_id != identity):
        raise ValueError('分页范围或source_id变化，不能把不同实验拼接。')
    end = min(cursor+batch_size, len(objects))
    rows, counts = [], {}
    for index in range(cursor, end):
        graph = objects[index]
        n = graph['n']
        bucket = counts.setdefault(str(n), {'visited': 0, 'eligible': 0, 'selected': 0, **dict.fromkeys(PROPERTIES, 0), 'controllable_with_wronskian': 0})
        bucket['visited'] += 1
        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(graph['edges'])
        degree = [v for _, v in g.degree()]
        if any((key == 'connected' and nx.is_connected(g) != value) or (key == 'bipartite' and nx.is_bipartite(g) != value) or (key == 'min_edges' and len(graph['edges']) < value) or (key == 'max_edges' and len(graph['edges']) > value) or (key == 'min_degree' and min(degree) < value) or (key == 'max_degree' and max(degree) > value) for key, value in filters.items()):
            continue
        spec, certificate = _certificate(graph, matrix, alpha, a, d)
        properties = certificate['properties']
        selected = all(properties[k] == v for k, v in select.items())
        bucket['eligible'] += 1
        bucket['selected'] += int(selected)
        for key in PROPERTIES:
            bucket[key] += int(properties[key])
        bucket['controllable_with_wronskian'] += int(properties['controllable'] and properties['has_wronskian_vertex'])
        rows.append({'index': index, 'graph': spec, 'selected': selected, 'properties': properties, 'certificate': certificate})
    return {'source_id': identity, 'source': source, 'matrix': matrix, 'cursor_start': cursor, 'cursor_next': end,
            'total_candidates': len(objects), 'finished': end == len(objects), 'nonisomorphic': nonisomorphic,
            'scope': scope, 'counts_by_order': counts, 'rows': rows,
            'arithmetic': 'exact_rational', 'independent_verification': False,
            'completeness': 'complete_supported_generator' if nonisomorphic else 'provided_input_set_only',
            'meaning': '本页为有限范围精确计算；跨页须核对source_id和连续游标。未扫描全部范围不构成完整统计；不推导一般定理。'}


def tool_definitions(obj, graph_args):
    rational = {'anyOf': [{'type': 'number'}, {'type': 'string', 'minLength': 1, 'maxLength': 64}]}
    matrix = {'enum': ['A', 'L', 'Q', 'alpha', 'U']}
    graph = obj({**graph_args, 'n': {'type': 'integer', 'minimum': 1, 'maximum': 12}}, ['kind', 'n'])
    coefficients = {'matrix': matrix, 'alpha': rational, 'a': rational, 'd': rational}
    boolean = {'type': 'boolean'}
    filters = obj({'connected': boolean, 'bipartite': boolean, **{k: {'type': 'integer', 'minimum': 0, 'maximum': 66} for k in ('min_edges', 'max_edges', 'min_degree', 'max_degree')}})
    return [
        ('graph_property_scan', '图族性质分批遍历与精确统计', graph_property_scan, obj({
            'source': {'enum': ['atlas', 'trees', 'provided']}, 'orders': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'uniqueItems': True, 'items': {'type': 'integer', 'minimum': 1, 'maximum': 12}},
            'graphs': {'type': 'array', 'minItems': 1, 'maxItems': 128, 'items': graph}, **coefficients,
            'filters': filters, 'select': obj(dict.fromkeys(PROPERTIES, boolean)), 'cursor': {'type': 'integer', 'minimum': 0},
            'source_id': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}, 'batch_size': {'type': 'integer', 'minimum': 1, 'maximum': 128}})),
        ('graph_property_verify', '图性质证据独立精确复核', graph_property_verify, obj({'graph': graph, 'certificate': {'type': 'object', 'maxProperties': 12}, **coefficients}, ['graph', 'certificate']))]
