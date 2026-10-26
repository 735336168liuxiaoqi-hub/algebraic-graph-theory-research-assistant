"""One explicit weighted/complex graph -> matrix -> spectrum workflow."""
import math
import numpy as np
from graph_research._lazy import sympy as sp


def _complex(value):
    if isinstance(value,dict):
        if set(value)!={'real','imag'}:raise ValueError('复权使用{real,imag}，不接受代码字符串。')
        real,imag=value['real'],value['imag']
    else:real,imag=value,0
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or abs(v)>10**6 or not math.isfinite(v) for v in (real,imag)):
        raise ValueError('边权实部与虚部须为绝对值不超过10^6的有限数。')
    return complex(real,imag),sp.Rational(str(real))+sp.I*sp.Rational(str(imag))


def weighted_matrices(n,edges,directed=False,matrix='A',alpha=0,degree_mode='absolute'):
    """Undirected complex edges use conjugate reverse weights (Hermitian A).

    absolute degree means sum |w|; sum degree means sum w and requires real
    weights. Directed degrees always use outgoing arcs. Self-loops and duplicate
    assignments are rejected. Isolates remain as zero rows/columns.
    """
    if type(n) is not int or not 1<=n<=128 or type(directed) is not bool:raise ValueError('需要1..128个顶点和布尔方向标记。')
    if matrix not in ('A','L','Q','alpha') or degree_mode not in ('absolute','sum'):raise ValueError('未知矩阵或度约定。')
    if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not math.isfinite(alpha) or not 0<=alpha<=1:raise ValueError('alpha须为0..1的有限实数。')
    records=list(edges)
    if len(records)>2048:raise ValueError('至多2048条赋权边/弧。')
    a=np.zeros((n,n),dtype=complex);exact=sp.zeros(n);seen=set();canonical=[]
    for record in records:
        if not isinstance(record,dict) or set(record)!={'u','v','weight'}:raise ValueError('每条边为{u,v,weight}。')
        u,v=record['u'],record['v']
        if any(type(x) is not int or not 0<=x<n for x in (u,v)) or u==v:raise ValueError('端点须在0..n-1，且不允许自环。')
        key=(u,v) if directed else frozenset((u,v))
        if key in seen:raise ValueError('边/弧不能重复赋权；无向反向记录也是重复。')
        seen.add(key);weight,expression=_complex(record['weight'])
        if degree_mode=='sum' and weight.imag:raise ValueError('sum度约定只接受实权；复权请用absolute。')
        a[u,v]=weight;exact[u,v]=expression
        if not directed:a[v,u]=weight.conjugate();exact[v,u]=sp.conjugate(expression)
        canonical.append({'u':u,'v':v,'weight':record['weight']})
    degrees=np.abs(a).sum(axis=1) if degree_mode=='absolute' else a.real.sum(axis=1)
    exact_degrees=[sum((sp.Abs(exact[i,j]) if degree_mode=='absolute' else exact[i,j] for j in range(n)),sp.S.Zero) for i in range(n)]
    diagonal=np.diag(degrees);exact_diagonal=sp.diag(*exact_degrees)
    if matrix=='A':result,exact_result=a,exact
    elif matrix=='L':result,exact_result=diagonal-a,exact_diagonal-exact
    elif matrix=='Q':result,exact_result=diagonal+a,exact_diagonal+exact
    else:
        parameter=sp.Rational(str(alpha));result=alpha*diagonal+(1-alpha)*a;exact_result=parameter*exact_diagonal+(1-parameter)*exact
    return result,exact_result,degrees,canonical


def weighted_graph_spectrum(n,edges,directed=False,matrix='A',alpha=0,degree_mode='absolute',exact=False):
    """Complete numerical spectrum with eigenvalue-based residuals; optional exact charpoly.

    The spectral radius is max |lambda|, while residuals use the eigenvalue
    itself, including negative/complex dominant eigenvalues. Only Hermitian
    adjacency matrices label the modulus sum as graph energy. Other matrices
    retain spectral_modulus_sum; this is not the shifted Laplacian energy.
    """
    a,exact_matrix,degrees,canonical=weighted_matrices(n,edges,directed,matrix,alpha,degree_mode)
    if exact and n>8:raise ValueError('此精确特征多项式入口限8顶点；数值谱限128。')
    hermitian=bool(np.array_equal(a,a.conj().T))
    values,vectors=np.linalg.eigh(a) if hermitian else np.linalg.eig(a)
    order=sorted(range(n),key=lambda i:(-abs(values[i]),-float(values[i].real),-float(values[i].imag)))
    # Ties in |lambda| are common (roots of unity, +-lambda pairs) and floating
    # point noise must not decide which one is dominant: inside the maximal
    # modulus the largest real part wins, so the Perron root is reported when
    # it exists and the residual still belongs to the value that is returned.
    modulus=np.abs(values);peak=float(modulus.max()) if n else 0.0
    tied=[i for i in range(n) if modulus[i]>=peak-1e-9*max(1.0,peak)]
    dominant=max(tied,key=lambda i:(float(values[i].real),float(values[i].imag)))
    value=values[dominant];vector=vectors[:,dominant]
    scale=max(1.0,float(np.linalg.norm(a)))
    residuals=[float(np.linalg.norm(a@vectors[:,i]-values[i]*vectors[:,i])/(scale*np.linalg.norm(vectors[:,i]))) for i in range(n)]
    result={'order':n,'size':len(canonical),'directed':directed,'hermitian':hermitian,'matrix_type':matrix,
            'degree_mode':degree_mode,'degrees':degrees.tolist(),'matrix':a,'spectrum':values[order],
            'rho':float(abs(value)),'dominant_eigenvalue':value,'dominant_eigenvector':vector,
            'relative_residual':residuals[dominant],'max_relative_residual':max(residuals),
            'spectral_modulus_sum':float(np.abs(values).sum()),
            'graph_input':{'n':n,'edges':canonical,'directed':directed},
            'interpretation':'无向复权反向取共轭；absolute度为逐点出边权模之和，sum度仅用于实权。谱半径取特征值模。'}
    if hermitian and matrix=='A':result['energy']=result['spectral_modulus_sum']
    if exact:
        polynomial=exact_matrix.charpoly(sp.Symbol('x'))
        result.update(polynomial=str(polynomial.as_expr()),exact_matrix=[[str(v) for v in row] for row in exact_matrix.tolist()],arithmetic='exact decimal rationals and algebraic absolute degrees')
    return result
