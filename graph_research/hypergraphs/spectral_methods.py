"""Budgeted two-block equitable reduction, expanded and independently checked."""
import math
import numpy as np


def two_block_spectrum(graph,alpha,tolerance,max_iterations):
    """Try a cheap degree partition. Never enumerate graph automorphisms.

    For two equitable blocks the first ratio is nondecreasing in x1/x0,
    the second nonincreasing. Solve their log difference by bracket/bisection.
    None means structural inapplicability, never a claimed numerical result.
    """
    from .quotients import OrbitQuotient
    if graph.vertex_degrees is not None or not np.all(graph.weights==1):return None
    groups={}
    for v in graph.Vertices:groups.setdefault(graph.degree(v),[]).append(v)
    if len(groups)!=2:return None
    try:quotient=OrbitQuotient(graph,list(groups.values()))
    except ValueError:return None
    def log_ratio(i,s):
        total=-math.inf
        if alpha and quotient.vertex_degrees[i]:total=math.log(alpha*quotient.vertex_degrees[i])
        for powers,c in quotient.rows[i].items():
            power=powers[1]-(graph.rank-1 if i==1 else 0)
            term=math.log1p(-alpha)+math.log(c)+power*s
            total=float(np.logaddexp(total,term))
        return total
    bound=650/max(1,graph.rank-1);left=-bound;right=bound
    if log_ratio(0,left)>log_ratio(1,left) or log_ratio(0,right)<log_ratio(1,right):return None
    limit=min(max_iterations,256)
    for iteration in range(1,limit+1):
        middle=(left+right)/2;first=log_ratio(0,middle);second=log_ratio(1,middle)
        rho=math.exp((first+second)/2)
        if abs(first-second)<=tolerance*.25:break
        if first>second:right=middle
        else:left=middle
    else:raise ArithmeticError('Two-block root solver unresolved within iteration budget')
    values=[1.,math.exp(middle)];membership={v:i for i,b in enumerate(quotient.blocks) for v in b}
    vector=np.array([values[membership[v]] for v in graph.Vertices]);vector/=vector.sum()
    return {'rho':rho,'perron_vector':vector.tolist(),'vertex_order':graph.vertices(),'alpha':float(alpha),
            'iterations':iteration,'method':'equitable_two_block_bisection','equitable_blocks':quotient.blocks,
            'initialization':'bracketed_log_ratio','stop_reason':'ratio_agreement'}
