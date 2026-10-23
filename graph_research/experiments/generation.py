"""Bounded legal hypertree construction; no objective optimization."""
import random


def generate_hypertree(k,m,*,seed=42,degree_cap=None):
    """Attach k-1 new vertices per edge, preserving an incidence tree.

    degree_cap is an upper bound, not a promise of exact maximum degree or its
    multiplicity. Those conditions must be checked by the experiment adapter.
    """
    if type(k) is not int or not 2<=k<=128 or type(m) is not int or not 0<=m<=128 or 1+(k-1)*m>128:
        raise ValueError('一致超树生成要求2<=k<=128、m>=0、总顶点数<=128。')
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('种子范围无效。')
    if degree_cap is not None and (type(degree_cap) is not int or not 0<=degree_cap<=128):raise ValueError('最大度上限无效。')
    rng=random.Random(seed);edges=[];degrees=[0]
    for _ in range(m):
        eligible=[v for v,d in enumerate(degrees) if degree_cap is None or d<degree_cap]
        if not eligible:raise ValueError('在该度上限下不能继续生长；未放宽约束。')
        parent=rng.choice(eligible);fresh=list(range(len(degrees),len(degrees)+k-1))
        edges.append([parent,*fresh]);degrees[parent]+=1;degrees.extend([1]*(k-1))
    return {'n':len(degrees),'edges':edges}
