"""Whitelisted symbolic analysis, with explicit undecided/conditional results."""
import ast
import keyword
import re
from graph_research._lazy import sympy as sp
from graph_research.algebra.expressions import arithmetic_expression

_FUNCTION_NAMES=('sin','cos','tan','exp','log','sqrt','Abs','factorial','binomial')
_functions_cache=None


def _functions():
    # Build the whitelist table on first use, keeping sympy lazy at import.
    global _functions_cache
    if _functions_cache is None:_functions_cache={n:getattr(sp,n) for n in _FUNCTION_NAMES}
    return _functions_cache


def mathematical_expression(value,symbols):
    """Parse arithmetic and named math calls; never execute source expressions."""
    if not isinstance(value,str):return arithmetic_expression(value,symbols)
    if not value.strip() or len(value)>1024:raise ValueError('表达式须为1..1024字符。')
    try:tree=ast.parse(value.replace('^','**'),mode='eval')
    except (SyntaxError,ValueError):raise ValueError('表达式语法无效。') from None
    if len(list(ast.walk(tree)))>128:raise ValueError('表达式过于复杂。')
    def convert(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return arithmetic_expression(node.value)
        if isinstance(node,ast.Name) and node.id in symbols:return symbols[node.id]
        if isinstance(node,ast.Name) and node.id in ('pi','E'):return sp.pi if node.id=='pi' else sp.E
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            term=convert(node.operand);return term if isinstance(node.op,ast.UAdd) else -term
        if isinstance(node,ast.BinOp):
            left,right=convert(node.left),convert(node.right)
            if isinstance(node.op,ast.Add):return left+right
            if isinstance(node.op,ast.Sub):return left-right
            if isinstance(node.op,ast.Mult):return left*right
            if isinstance(node.op,ast.Div):return left/right
            if isinstance(node.op,ast.Pow):
                if right.is_number and (right.is_Rational is not True or abs(right)>32 or right.q>16):raise ValueError('数值指数须为绝对值≤32、分母≤16的有理数。')
                return left**right
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in _functions() and not node.keywords:
            name=node.func.id;args=[convert(arg) for arg in node.args]
            if len(args)!=(2 if name=='binomial' else 1):raise ValueError('数学函数参数数目不符。')
            if name in ('factorial','binomial') and any(arg.is_number and (arg.is_Integer is not True or not 0<=arg<=128) for arg in args):raise ValueError('阶乘/二项式数值参数限0..128整数。')
            return _functions()[name](*args)
        raise ValueError('只接受声明变量、算术及白名单数学函数。')
    result=convert(tree.body)
    if result.has(sp.zoo,sp.oo,-sp.oo,sp.nan):raise ValueError('输入表达式非有限；无穷端点只在求和上界填写oo。')
    return result


def symbolic_analysis(operation,expression,variable='x',parameters=None,lower=0,upper=10,center=0,order=6):
    """Sum or locally expand; unevaluated results are not claimed as solved."""
    names=[variable,*list(parameters or [])]
    if len(names)>9 or len(set(names))!=len(names) or any(not isinstance(name,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,31}',name) or keyword.iskeyword(name) or name in (*_functions(),'pi','E','oo') for name in names):raise ValueError('变量/参数名须互异，不得占用函数或常量名。')
    symbols={name:sp.Symbol(name,integer=True) if operation=='summation' else sp.Symbol(name) for name in names}
    x=symbols[variable];expr=mathematical_expression(expression,symbols)
    if operation=='summation':
        lo=mathematical_expression(lower,symbols);hi=sp.oo if upper=='oo' else mathematical_expression(upper,symbols)
        if lo.has(x) or hi.has(x) or lo.is_integer is not True or (hi!=sp.oo and hi.is_integer is not True):raise ValueError('求和界限须为不含下标变量的整数表达式，上界可为oo。')
        if lo.is_number and hi.is_number and hi!=sp.oo and (hi<lo or hi-lo>10000):raise ValueError('数值区间须有序且跨度≤10000。')
        requested=sp.Sum(expr,(x,lo,hi));value=requested.doit()
        condition=sp.true if hi==sp.oo else sp.Ge(hi,lo)
        status='unevaluated' if value.has(sp.Sum) else 'divergent' if value.has(sp.oo,-sp.oo,sp.zoo,sp.nan) else 'conditional' if value.has(sp.Piecewise) or condition is not sp.true else 'evaluated'
        return {'status':status,'expression':str(expr),'requested':str(requested),'result':str(value),'latex':sp.latex(value),
                'conditions':[] if condition is sp.true else [str(condition)],
                'interpretation':'整数下标包含两端；有限和要求上界不小于下界，符号界限保留该条件，不使用倒置界限的有向和解释。条件分支及无穷求和条件必须保留。'}
    if operation!='series':raise ValueError('operation为summation或series。')
    point=mathematical_expression(center,{})
    if point.is_real is not True or type(order) is not int or not 1<=order<=16:raise ValueError('展开中心须为有限实数，阶数1..16。')
    value=sp.series(expr,x,point,order)
    return {'status':'unevaluated' if value.has(sp.Sum) else 'expanded','expression':str(expr),'center':str(point),'expansion_order':order,
            'result':str(value),'truncated':str(value.removeO()),'remainder':str(value.getO()),'latex':sp.latex(value),
            'interpretation':'局部展开保留O项，可为Laurent/广义级数；不声明全局收敛范围。'}
