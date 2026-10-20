"""Integer linear systems using exact Smith transformations, never rational relaxation."""
from graph_research._lazy import sympy as sp
from .expressions import arithmetic_expression,integer_symbols


def solve_integer_linear_system(matrix,rhs,parameters=None):
    """Solve A*x=b over integers for constant integer A and polynomial integer b.

    Symbolic RHS parameters are integers. Return conditions, one particular
    vector and a full integer nullspace basis; no_solution is distinguished
    from a solution that exists only under divisibility/zero-row conditions.
    """
    from sympy.polys.matrices import DomainMatrix
    from sympy.polys.matrices.normalforms import smith_normal_decomp
    rows=matrix.tolist() if isinstance(matrix,sp.MatrixBase) else [list(row) for row in matrix]
    if not rows or not 1<=len(rows)<=12 or not 1<=len(rows[0])<=12 or any(len(row)!=len(rows[0]) for row in rows):
        raise ValueError('系数矩阵须为规则的1..12行列矩阵。')
    parsed=[[arithmetic_expression(value) for value in row] for row in rows]
    parsed=[[sp.Rational(str(value)) if value.is_Float else value for value in row] for row in parsed]
    a=sp.Matrix(parsed)
    if not 1<=a.rows<=12 or not 1<=a.cols<=12 or any(value.is_Integer is not True or abs(value)>10**9 for value in a):
        raise ValueError('系数矩阵须为1..12行列、绝对值不超过10^9的整数矩阵。')
    values=list(rhs)
    if len(values)!=a.rows:raise ValueError('右端项长度须等于矩阵行数。')
    if parameters is None:
        parameters=sorted({str(symbol) for value in values if isinstance(value,sp.Basic) for symbol in value.free_symbols})
    symbols=integer_symbols(parameters)
    expressions=[arithmetic_expression(value,symbols) for value in values]
    for expression in expressions:
        if not symbols:
            valid=expression.is_Integer is True
        else:
            try:polynomial=sp.Poly(expression,*symbols.values(),domain=sp.ZZ);valid=polynomial.total_degree()<=8
            except (sp.PolynomialError,sp.CoercionFailed):valid=False
        if not valid:raise ValueError('右端项须为整数或已声明整数参数的整系数多项式（次数≤8）。')
    b=sp.Matrix(expressions);domain=DomainMatrix.from_Matrix(a).convert_to(sp.ZZ)
    diagonal,left,right=smith_normal_decomp(domain);d,s,t=[item.to_Matrix() for item in (diagonal,left,right)]
    if d!=s*a*t:raise ArithmeticError('Smith分解校验失败。')
    c=s*b;rank=sum(d[i,i]!=0 for i in range(min(a.shape)));conditions=[];y=sp.zeros(a.cols,1)
    for i in range(a.rows):
        condition=sp.Eq(sp.Mod(c[i],abs(d[i,i])),0) if i<rank else sp.Eq(c[i],0)
        if condition is sp.false:
            return {'status':'no_solution','rank':rank,'domain':'integers','conditions':[],
                    'reason':f'Smith变换后第{i}行不满足整除或零行条件。','smith_diagonal':[str(d[j,j]) for j in range(min(a.shape))]}
        if condition is not sp.true:conditions.append(str(condition))
        if i<rank:y[i]=sp.cancel(c[i]/d[i,i])
    particular=t*y;kernel=t[:,rank:];free=sp.symbols(f'_t0:{a.cols-rank}',integer=True)
    solution=particular+kernel*sp.Matrix(len(free),1,free)
    if a*kernel!=sp.zeros(a.rows,kernel.cols):raise ArithmeticError('整数零空间校验失败。')
    return {'status':'conditional' if conditions else 'solved','domain':'integers','rank':rank,
            'conditions':conditions,'parameters':list(symbols),'particular':list(map(str,particular)),
            'kernel_basis':[[str(kernel[i,j]) for j in range(kernel.cols)] for i in range(kernel.rows)],
            'free_parameters':list(map(str,free)),'solution':list(map(str,solution)),
            'smith_diagonal':[str(d[i,i]) for i in range(min(a.shape))],
            'smith_decomposition_verified':True,'kernel_verified':True,
            'interpretation':'自由参数及输入参数均取整数；conditional仅在列出的条件同时成立时有解。'}
