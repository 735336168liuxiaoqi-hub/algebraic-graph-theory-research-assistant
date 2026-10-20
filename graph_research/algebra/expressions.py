"""A bounded arithmetic parser for mathematical data; never eval or sympify text."""
import ast
import keyword
import math
import re
from graph_research._lazy import sympy as sp


def integer_symbols(names):
    names=list(names or [])
    if len(names)>8 or any(not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',name) or keyword.iskeyword(name) or name in ('factorial','binomial') for name in names) or len(set(names))!=len(names):
        raise ValueError('参数名须唯一，使用字母开头的名称，至多8个。')
    return {name:sp.Symbol(name,integer=True) for name in names}


def arithmetic_expression(value,symbols=None,*,functions=False):
    """Parse rational arithmetic and declared symbols; ^ is accepted as a power."""
    symbols=symbols or {}
    if isinstance(value,bool):raise ValueError('数学表达式不能使用布尔值。')
    if isinstance(value,sp.Basic):
        if any(str(symbol) not in symbols for symbol in value.free_symbols):raise ValueError('表达式包含未声明的符号。')
        return value.xreplace({symbol:symbols[str(symbol)] for symbol in value.free_symbols})
    if isinstance(value,(int,float)):
        if abs(value)>10**12 or not math.isfinite(value):raise ValueError('数值须有限且绝对值不超过10^12。')
        return sp.Rational(str(value))
    if not isinstance(value,str) or not value.strip() or len(value)>1024:raise ValueError('表达式应为至多1024字符的算式。')
    try:tree=ast.parse(value.replace('^','**'),mode='eval')
    except (SyntaxError,ValueError):raise ValueError('算式格式无效。') from None
    if sum(1 for _ in ast.walk(tree))>128:raise ValueError('算式过于复杂。')
    def convert(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return arithmetic_expression(node.value)
        if isinstance(node,ast.Name) and node.id in symbols:return symbols[node.id]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            result=convert(node.operand);return result if isinstance(node.op,ast.UAdd) else -result
        if isinstance(node,ast.BinOp):
            left,right=convert(node.left),convert(node.right)
            if isinstance(node.op,ast.Add):return left+right
            if isinstance(node.op,ast.Sub):return left-right
            if isinstance(node.op,ast.Mult):return left*right
            if isinstance(node.op,ast.Div):return left/right
            if isinstance(node.op,ast.Pow):
                if right.is_number and (right.is_Integer is not True or abs(right)>32):raise ValueError('数值幂指数须为-32到32的整数。')
                if not right.is_number and not functions:raise ValueError('此处不允许符号指数。')
                return left**right
        if functions and isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            allowed={'factorial':(sp.factorial,1),'binomial':(sp.binomial,2)}
            if node.func.id in allowed:
                function,length=allowed[node.func.id]
                if len(node.args)==length:
                    args=[convert(arg) for arg in node.args]
                    if any(arg.is_number and (arg.is_Integer is not True or not 0<=arg<=128) for arg in args):raise ValueError('函数的数值参数须为0到128的整数。')
                    return function(*args)
        raise ValueError('只接受算术、声明的符号及允许的数学函数；不执行Python代码。')
    result=convert(tree.body)
    if result.has(sp.zoo,sp.oo,-sp.oo,sp.nan):raise ValueError('算式包含除零或非有限值。')
    return result
