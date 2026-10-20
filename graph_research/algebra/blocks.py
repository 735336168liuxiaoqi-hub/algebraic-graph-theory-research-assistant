"""Exact block extraction/permutation/multiplication and polynomial companions."""
from graph_research._lazy import sympy as sp
from graph_research.algebra.expressions import arithmetic_expression,integer_symbols


def _matrix(data,symbols):
    if not isinstance(data,list) or not data or len(data)>16 or not all(isinstance(row,list) and 1<=len(row)<=16 for row in data) or len({len(row) for row in data})!=1:raise ValueError('矩阵须为≤16×16的非空矩形数组。')
    return sp.Matrix([[arithmetic_expression(value,symbols) for value in row] for row in data])


def _partition(sizes,total):
    if not sizes or any(type(value) is not int or value<1 for value in sizes) or sum(sizes)!=total:raise ValueError('块尺寸须为正整数，且恰好覆盖对应轴。')
    boundaries=[0]
    for value in sizes:boundaries.append(boundaries[-1]+value)
    return list(zip(boundaries,boundaries[1:]))


def block_matrix_analysis(operation,matrix=None,row_sizes=None,column_sizes=None,row_order=None,column_order=None,right=None,polynomials=None,parameters=None):
    """Companions have subdiagonal ones and negative coefficients in last column.

    diag(C(p1),...) has characteristic polynomial prod(pi), with every input
    normalized to monic. This is a construction, not a Jordan decomposition.
    """
    symbols=integer_symbols(parameters)
    if operation=='companion_blocks':
        if not polynomials or len(polynomials)>8:raise ValueError('需要1..8组多项式系数。')
        blocks=[];monics=[];x=sp.Symbol('x')
        if 'x' in symbols:raise ValueError('伴随块保留x为多项式变量，参数请用其他名称。')
        if any(len(values)<2 or len(values)>9 for values in polynomials) or sum(len(values)-1 for values in polynomials)>16:raise ValueError('各多项式次数1..8，总次数≤16。')
        for values in polynomials:
            coefficients=[arithmetic_expression(value,symbols) for value in values]
            # A symbolic leading coefficient may vanish: require an explicit nonzero rational.
            if coefficients[0].is_Rational is not True or coefficients[0]==0:raise ValueError('首项系数须为显式非零有理数。')
            coefficients=[value/coefficients[0] for value in coefficients];n=len(values)-1;c=sp.zeros(n)
            for i in range(1,n):c[i,i-1]=1
            for i,value in enumerate(reversed(coefficients[1:])):c[i,n-1]=-value
            blocks.append(c);monics.append(sum(coefficient*x**(n-i) for i,coefficient in enumerate(coefficients)))
        result=sp.diag(*blocks);expected=sp.prod(monics);actual=result.charpoly(x).as_expr()
        return {'matrix':result,'blocks':blocks,'monic_polynomials':[str(poly) for poly in monics],'polynomial':str(actual),
                'verified':sp.expand(actual-expected)==0,'interpretation':'块对角伴随构造：次对角为1，最后一列为负的升幂系数；不是Jordan标准形。'}
    if matrix is None:raise ValueError('此分支需要matrix。')
    a=_matrix(matrix,symbols);rows=_partition(row_sizes,a.rows);columns=_partition(column_sizes,a.cols)
    if operation=='extract':return {'shape':list(a.shape),'blocks':[[a[r:s,c:d] for c,d in columns] for r,s in rows]}
    if operation=='permute':
        ro=list(range(len(rows))) if row_order is None else row_order;co=list(range(len(columns))) if column_order is None else column_order
        if sorted(ro)!=list(range(len(rows))) or sorted(co)!=list(range(len(columns))) or any(type(i) is not int for i in [*ro,*co]):raise ValueError('行/列块序须为从0开始的完整排列。')
        ri=[i for group in ro for i in range(*rows[group])];ci=[i for group in co for i in range(*columns[group])]
        return {'matrix':a.extract(ri,ci),'row_indices':ri,'column_indices':ci}
    if operation!='multiply' or right is None:raise ValueError('分支extract/permute/multiply/companion_blocks；multiply需要right。')
    b=_matrix(right,symbols)
    if a.cols!=b.rows:raise ValueError('矩阵乘法内维不匹配；column_sizes同时划分右矩阵的行。')
    partials=[[a[r:s,c:d]*b[c:d,:] for c,d in columns] for r,s in rows]
    result=sp.Matrix.vstack(*[sum(parts,sp.zeros(rows[i][1]-rows[i][0],b.cols)) for i,parts in enumerate(partials)])
    return {'matrix':result,'block_contributions':partials,'verified':result==a*b,'arithmetic':'exact'}
