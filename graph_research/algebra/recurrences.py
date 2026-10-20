"""Regular univariate rational-coefficient recurrences and exact sequence values."""
from graph_research._lazy import sympy as sp
from .expressions import arithmetic_expression,integer_symbols


def solve_linear_recurrence(coefficients,initial_values,forcing=0,variable='n',start=0,terms=12):
    """Solve sum(c[i](n)*a(n+i))=forcing(n), n>=start, order 1..8.

    Require one rational initial value per order and no leading zeros/poles
    at integer n>=start. A missing closed form is not a proof of nonexistence;
    the exact recurrence-generated terms remain available.
    """
    if type(start) is not int or start<0 or type(terms) is not int or not 1<=terms<=64:raise ValueError('start须为非负整数，terms须为1..64。')
    n=integer_symbols([variable])[variable];scope={variable:n};coefficients=list(coefficients);order=len(coefficients)-1
    if not 1<=order<=8 or len(initial_values)!=order:raise ValueError('递推阶数须为1..8，且每阶需要一个连续初值。')
    c=[arithmetic_expression(value,scope) for value in coefficients]
    if c[-1]==0:raise ValueError('最高移位项的系数不能为零。')
    for expression in c:
        if not expression.is_rational_function(n):raise ValueError('递推系数须为n的有理函数。')
        numerator,denominator=sp.cancel(expression).as_numer_denom()
        for polynomial in (numerator,denominator):
            try:p=sp.Poly(polynomial,n,domain=sp.QQ)
            except (sp.PolynomialError,sp.CoercionFailed):raise ValueError('系数须为有理数域上的有理函数。') from None
            if p.degree()>8:raise ValueError('系数的分子、分母次数须≤8。')
        for root in sp.Poly(denominator,n,domain=sp.QQ).ground_roots():
            if root.is_Integer and root>=start:raise ValueError(f'系数在n={root}处有极点，请调整起点或单独分析。')
    for root in sp.Poly(sp.cancel(c[-1]).as_numer_denom()[0],n,domain=sp.QQ).ground_roots():
        if root.is_Integer and root>=start:raise ValueError(f'最高移位系数在n={root}处为零，暂不支持奇异递推。')
    f=arithmetic_expression(forcing,scope,functions=True)
    if any(term!=0 and term.is_hypergeometric(n) is not True for term in sp.Add.make_args(f)):
        raise ValueError('右端项须为超几何项或有限个此类项之和，例如n、2^n、factorial(n)。')
    for term in sp.Add.make_args(f):
        denominator=sp.together(term).as_numer_denom()[1]
        if denominator.is_polynomial(n):
            for root in sp.Poly(denominator,n).ground_roots():
                if root.is_Integer and root>=start:raise ValueError(f'右端项在n={root}处有极点。')
    for atom in f.atoms(sp.factorial):
        argument=sp.Poly(atom.args[0],n)
        if argument.degree()>1 or argument.eval(start)<0 or (argument.degree()==1 and argument.LC()<0):
            raise ValueError('factorial的自变量须在递推下标范围内始终为非负整数。')
    initial=[arithmetic_expression(value) for value in initial_values]
    if any(value.is_Rational is not True for value in initial):raise ValueError('初值须为精确有理数。')
    sequence=list(initial)
    for i in range(start,start+max(0,terms-order)):
        value=sp.cancel((f.subs(n,i)-sum(c[j].subs(n,i)*sequence[i-start+j] for j in range(order)))/c[-1].subs(n,i))
        if value.has(sp.zoo,sp.oo,-sp.oo,sp.nan):raise ValueError(f'递推在n={i}处产生非有限值。')
        sequence.append(value)
    function=sp.Function('a');equation=sum(c[i]*function(n+i) for i in range(order+1))-f
    try:closed=sp.rsolve(equation,function(n),{function(start+i):value for i,value in enumerate(initial)})
    except (NotImplementedError,ValueError,ZeroDivisionError):closed=None
    verified=False
    if closed is not None:
        residual=sp.simplify(sum(c[i]*closed.subs(n,n+i) for i in range(order+1))-f)
        verified=residual==0 and all(sp.simplify(closed.subs(n,start+i)-value)==0 for i,value in enumerate(initial))
    return {'status':'verified_closed_form' if verified else 'unverified_closed_form' if closed is not None else 'terms_only',
            'recurrence_order':order,'variable':variable,'start':start,'solution':str(closed) if closed is not None else None,
            'recurrence_verified':verified,'terms':[str(value) for value in sequence[:terms]],
            'equation':str(sp.Eq(sum(c[i]*function(n+i) for i in range(order+1)),f)),
            'interpretation':'coefficients[i]对应a(n+i)；terms从start开始，精确递推生成。未找到闭式不表示无解。'}
