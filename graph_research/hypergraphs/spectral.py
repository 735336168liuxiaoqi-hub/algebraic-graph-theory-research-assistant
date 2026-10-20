"""Functional hypergraphs.spectral implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp
from graph_research.runtime.observability import timed


class HypergraphSpectralMixin:
    def alpha_spectrum(self, alpha=0, tolerance=1e-11, max_iterations=20000, seed=42, initial_vector=None, method="auto"):
        """求一个正Perron特征对，不是全部张量谱。

        要求非空、连通、一致、正边权；alpha<1时连通，alpha=1为度对角端点。返回rho、按vertex_order
        排列且L1归一化的perron_vector、独立relative_residual、Collatz上下界
        及迭代信息。默认auto，支持稳定移位幂法及保正Newton–Noda；后者
        按需60位精化，高α延拓与重试共享总预算。失败不返回未收敛近似。谱半径实验
        不是数学证明。若要精确多项式，使用characteristic_polynomial。

        tolerance是迭代求解器的收敛判据（残差低于它即停止），不是误差界；
        实际残差看achieved_tolerance，可信区间看verification.lower/upper
        （有理数证书），auto结果的方法间一致性看method_consistency。
        """
        k = self.uniform()
        if not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
            raise ValueError("alpha must be in [0,1]")
        if not 0 < tolerance < 1 or type(max_iterations) is not int or max_iterations < 1:
            raise ValueError("Invalid convergence controls")
        if method not in ('iteration','auto','newton_noda'):raise ValueError('method must be iteration, auto or newton_noda')
        if alpha==1:
            degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
            return self._verified_spectrum({'rho':float(max(degrees)),'perron_vector':None,'vertex_order':self.vertices(),
                'alpha':1.0,'degree_diagonal':degrees.tolist(),'max_degree':float(max(degrees)),'min_degree':float(min(degrees)),
                'iterations':0,'relative_residual':None,'method':'degree_diagonal','stop_reason':'diagonal_endpoint',
                'positive_perron_vector_guaranteed':False},tolerance)
        if not self.is_connected():
            raise ValueError("Positive Perron solver requires a connected hypergraph")
        if initial_vector is not None:
            initial_vector=np.asarray(initial_vector,dtype=float)
            if initial_vector.shape!=(self.order(),) or not np.isfinite(initial_vector).all() or np.any(initial_vector<=0):raise ValueError('initial_vector must match vertex_order and be finite/positive')
        if method=='auto':
            from .spectral_methods import two_block_spectrum
            reduced=two_block_spectrum(self,float(alpha),tolerance,max_iterations)
            if reduced is not None:
                reduced['initial_vector_used']=False
                return self._verified_spectrum(reduced,tolerance,cross_check=True)
        if method=='newton_noda' or (method=='auto' and alpha>.8):
            from .newton_noda import newton_noda_spectrum
            return self._verified_spectrum(newton_noda_spectrum(self,float(alpha),tolerance,max_iterations,seed,initial_vector),tolerance,
                                           cross_check=(method=='auto'))
        adjacency_degrees = self.incidence_matrix()@self.weights
        degrees = adjacency_degrees if self.vertex_degrees is None else self.vertex_degrees
        rng = np.random.default_rng(seed)
        x = rng.uniform(0.5, 1, self.order()) if initial_vector is None else initial_vector.copy()
        x /= x.max();x /= x.sum()
        from .newton_noda import _LogAction
        action=_LogAction(self,float(alpha))
        power_budget=min(128,max_iterations) if method=='auto' else max_iterations
        for iteration in range(1, power_budget+1):
            with np.errstate(over="raise", divide="raise", invalid="raise"):
                logq,_=action.evaluate(x)
                scale=float(logq.max());scaled_lower=math.exp(float(logq.min())-scale)
                try:upper=math.exp(scale)
                except OverflowError:upper=math.inf
                lower=upper*scaled_lower;rho=upper*(1+scaled_lower)/2
                residual=(1-scaled_lower)/(1+scaled_lower) if rho>=1 else (upper-lower)/2
                if residual <= tolerance:
                    break
                logx=np.log(x)+np.logaddexp(logq,0)/(k-1)
                x=np.exp(logx-float(np.logaddexp.reduce(logx)))
        else:
            if method=='auto' and power_budget<max_iterations:
                from .newton_noda import newton_noda_spectrum
                result=newton_noda_spectrum(self,float(alpha),tolerance,max_iterations-power_budget,seed,x)
                result['iterations']+=power_budget;result['initialization']='power_warm_start'
                result['solver_diagnostics'].update(power_warmup_iterations=power_budget,iterations=result['iterations'])
                return self._verified_spectrum(result,tolerance,cross_check=True)
            raise ArithmeticError(f"Perron solver did not converge after {max_iterations} iterations")
        # Reconstruct residual independently vertex-by-vertex from edge lists.
        independent = []
        for i, v in enumerate(self.Vertices):
            logadj=-math.inf
            for w,e in zip(self.weights,self.Edges):
                if v in e:
                    term=math.log(float(w))+math.fsum(math.log(float(x[self._index[u]])) for u in e if u!=v)-(k-1)*math.log(float(x[i]))
                    logadj=float(np.logaddexp(logadj,term))
            independent.append(alpha*float(degrees[i])+math.exp(math.log1p(-alpha)+logadj))
        checked_residual = max(abs(q-rho) for q in independent)/max(1, abs(rho))
        if not math.isfinite(checked_residual) or checked_residual > max(tolerance*1.01, 1e-13):
            raise ArithmeticError("Independent eigen-equation check failed")
        return self._verified_spectrum({"rho": rho, "perron_vector": x.tolist(), "relative_residual": checked_residual,
                "collatz_lower": min(independent), "collatz_upper": max(independent),
                "min_degree": float((alpha*degrees+(1-alpha)*adjacency_degrees).min()), "max_degree": float((alpha*degrees+(1-alpha)*adjacency_degrees).max()),
                "vertex_order": self.vertices(), "matrix_edge_order": [list(e) for e in self.Edges],
                "rank": k, "order": self.order(), "size": self.size(), "alpha": float(alpha),
                "seed": seed, "iterations": iteration, "backend": "native-python",
                "source_function": "graph_research.hypergraphs.Hypergraph.alpha_spectrum",
                "normalization": "A[e permutations] = weight/(k-1)!", "sources": [],
                "method":"shifted_power_iteration","initialization":"provided_vector" if initial_vector is not None else "seeded_random",
                "stop_reason":"residual_tolerance"},tolerance)

    @timed('spectral_verification')
    def _verified_spectrum(self,result,tolerance,cross_check=False):
        result.update(rank=self.uniform(),order=self.order(),size=self.size(),backend='native-python')
        adjacent=self.incidence_matrix()@self.weights
        diagonal=adjacent if self.vertex_degrees is None else self.vertex_degrees
        rows=result['alpha']*diagonal+(1-result['alpha'])*adjacent
        result.setdefault('min_degree',float(min(rows)));result.setdefault('max_degree',float(max(rows)))
        result.setdefault('matrix_edge_order',[list(e) for e in self.Edges])
        result.setdefault('normalization','A[e permutations] = weight/(k-1)!; vector L1')
        result.setdefault('source_function','graph_research.hypergraphs.Hypergraph.alpha_spectrum')
        from .spectral_certificate import verify_spectrum_certificate
        if self.order()<=128 and self.size()<=128 and self.rank<=8:
            checked=verify_spectrum_certificate(self.hyperedges(),result,weights=self.weights.tolist(),
                vertex_degrees=self.vertex_degrees.tolist() if self.vertex_degrees is not None else None,tolerance=tolerance,vertices=self.vertices())
            if not checked['passed']:raise ArithmeticError('Independent rational certificate failed')
            result['verification']=checked
            if result['alpha']<1:
                result.update(relative_residual=checked['relative_residual'],collatz_lower=checked['lower'],collatz_upper=checked['upper'])
        else:result['verification']={'level':'not_checked','reason':'independent checker size budget exceeded','passed':None}
        result['achieved_tolerance']=result.get('relative_residual')
        if cross_check:result['method_consistency']=self._cross_check_iteration(result,tolerance)
        return result

    def _cross_check_iteration(self,result,tolerance):
        """One independent shifted-power probe: does the auto route agree?

        tolerance is a stopping criterion, not an error bound; agreement between
        independent methods is the practical signal, the certificate interval is
        the rigorous one. Probe failure never discards the primary result.
        """
        try:
            probe=self.alpha_spectrum(result['alpha'],tolerance=tolerance,max_iterations=512,
                                      seed=result.get('seed',42),method='iteration')
        except Exception as exc:
            return {'checked':False,'reason':type(exc).__name__+': '+str(exc)}
        delta=abs(probe['rho']-result['rho'])
        return {'checked':True,'probe_method':probe['method'],'rho_delta':delta,
                'consistent':bool(delta<=max(10*tolerance,1e-10))}

    def Alpha_Spectral_Radius(self, alpha=0, edge_weighted=None, vertex_weighted=None, **kwargs):
        from graph_research.hypergraphs.model import Hypergraph
        graph=self
        if edge_weighted is False or vertex_weighted is False:
            graph=Hypergraph(self,weights=np.ones(self.size()) if edge_weighted is False else self.weights,
                             vertex_degrees=self.vertex_degrees)
            if vertex_weighted is False: graph.vertex_degrees=None
        result = graph.alpha_spectrum(alpha, **kwargs)
        return result["rho"], np.asarray(result["perron_vector"]) if result['perron_vector'] is not None else None

    def alpha_spectral_radius(self, alpha=0, **kwargs):
        return self.Alpha_Spectral_Radius(alpha, **kwargs)

    def WeightIncidenceMatrix(self, alpha=0, reduced=False, dig=None, edge_weighted=None, vertex_weighted=None, **kwargs):
        """Perron向量对应的赋权关联阵；行顶点、列超边。

        默认不舍入；dig指定显示舍入位数。reduced仅保留度>1的顶点行。
        独立D不等于实际加权度时尚不支持此关联标号，不能由谱可计算推断
        标号也可计算。其他前提及kwargs见alpha_spectrum。
        """
        from graph_research.hypergraphs.model import Hypergraph
        graph=self
        if edge_weighted is False or vertex_weighted is False:
            graph=Hypergraph(self,weights=np.ones(self.size()) if edge_weighted is False else self.weights)
            if vertex_weighted is False: graph.vertex_degrees=None
        result = graph.alpha_spectrum(alpha, **kwargs)
        matrix=graph.weighted_incidence_from_result(result)
        if reduced: matrix=matrix[[i for i,v in enumerate(graph.Vertices) if graph.degree(v)>1],:]
        return np.round(matrix,dig) if dig is not None else matrix

    def weighted_incidence_from_result(self, result):
        """Construct Perron incidence labels in log space; never renormalize rows.

        Accept any finite positive scaling of the vertex vector. Unrepresentable
        positive entries fail explicitly rather than silently becoming zero/NaN.
        This validates shape/labels, not an arbitrary supplied eigenpair.
        """
        if result.get("alpha")==1 or result.get("perron_vector") is None:raise ValueError("Positive-vector incidence output is unavailable at alpha=1")
        if self.vertex_degrees is not None:
            actual=self.incidence_matrix()@self.weights
            if np.any(np.abs(self.vertex_degrees-actual)>8*np.finfo(float).eps*np.maximum(1,np.abs(actual))):
                raise ValueError("Incidence labeling for a separate vertex diagonal is not implemented; spectrum is available")
        x = np.asarray(result["perron_vector"],dtype=float)
        alpha, rho = float(result["alpha"]), float(result["rho"])
        if not math.isfinite(alpha) or not 0<=alpha<1 or not math.isfinite(rho) or rho<=0:
            raise ValueError('Finite alpha<1 and a positive finite rho are required')
        if result.get('vertex_order')!=self.vertices() or x.shape!=(self.order(),) or not np.isfinite(x).all() or np.any(x<=0):
            raise ValueError('Positive vector and matching vertex_order are required')
        logs=np.log(x);logs-=logs.max();logrho=math.log(rho);logeps=math.log1p(-alpha)
        matrix = np.zeros((self.order(), self.size()))
        for j, (e, weight) in enumerate(zip(self.Edges, self.weights)):
            logweight=math.log(float(weight));edge_sum=math.fsum(float(logs[self._index[v]]) for v in e)
            diagonal=math.log(alpha)+logweight if alpha else -math.inf
            for v in e:
                i = self._index[v]
                value_log=float(np.logaddexp(diagonal,logweight+logeps+edge_sum-self.uniform()*float(logs[i])))-logrho
                if value_log>math.log(np.finfo(float).max):raise ArithmeticError('Weighted incidence entry outside binary64 range')
                value=math.exp(value_log)
                if not math.isfinite(value) or value<=0:raise ArithmeticError('Weighted incidence entry outside binary64 range')
                matrix[i, j] = value
        return matrix

    def adjacency_tensor(self, max_entries=2_000_000):
        k, n = self.uniform(), self.order()
        if n**k > max_entries:
            raise ValueError("Dense tensor too large; use sparse alpha_spectrum instead")
        a = np.zeros((n,)*k)
        for edge, weight in zip(self.Edges, self.weights):
            for indices in itertools.permutations([self._index[v] for v in edge]):
                a[indices] = weight/math.factorial(k-1)
        from graph_research.tensors import Tensor
        return Tensor(a, symmetric=True)

    def alpha_tensor(self, alpha=0):
        from graph_research.tensors import Tensor, DiagonalTensor
        adjacency = self.adjacency_tensor()
        degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
        return alpha*DiagonalTensor(degrees, self.uniform())+(1-alpha)*adjacency

    def laplacian_tensor(self):
        from graph_research.tensors import DiagonalTensor
        degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
        return DiagonalTensor(degrees, self.uniform())-self.adjacency_tensor()

    def signless_laplacian_tensor(self):
        from graph_research.tensors import DiagonalTensor
        degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
        return DiagonalTensor(degrees, self.uniform())+self.adjacency_tensor()

    def eigen_equation(self, Type="A", l=None):
        x = sp.symbols(f"x0:{self.order()}")
        lam = sp.Symbol("lambda") if l is None else l
        k = self.uniform()
        result = []
        for i, v in enumerate(self.Vertices):
            adjacency = sum(sp.Rational(str(w))*sp.prod(x[self._index[u]] for u in e if u != v) for e,w in zip(self.Edges,self.weights) if v in e)
            degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
            d = sp.Rational(str(degrees[i]))*x[i]**(k-1)
            result.append(lam*x[i]**(k-1)-(d if Type in ("L", "Q") else 0)
                          + (adjacency if Type == "L" else -adjacency))
        return result

    def Alpha(self):
        return self.Alpha_Spectral_Radius()[0] ** (-self.uniform())

    def characteristic_polynomial(self,matrix="A",alpha=0,variable="lambda",**kwargs):
        """精确Res(lambda*x_i^(k-1)-(T*x^(k-1))_i)，保留代数重数。

        matrix支持A/L/Q/alpha；一般非空一致超图及显式rank的无边情形。
        支持孤立点和分量；返回SymPy Poly，details=True返回计算记录。
        不是匹配或E特征多项式，不返回特征向量。kwargs含精确weights、
        vertex_degrees、rank及EliminationLimits；分数请用Rational或字符串。
        """
        from graph_research.tensors.elimination import hypergraph_characteristic_polynomial
        return hypergraph_characteristic_polynomial(self,matrix,alpha,variable,**kwargs)

    def charpoly(self, variable='x', **kwargs):
        return self.characteristic_polynomial(variable=variable, **kwargs)

    def charpoly_system(self):
        from graph_research.tensors.elimination import charpoly_system
        return charpoly_system(self)

    def alpha_eigen_equations(self,alpha=None,l=None):
        """返回alpha张量的齐次多项式方程列表，不求解。

        非空一致超图；alpha=None保留符号alpha。x_i按vertices()顺序，
        l是可选谱变量。已有浮点权按十进制值精确化，不能恢复原始分数。
        """
        alpha=sp.Symbol("alpha") if alpha is None else sp.sympify(alpha)
        x=sp.symbols(f"x0:{self.order()}"); k=self.uniform()
        lam=sp.Symbol("lambda") if l is None else l
        degrees=self.incidence_matrix()@self.weights if self.vertex_degrees is None else self.vertex_degrees
        return [sp.expand((lam-alpha*sp.Rational(str(degrees[i])))*x[i]**(k-1)
                -(1-alpha)*sum(sp.Rational(str(w))*sp.prod(x[self._index[u]] for u in e if u!=v)
                 for e,w in zip(self.Edges,self.weights) if v in e)) for i,v in enumerate(self.Vertices)]

    def reduced_eigenequs(self,Type="A"):
        equations=self.eigen_equation(Type); blocks=self.orbit_subdivision()
        x=sp.symbols(f"x0:{self.order()}"); y=sp.symbols(f"y0:{len(blocks)}")
        substitutions={x[self._index[v]]:y[i] for i,block in enumerate(blocks) for v in block}
        return [sp.expand(equations[self._index[block[0]]].subs(substitutions)) for block in blocks]

    def Associated_Weight_Bipartite_Graph(self,alpha=0,W=True):
        matrix=self.WeightIncidenceMatrix(alpha)
        graph=self.incidence_graph()
        for i,v in enumerate(self.Vertices):
            for j,e in enumerate(self.Edges):
                if v in e: graph[("v",v)][("e",j)]["weight"]=float(matrix[i,j]) if W else 1.0
        return graph


    def eigenVfun(self,l=None,X=None):
        """Laplacian tensor equations as a SymPy column Matrix; not a solver."""
        if not self.is_uniform() or not self.Edges:raise ValueError('需要非空一致超图。')
        if self.vertex_degrees is not None:raise ValueError('此旧接口按边权度定义L，不读取独立D对角。')
        variables=list(sp.symbols(f'x0:{self.order()}'))
        target=variables if X is None else list(X)
        if len(target)!=self.order():raise ValueError('变量数量须与顶点数相同。')
        lam=sp.Symbol('lambda_',real=True) if l is None else l
        equations=self.eigen_equation('L',l=lam)
        return sp.Matrix([equation.subs(dict(zip(variables,target)),simultaneous=True) for equation in equations])


def alpha_spectral_radius(g, alpha=0, **kwargs):
    return g.Alpha_Spectral_Radius(alpha, **kwargs)


def WeightIncidenceMatrix(g, alpha=0, **kwargs):
    return g.WeightIncidenceMatrix(alpha, **kwargs)


def adjacency_tensor(g):
    return g.adjacency_tensor()


def laplacian_tensor(g):
    return g.laplacian_tensor()


def signless_laplacian_tensor(g):
    return g.signless_laplacian_tensor()


def alpha_tensor(g, alpha):
    return g.alpha_tensor(alpha)


def AdjacencyTensor(h,edge_weighted=True):
    from graph_research.hypergraphs.model import Hypergraph
    return (h if edge_weighted else Hypergraph(h.Edges,vertices=h.Vertices)).adjacency_tensor()


def Associated_Weight_Bipartite_Graph(h, alpha=0, W=True):
    return h.Associated_Weight_Bipartite_Graph(alpha, W)


def WIe(h,v,e,alpha=0,dig=None):
    from graph_research.hypergraphs.operations import Index
    index=e if type(e) is int else Index(h,e)[0]
    value=float(h.WeightIncidenceMatrix(alpha)[h._index[v],index])
    return round(value,dig) if dig is not None else value


def Matching_Polynomial(h,a=0,max_states=100000):
    """sum_M (-1)^|M| (1-a)^(k|M|) prod_uncovered(x-a*d_v)."""
    k=h.uniform(); n=h.order()
    if n>40 or not np.allclose(h.weights,1): raise ValueError("Exact unweighted matching polynomial supports at most40 vertices")
    x=sp.Symbol("x"); a=sp.sympify(a)
    masks=[sum(1<<h._index[v] for v in e) for e in h.Edges]
    degrees=h.degree_sequence(); states=0
    @lru_cache(maxsize=None)
    def polynomial(mask):
        nonlocal states
        states+=1
        if states>max_states: raise RuntimeError("Matching polynomial state budget exceeded")
        if not mask: return sp.Poly(1,x)
        v=(mask & -mask).bit_length()-1
        p=sp.Poly(x-a*degrees[v],x)*polynomial(mask & ~(1<<v))
        for edge_mask in masks:
            if edge_mask & (1<<v) and edge_mask & mask==edge_mask:
                p-=sp.Poly((1-a)**k,x)*polynomial(mask & ~edge_mask)
        return p
    return polynomial((1<<n)-1)

__all__ = ['alpha_spectral_radius', 'WeightIncidenceMatrix', 'adjacency_tensor', 'laplacian_tensor', 'signless_laplacian_tensor', 'alpha_tensor', 'AdjacencyTensor', 'Associated_Weight_Bipartite_Graph', 'WIe', 'Matching_Polynomial']
