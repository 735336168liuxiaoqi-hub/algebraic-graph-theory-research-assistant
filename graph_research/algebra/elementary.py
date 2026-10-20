"""SymPy elementary operations and explicit LaTeX, with no notebook side effects."""
import math
import numbers
import numpy as np
from graph_research._lazy import sympy as sp
from .expressions import arithmetic_expression


def _index(value):
    if isinstance(value,bool) or not isinstance(value,(numbers.Integral,sp.Integer)) or value<0:raise ValueError('索引须为非负整数。')
    return int(value)


def _scalar(value):
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,bool):raise ValueError('倍数不能是布尔值。')
    result=value if isinstance(value,sp.Expr) else arithmetic_expression(value)
    if result.has(sp.oo,-sp.oo,sp.zoo,sp.nan):raise ValueError('倍数须为有限表达式。')
    return result


def _action(action):
    values=list(action)
    if not values or values[0] not in ('r1','r2','r3','c1','c2','c3'):raise ValueError('操作须为r1/r2/r3/c1/c2/c3。')
    name=values[0];arity=4 if name[1]=='3' else 3
    if len(values)!=arity:raise ValueError('初等操作参数数量错误。')
    result=[name,_index(values[1])]
    result += [_scalar(values[2])] if name[1]=='2' else [_index(values[2])]
    if name[1]=='3':result.append(_scalar(values[3]))
    return result


def do_Actions(matrix,ops,repl=False):
    """Apply old r1/c1 swap, r2/c2 scale, r3/c3 add-multiple instructions.

    Zero scaling is allowed but is not invertible. With repl=True require a
    mutable SymPy Matrix and commit only after ALL instructions succeeded.
    """
    actions=[_action(action) for action in ops];result=sp.Matrix(matrix)
    if repl and not isinstance(matrix,sp.MutableMatrix):raise ValueError('原地更新需要可变SymPy Matrix。')
    for name,i,value,*extra in actions:
        size=result.rows if name[0]=='r' else result.cols
        if i>=size or (name[1]!='2' and value>=size):raise ValueError('行列索引超出范围。')
        method=result.elementary_row_op if name[0]=='r' else result.elementary_col_op
        prefix='row' if name[0]=='r' else 'col'
        if name[1]=='1':result=method('n<->m',**{prefix+'1':i,prefix+'2':value})
        elif name[1]=='2':result=method('n->kn',**{prefix:i,'k':value})
        else:result=method('n->n+km',**{prefix+'1':i,prefix+'2':value,'k':extra[0]})
    if repl:matrix[:,:]=result;return matrix
    return result


def el_rop2(matrix,c,repl=False):
    """Scale row (index,multiple), return Matrix instead of Sage rich display."""
    return do_Actions(matrix,[('r2',*c)],repl)


def el_rop3(matrix,c,repl=False):
    """Add row (target,source,multiple), returning a Matrix."""
    return do_Actions(matrix,[('r3',*c)],repl)


def el_cop2(matrix,c,repl=False):
    """Scale column (index,multiple), returning a Matrix."""
    return do_Actions(matrix,[('c2',*c)],repl)


def el_cop3(matrix,c,repl=False):
    """Add column (target,source,multiple), returning a Matrix."""
    return do_Actions(matrix,[('c3',*c)],repl)


def _latex(value,determinant=False):
    if isinstance(value,str):return value
    if isinstance(value,sp.MatrixBase) or isinstance(value,(list,tuple,np.ndarray)):
        return sp.latex(sp.Matrix(value),mat_delim=None if determinant else '(',mat_str='vmatrix' if determinant else 'matrix')
    return sp.latex(value)


def lst2ltx(values,Det=False):
    """Join literal strings and SymPy LaTeX, without changing global delimiters."""
    return ''.join(_latex(value,Det) for value in values)


def sum_hold(values,Det=True):
    """Render unevaluated displayed sums; no algebraic terms are combined."""
    return '+'.join(_latex(value,Det) for value in values) or '0'


def split_vector(vector):
    """Decompose a row/column vector into single-nonzero column vectors."""
    values=sp.Matrix(vector)
    if values.rows>1 and values.cols>1:raise ValueError('需要向量，不是二维矩阵。')
    flat=list(values);result=[]
    for i,value in enumerate(flat):
        if value!=0:
            part=sp.zeros(len(flat),1);part[i]=value;result.append(part)
    return result


