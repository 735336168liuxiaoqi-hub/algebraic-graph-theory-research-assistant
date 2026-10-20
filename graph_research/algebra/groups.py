"""Finite permutation groups in SymPy and labelled Cayley graphs in NetworkX."""
from itertools import islice
import numbers
import networkx as nx
from graph_research._lazy import sympy as sp


def permutation_group(generators,max_order=4096):
    """Build a group from zero-based image lists; bound BEFORE enumerating."""
    from sympy.combinatorics import Permutation,PermutationGroup
    if type(max_order) is not int or not 1<=max_order<=100000:raise ValueError('群阶上限须为1..100000。')
    if isinstance(generators,PermutationGroup):group=generators
    else:
        rows=[list(row) for row in generators]
        if not rows or not 1<=len(rows[0])<=16 or len(rows)>16:raise ValueError('需要1..16个生成元，作用点数1..16。')
        size=len(rows[0])
        if any(len(row)!=size or any(isinstance(v,bool) or not isinstance(v,numbers.Real) or not 0<=v<size or v!=int(v) for v in row) or sorted(row)!=list(range(size)) for row in rows):
            raise ValueError('每个生成元须为同一长度的0起始置换像列表。')
        group=PermutationGroup([Permutation(list(map(int,row)),size=size) for row in rows])
    if group.order()>max_order:raise ValueError(f'群阶超过{max_order}，不会展开枚举。')
    return group


def _members(group,max_order):
    group=permutation_group(group,max_order)
    return group,sorted(group.generate_schreier_sims(),key=lambda p:tuple(p.array_form))


def getCycleIndex(group,*,max_order=4096):
    """Standard cycle index Z(G)=average(product(x_j**number_of_j_cycles))."""
    group,members=_members(group,max_order);variables=sp.symbols(f'x1:{group.degree+1}');result=sp.S.Zero
    for element in members:
        result+=sp.prod(variables[length-1]**count for length,count in element.cycle_structure.items())
    return sp.expand(result/len(members))


def getCycleIndex1(group,*,max_order=4096):
    """Legacy partition-as-exponents encoding; NOT the standard cycle index.

    Sage's getCycleIndex1 used a partition's parts as consecutive exponents,
    not as cycle lengths. Preserve that representation explicitly, x0..x(n-1).
    Use getCycleIndex for Polya/Burnside calculations.
    """
    group,members=_members(group,max_order);variables=sp.symbols(f'x0:{group.degree}');result=sp.S.Zero
    for element in members:
        partition=sorted([length for length,count in element.cycle_structure.items() for _ in range(count)],reverse=True)
        result+=sp.prod(variable**part for variable,part in zip(variables,partition))
    return sp.expand(result/len(members))


def cayley_graph(group,side='right',simple=False,elements=None,generators=None,connecting_set=None,*,max_order=4096):
    """Left/right/twosided finite Cayley graph, preserving generator labels.

    SymPy groups use Schreier-Sims with an order bound. Other finite semigroups
    require explicit generators and iterable hashable elements implementing
    multiplication. An explicit elements subset gives an induced restriction.
    simple=True returns a loopless DiGraph; otherwise a labelled MultiDiGraph.
    """
    if side not in ('left','right','twosided'):raise ValueError('side须为left/right/twosided。')
    if type(max_order) is not int or not 1<=max_order<=100000:raise ValueError('需要有限的群阶上限。')
    from sympy.combinatorics import PermutationGroup
    if connecting_set is not None:
        if generators is not None:raise ValueError('generators与connecting_set只能指定一个。')
        generators=connecting_set
    if isinstance(group,PermutationGroup):
        group=permutation_group(group,max_order)
        if generators is None:generators=group.generators
        if elements is None:elements=group.generate_schreier_sims()
    elif elements is None:elements=group
    nodes=list(islice(iter(elements),max_order+1))
    if len(nodes)>max_order or len(set(nodes))!=len(nodes):raise ValueError('元素数超过上限或含重复元素。')
    if generators is None:raise ValueError('普通有限半群须显式提供生成元。')
    labels=dict(generators) if isinstance(generators,dict) else dict(enumerate(islice(iter(generators),65)))
    if len(labels)>64:raise ValueError('生成元至多64个。')
    result=nx.DiGraph() if simple else nx.MultiDiGraph();result.add_nodes_from(nodes);known=set(nodes)
    for element in nodes:
        for label,generator in labels.items():
            for action in (('left','right') if side=='twosided' else (side,)):
                target=generator*element if action=='left' else element*generator
                if target not in known or (simple and target==element):continue
                if simple:result.add_edge(element,target)
                else:result.add_edge(element,target,generator=label,side=action)
    return result


def group_calculation(operation,generators,max_order=128,side='right'):
    """JSON-safe standard cycle index or directed Cayley structure."""
    group,members=_members(generators,max_order)
    if operation=='cycle_index':
        return {'polynomial':str(getCycleIndex(group,max_order=max_order)),
                'group_order':int(group.order()),'action_degree':group.degree,
                'variables':[f'x{i}' for i in range(1,group.degree+1)],'normalization':'average over every group element'}
    if operation!='cayley_graph':raise ValueError('未知群计算。')
    graph=cayley_graph(group,side=side,simple=True,max_order=max_order);index={element:i for i,element in enumerate(members)}
    return {'n':len(members),'arcs':[[index[u],index[v]] for u,v in graph.edges()],
            'elements':[list(p.array_form) for p in members],'directed':True,'side':side,
            'group_order':len(members),'note':'arcs为有向边；不是无向边表，n是群阶而不是置换作用点数。'}
