"""Finite parameter-domain energy comparisons using rational root intervals."""
from graph_research._lazy import sympy as sp
from graph_research.workflows.recipes import build_recipe
from graph_research.graphs import exact_graph_matrix
from graph_research.graphs.weighted import weighted_matrices


def _polynomial(spec,parameters,resolved=None):
    if 'recipe' in spec:
        recipe=dict(spec['recipe'])
        if recipe.get('graph_type','graph')!='graph':raise ValueError('能量证书只支持普通无向图/实对称带权图。')
        fixed=dict(recipe.get('parameters',{}));fixed.update(parameters);recipe.update(parameters=fixed,graph_type='graph')
        graph,_=build_recipe(**recipe)
        if len(graph)>10:raise ValueError('精确能量比较限10顶点。')
        matrix=exact_graph_matrix(graph,'A')
        if resolved is not None:
            from graph_research.graph_input.adapters import result_graph
            nodes=list(graph);index={v:i for i,v in enumerate(nodes)}
            spec={'graph_spec':{'kind':'edges','n':len(nodes),'edges':[[index[u],index[v]] for u,v in graph.edges]},'graph_spec_labels':nodes}
            resolved.update(result_graph({'tool':'graph_recipe','ok':True,'arguments':recipe,'result':spec}).to_dict())
    elif 'weighted' in spec:
        weighted=dict(spec['weighted'])
        if weighted.get('matrix','A')!='A':raise ValueError('图能量比较仅用邻接矩阵A；L/Q的谱模之和不能混称普通图能量。')
        if weighted.get('n',129)>10:raise ValueError('精确能量比较限10顶点。')
        _,matrix,_,canonical=weighted_matrices(**weighted)
        if matrix!=matrix.T or any(value.is_Rational is not True for value in matrix):raise ValueError('证书需要有理数实对称矩阵，不能使用一般有向/复权矩阵。')
        if resolved is not None:
            from graph_research.graph_input.document import document
            try:
                records=[{'vertices':[r['u'],r['v']],'weight':float(matrix[r['u'],r['v']])} for r in canonical]
                if all(sp.Rational(str(r['weight']))==matrix[r['vertices'][0],r['vertices'][1]] for r in records):resolved.update(document(list(range(matrix.rows)),records,weighted=True,directed=weighted.get('directed',False)).to_dict())
            except (ValueError,OverflowError):pass
    else:
        from graph_research.graphs import make_graph
        from graph_research.tools.registry import GRAPH_ARGS,object_schema
        import jsonschema
        jsonschema.validate(spec,object_schema(GRAPH_ARGS,['kind','n']))
        if spec['n']>10:raise ValueError('精确能量比较限10顶点。')
        graph=make_graph(**spec);matrix=exact_graph_matrix(graph,'A')
        if resolved is not None:
            from graph_research.graph_input.document import from_networkx
            resolved.update(from_networkx(graph).to_dict())
    return matrix.charpoly(sp.Symbol('x')).as_poly()


def energy_interval(polynomial,digits=12):
    """A rational enclosure, counting every real eigenvalue multiplicity."""
    intervals=polynomial.intervals(eps=sp.Rational(1,10**digits))
    if sum(multiplicity for _,multiplicity in intervals)!=polynomial.degree():raise ValueError('多项式未获得覆盖全部次数的实根区间。')
    lower=sp.S.Zero;upper=sp.S.Zero;records=[]
    for (a,b),multiplicity in intervals:
        lo,hi=(a,b) if a>=0 else (-b,-a) if b<=0 else (sp.S.Zero,max(-a,b))
        lower+=lo*multiplicity;upper+=hi*multiplicity
        records.append({'interval':[str(a),str(b)],'multiplicity':multiplicity})
    certificate={'bounds':[str(lower),str(upper)],'root_intervals':records}
    if not verify_energy_interval(polynomial,certificate):raise ArithmeticError('精确根区间证书未通过独立计根复核。')
    return certificate


def verify_energy_interval(polynomial,certificate):
    """Recheck supplied intervals by square-free factor Sturm root counts."""
    try:
        factors=polynomial.sqf_list()[1];previous=None;total=0;lower=sp.S.Zero;upper=sp.S.Zero
        for record in certificate['root_intervals']:
            a,b=map(sp.Rational,record['interval']);multiplicity=record['multiplicity']
            if a>b or (previous is not None and a<=previous) or type(multiplicity) is not int or multiplicity<1:return False
            found=[]
            for factor,power in factors:
                count=int(factor.eval(a)==0) if a==b else factor.count_roots(a,b)
                found += [power]*count
            if found!=[multiplicity]:return False
            total+=multiplicity;previous=b
            lo,hi=(a,b) if a>=0 else (-b,-a) if b<=0 else (sp.S.Zero,max(-a,b))
            lower+=lo*multiplicity;upper+=hi*multiplicity
        return total==polynomial.degree() and list(map(sp.Rational,certificate['bounds']))==[lower,upper]
    except (KeyError,ValueError,TypeError,ZeroDivisionError):return False


def graph_energy_study(left,right,parameter='t',values=None,digits=12):
    """No infinite-domain claim; unresolved comparisons remain unresolved."""
    from graph_research.algebra.expressions import integer_symbols
    integer_symbols([parameter]);values=[0] if values is None else list(values)
    if not 1<=len(values)<=16 or any(type(value) is not int or not 0<=value<=128 for value in values) or len(set(values))!=len(values):raise ValueError('参数取1..16个互异的0..128整数。')
    if type(digits) is not int or not 4<=digits<=24:raise ValueError('初始根隔离精度须4..24位。')
    rows=[]
    for value in values:
        resolved_left={};resolved_right={}
        p,q=_polynomial(left,{parameter:value},resolved_left),_polynomial(right,{parameter:value},resolved_right)
        precision=digits
        while True:
            l,r=energy_interval(p,precision),energy_interval(q,precision)
            lo=sp.Rational(l['bounds'][0])-sp.Rational(r['bounds'][1]);hi=sp.Rational(l['bounds'][1])-sp.Rational(r['bounds'][0])
            comparison='equal_cospectral' if p==q else 'greater' if lo>0 else 'less' if hi<0 else 'undetermined'
            if comparison!='undetermined' or precision>=48:break
            precision=min(48,precision*2)
        rows.append({'parameter_value':value,'resolved_left':resolved_left,'resolved_right':resolved_right,'comparison':comparison,'difference_bounds':[str(lo),str(hi)],'left_certificate':{'polynomial':str(p.as_expr()),**l},
                     'right_certificate':{'polynomial':str(q.as_expr()),**r},'isolation_digits':precision,'verified':True})
    return {'status':'certified_finite_domain' if all(row['comparison']!='undetermined' for row in rows) else 'partly_undetermined','parameter':parameter,'domain':values,'rows':rows,
            'interpretation':'仅覆盖列出的有限整数参数；对有理实对称矩阵精确隔离特征根并累加绝对值，差区间分离0才给严格大小。同谱可证能量相等；未分离不作判断。'}