def split_row(matrix,i,Ls,disp=True):
    """Determinant row linearity, including the exact remainder row.

    disp=True returns LaTeX text; False returns [original,*term_matrices].
    It does not open a display or mutate the input matrix.
    """
    a=sp.Matrix(matrix);i=_index(i)
    if a.rows!=a.cols or i>=a.rows:raise ValueError('拆行行列式需要方阵和有效行序号。')
    rows=[list(row) for row in Ls]
    if any(len(row)!=a.cols for row in rows):raise ValueError('每个拆分向量须与原矩阵列数相同。')
    terms=[sp.Matrix(1,a.cols,row) for row in rows]
    terms.append(a[i,:]-sum(terms,sp.zeros(1,a.cols)));matrices=[]
    for row in terms:
        piece=a.copy();piece[i,:]=row;matrices.append(piece)
    return lst2ltx([a,'=',sum_hold(matrices)],Det=True) if disp else [a,*matrices]


def Op_links(ops):
    """LaTeX arrow annotations for elementary instructions, indices displayed from 1."""
    labels=[]
    for name,i,value,*extra in map(_action,ops):
        axis='r' if name[0]=='r' else 'c';target=f'{axis}_{{{i+1}}}'
        if name[1]=='1':text=target+r'\leftrightarrow '+f'{axis}_{{{value+1}}}'
        elif name[1]=='2':text=target+r'\leftarrow ('+sp.latex(value)+')'+target
        else:text=target+r'\leftarrow '+target+'+('+sp.latex(extra[0])+f'){axis}_{{{value+1}}}'
        labels.append(text)
    return r'\xrightarrow{\substack{'+r'\\'.join(labels)+'}}' if labels else '='


def do_show_ops(matrix,ops):
    """Return original/arrow/result LaTeX; unlike Sage, no implicit mutation."""
    actions=list(ops)
    return _latex(sp.Matrix(matrix))+Op_links(actions)+_latex(do_Actions(matrix,actions))


def show_equtions(equsys):
    """Equation-system LaTeX (retains the historic misspelling in this alias)."""
    lines=[sp.latex(eq.lhs)+'&='+sp.latex(eq.rhs) if isinstance(eq,sp.Equality) else sp.latex(eq)+'&=0' for eq in equsys]
    return r'\left\{\begin{aligned}'+r'\\'.join(lines)+r'\end{aligned}\right.'


def stdequs(equsys):
    """Put affine linear equations in variable-part = constant form, exactly."""
    result=[]
    for equation in equsys:
        expression=sp.expand(equation.lhs-equation.rhs) if isinstance(equation,sp.Equality) else sp.expand(equation)
        variables=sorted(expression.free_symbols,key=str)
        if variables and sp.Poly(expression,*variables).total_degree()>1:raise ValueError('只支持线性方程。')
        constant=expression.subs({symbol:0 for symbol in variables})
        result.append(sp.Eq(expression-constant,-constant,evaluate=False))
    return result


def Mat2PR(matrix,R=None):
    """Exact DomainMatrix over base domain R and all free-symbol generators."""
    from sympy.polys.matrices import DomainMatrix
    if R is None:R=sp.QQ
    a=sp.Matrix(matrix);symbols=sorted(a.free_symbols,key=str)
    if R not in (sp.ZZ,sp.QQ):raise ValueError('此适配入口的基域支持ZZ/QQ。')
    domain=R.poly_ring(*symbols) if symbols else R
    return DomainMatrix.from_Matrix(a).convert_to(domain)


def _round(value,ndigits,eps):
    if isinstance(value,(numbers.Integral,sp.Integer)):return int(value)
    if isinstance(value,sp.Basic) and value.free_symbols:return value
    try:number=float(value)
    except (TypeError,ValueError,OverflowError):raise ValueError('舍入只支持有限实数及未处理的符号项。') from None
    if not math.isfinite(number):raise ValueError('舍入数值须有限。')
    candidate=round(number,ndigits)
    error=abs(sp.Rational(str(candidate))-value) if isinstance(value,sp.Number) else abs(candidate-number)
    if error>eps:return value
    return int(candidate) if candidate.is_integer() else candidate


def map_round(values,ndigits=8,eps=1e-10):
    """Round only within eps; preserve exact values when the threshold fails."""
    if type(ndigits) is not int or not -15<=ndigits<=15 or not math.isfinite(float(eps)) or eps<0:raise ValueError('需要有效舍入位数和非负有限误差。')
    if isinstance(values,sp.MatrixBase):return values.applyfunc(lambda value:_round(value,ndigits,eps))
    if isinstance(values,np.ndarray):return np.vectorize(lambda value:_round(value,ndigits,eps),otypes=[object])(values)
    return [_round(value,ndigits,eps) for value in values]


def matrix_round(matrix,ndigits=8,eps=1e-10):
    """Matrix version of tolerance-aware map_round; no source mutation."""
    return map_round(matrix if isinstance(matrix,(sp.MatrixBase,np.ndarray)) else sp.Matrix(matrix),ndigits,eps)
