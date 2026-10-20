"""Bounded JSON adapters for recurrence and integer-system calculations."""
from graph_research.algebra.recurrences import solve_linear_recurrence
from graph_research.algebra.integer_systems import solve_integer_linear_system


def linear_recurrence(coefficients,initial_values,forcing=0,variable='n',start=0,terms=12):
    return solve_linear_recurrence(coefficients,initial_values,forcing,variable,int(start),int(terms))


def integer_linear_system(matrix,rhs,parameters=None):
    return solve_integer_linear_system([[int(value) for value in row] for row in matrix],rhs,parameters)


def symbolic_tool_definitions(obj):
    scalar={'anyOf':[{'type':'number','minimum':-10**12,'maximum':10**12},{'type':'string','minLength':1,'maxLength':1024}]}
    names={'type':'array','maxItems':8,'uniqueItems':True,'items':{'type':'string','pattern':r'^[A-Za-z][A-Za-z0-9_]{0,31}$'}}
    return [
        ('linear_recurrence','求解正则线性递推，返回精确序列项和经校验的闭式状态。',linear_recurrence,
         obj({'coefficients':{'type':'array','minItems':2,'maxItems':9,'items':scalar},
              'initial_values':{'type':'array','minItems':1,'maxItems':8,'items':scalar},'forcing':scalar,
              'variable':{'type':'string','pattern':r'^[A-Za-z][A-Za-z0-9_]{0,31}$'},
              'start':{'type':'integer','minimum':0,'maximum':128},'terms':{'type':'integer','minimum':1,'maximum':64}},['coefficients','initial_values'])),
        ('integer_linear_system','以Smith分解求整数线性方程的完整整数解族，支持整系数参数右端项及条件。',integer_linear_system,
         obj({'matrix':{'type':'array','minItems':1,'maxItems':12,'items':{'type':'array','minItems':1,'maxItems':12,
               'items':{'type':'integer','minimum':-10**9,'maximum':10**9}}},
              'rhs':{'type':'array','minItems':1,'maxItems':12,'items':scalar},'parameters':names},['matrix','rhs']))]
