"""Exact characteristic resultants by Macaulay's determinant quotient.

For an order-k, dimension-n action F, compute
    Res(lambda*x_i**(k-1) - F_i(x), i=0,...,n-1).
This is the ordinary tensor characteristic polynomial, NOT the E-polynomial,
the square-free eigenvalue polynomial, or a hypergraph matching polynomial.

The special lambda*I structure makes the Macaulay numerator and the principal
extraneous submatrix monic characteristic matrices. Their quotient is exact.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import itertools
import math
import re
import time

import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


class EliminationLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class EliminationLimits:
    max_macaulay_size: int = 4096
    max_block_size: int = 256
    max_polynomial_degree: int = 4096
    seconds: float = 30

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in (self.max_macaulay_size,self.max_block_size,self.max_polynomial_degree)):
            raise ValueError("Positive integer elimination limits required")
        if not math.isfinite(self.seconds) or self.seconds<=0:
            raise ValueError("Positive finite computation budget required")


@dataclass
class EliminationResult:
    polynomial: 'sp.Poly'  # string annotation: keep sympy lazy at class-definition time
    metadata: dict

    def as_dict(self):
        factored=sp.factor(self.polynomial.as_expr())
        expanded=str(self.polynomial.as_expr()); factor_text=str(factored)
        use_factored=len(expanded)>60000
        return {"polynomial":factor_text if use_factored else expanded,"factorization":factor_text,
                "polynomial_format":"factored" if use_factored else "expanded",
                "degree":int(self.polynomial.degree()),"variable":str(self.polynomial.gen),
                "leading_coefficient":str(self.polynomial.LC()),"metadata":self.metadata}


def exact_scalar(value):
    """No eval/sympify of user strings. Decimal floats mean exact decimals."""
    if isinstance(value,(bool,np.bool_)): raise ValueError("Boolean is not a tensor coefficient")
    if isinstance(value,sp.Expr):
        if value.has(sp.Float):
            value=value.xreplace({x:sp.Rational(str(x)) for x in value.atoms(sp.Float)})
        if value.has(sp.oo,-sp.oo,sp.zoo,sp.nan): raise ValueError("Finite coefficients required")
        if not value.is_rational_function(*sorted(value.free_symbols,key=str)):
            raise ValueError("Coefficients must be rational functions of exact parameters")
        return value
    if isinstance(value,(int,np.integer)): return sp.Integer(int(value))
    if isinstance(value,Fraction): return sp.Rational(value.numerator,value.denominator)
    text=str(value)
    if len(text)>128 or not re.fullmatch(r"[+-]?(?:\d+/\d+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",text):
        raise ValueError("Use an integer, finite decimal, rational string, or exact SymPy parameter")
    if "/" in text:
        numerator,denominator=text.split("/")
        if int(denominator)==0: raise ValueError("Zero denominator")
        return sp.Rational(int(numerator),int(denominator))
    value=Decimal(text)
    if not value.is_finite() or abs(value.adjusted())>1000: raise ValueError("Decimal exponent too large")
    rational=Fraction(value)
    return sp.Rational(rational.numerator,rational.denominator)


def elimination_size(n,rank):
    if type(n) is not int or n<1 or type(rank) is not int or rank<2:
        raise ValueError("Positive dimension and tensor order>=2 required")
    d=rank-1; critical=n*(d-1)+1
    return {"dimension":n,"tensor_order":rank,"equation_degree":d,
            "macaulay_degree":critical,"macaulay_size":math.comb(n*d,n-1),
            "expected_characteristic_degree":n*d**(n-1)}


def _compositions(total,length):
    if length==1:
        yield (total,); return
    for first in range(total,-1,-1):
        for tail in _compositions(total-first,length-1): yield (first,)+tail


class _Budget:
    def __init__(self,limits): self.limits=limits; self.start=time.monotonic()
    def check(self):
        if time.monotonic()-self.start>self.limits.seconds:
            raise EliminationLimitError("Exact elimination computation budget exceeded")


def _validate_action(rows,rank,variable):
    n=len(rows); d=rank-1; result=[]
    if not n or type(rank) is not int or rank<2: raise ValueError("Nonempty tensor action and order>=2 required")
    spectral=sp.Symbol(variable) if isinstance(variable,str) else variable
    if not isinstance(spectral,sp.Symbol): raise ValueError("Spectral variable must be a symbol")
    for row in rows:
        converted={}
        for powers,value in row.items():
            powers=tuple(powers)
            if len(powers)!=n or any(type(p) is not int or p<0 for p in powers) or sum(powers)!=d:
                raise ValueError("Each action monomial must be homogeneous of degree k-1")
            coefficient=exact_scalar(value)
            if spectral in coefficient.free_symbols: raise ValueError("Spectral variable occurs in a tensor coefficient")
            if coefficient!=0: converted[powers]=sp.cancel(converted.get(powers,0)+coefficient)
        result.append({p:c for p,c in converted.items() if c!=0})
    return result,spectral


def _matrix_charpoly(size,entries,variable,budget):
    """SCC factorization of det(variable*I-N), retaining ALL singleton factors."""
    if size==0: return sp.Poly(1,variable),[]
    graph=nx.DiGraph(); graph.add_nodes_from(range(size))
    graph.add_edges_from((i,j) for (i,j),c in entries.items() if c!=0 and i!=j)
    blocks=sorted((sorted(b) for b in nx.strongly_connected_components(graph)),key=lambda b:b[0])
    largest=max(map(len,blocks))
    if largest>budget.limits.max_block_size:
        raise EliminationLimitError(f"Macaulay SCC block {largest} exceeds limit {budget.limits.max_block_size}")
    factors=[]
    for block in blocks:
        budget.check()
        if len(block)==1:
            factor=sp.Poly(variable-entries.get((block[0],block[0]),0),variable)
        else:
            membership=set(block)
            off={i:[(j,entries[(i,j)]) for j in graph.successors(i) if j in membership] for i in block}
            # A single directed cycle has determinant prod(lambda-d_i)-prod(w_i).
            if all(len(off[i])==1 for i in block):
                expression=sp.prod(variable-entries.get((i,i),0) for i in block)-sp.prod(off[i][0][1] for i in block)
                factor=sp.Poly(expression,variable)
            else:
                position={v:i for i,v in enumerate(block)}
                matrix=sp.MutableSparseMatrix(len(block),len(block),
                    {(position[i],position[j]):value for (i,j),value in entries.items() if i in membership and j in membership})
                factor=matrix.charpoly(variable).as_poly(variable)
        factors.append(factor)
    # Small factors first reduces avoidable intermediate expression expansion.
    result=sp.Poly(1,variable)
    for factor in sorted(factors,key=lambda p:p.degree()):
        budget.check(); result*=factor
    return result,[len(b) for b in blocks]


def _macaulay(rows,rank,variable,budget):
    n=len(rows); d=rank-1; sizes=elimination_size(n,rank)
    if sizes["expected_characteristic_degree"]>budget.limits.max_polynomial_degree:
        raise EliminationLimitError("Characteristic polynomial degree exceeds configured limit")
    if sizes["macaulay_size"]>budget.limits.max_macaulay_size:
        raise EliminationLimitError(f"Macaulay matrix order {sizes['macaulay_size']} exceeds limit {budget.limits.max_macaulay_size}")
    monomials=list(_compositions(sizes["macaulay_degree"],n)); index={p:i for i,p in enumerate(monomials)}
    entries={}; nonreduced=[]
    for row_number,powers in enumerate(monomials):
        budget.check()
        divisible=[i for i,p in enumerate(powers) if p>=d]
        if len(divisible)>1: nonreduced.append(row_number)
        chosen=divisible[0]
        multiplier=list(powers); multiplier[chosen]-=d
        for exponent,coefficient in rows[chosen].items():
            target=tuple(a+b for a,b in zip(multiplier,exponent))
            key=(row_number,index[target]); entries[key]=entries.get(key,0)+coefficient
    numerator,nblocks=_matrix_charpoly(len(monomials),entries,variable,budget)
    kept={old:new for new,old in enumerate(nonreduced)}
    denominator,dblocks=_matrix_charpoly(len(nonreduced),
        {(kept[i],kept[j]):c for (i,j),c in entries.items() if i in kept and j in kept},variable,budget)
    budget.check()
    quotient,remainder=numerator.div(denominator)
    if not remainder.is_zero: raise ArithmeticError("Macaulay quotient has a nonzero remainder; no polynomial was accepted")
    if quotient.degree()!=sizes["expected_characteristic_degree"] or sp.simplify(quotient.LC()-1)!=0:
        raise ArithmeticError("Characteristic degree or monic normalization check failed")
    metadata={**sizes,"method":"macaulay_determinant_quotient","numerator_degree":int(numerator.degree()),
              "denominator_degree":int(denominator.degree()),"extraneous_matrix_size":len(nonreduced),
              "numerator_scc_blocks":nblocks,"denominator_scc_blocks":dblocks,
              "exact_division":True,"monic_checked":True,"degree_checked":True}
    return EliminationResult(quotient,metadata)


def action_characteristic_polynomial(rows,rank,variable="lambda",limits=None,details=False):
    """Generic sparse homogeneous tensor action. Coefficients remain exact."""
    limits=limits or EliminationLimits(); budget=_Budget(limits)
    rows,variable=_validate_action(rows,rank,variable)
    result=_macaulay(rows,rank,variable,budget)
    result.metadata.update(elapsed_seconds=time.monotonic()-budget.start,
        definition="Res(lambda*x_i^(k-1) - (T*x^(k-1))_i)",
        coefficient_policy="exact rational/parameter arithmetic; float inputs are exact decimal rationals")
    return result if details else result.polynomial


def tensor_characteristic_polynomial(tensor,variable="lambda",limits=None,details=False):
    """Cubical dense tensor, including nonsymmetric or signed tensors."""
    array=np.asarray(getattr(tensor,"array",tensor),dtype=object)
    if array.ndim<2 or not array.shape[0] or len(set(array.shape))!=1:
        raise ValueError("A nonempty cubical tensor of order>=2 is required")
    if array.size>20000: raise EliminationLimitError("Dense input exceeds20000 entries; supply a sparse action")
    n=array.shape[0]; rows=[{} for _ in range(n)]
    for indices in np.ndindex(array.shape):
        coefficient=exact_scalar(array[indices])
        if coefficient==0: continue
        powers=[0]*n
        for v in indices[1:]: powers[v]+=1
        key=tuple(powers); i=indices[0]
        rows[i][key]=rows[i].get(key,0)+coefficient
    return action_characteristic_polynomial(rows,array.ndim,variable,limits,details)


def hypergraph_characteristic_polynomial(h,matrix="A",alpha=0,variable="lambda",rank=None,
                                        weights=None,vertex_degrees=None,limits=None,details=False):
    """General uniform hypergraphs: A,L,Q,alpha, disconnected and isolated vertices.

    Empty-edge inputs need an explicit rank. Rational strings avoid float loss.
    Disjoint components are combined with tensor resultant multiplicities.
    """
    limits=limits or EliminationLimits(); budget=_Budget(limits)
    n=h.order()
    if not n: raise ValueError("At least one vertex is required")
    rank=(h.uniform() if h.Edges else None) if rank is None else rank
    if type(rank) is not int or rank<2: raise ValueError("Specify tensor rank>=2 for an edgeless hypergraph")
    if h.Edges and any(len(e)!=rank for e in h.Edges): raise ValueError("A uniform hypergraph is required")
    variable=sp.Symbol(variable) if isinstance(variable,str) else variable
    if not isinstance(variable,sp.Symbol): raise ValueError("Spectral variable must be a symbol")
    if matrix not in ("A","L","Q","alpha"): raise ValueError("matrix must be A,L,Q,alpha")
    alpha=exact_scalar(alpha)
    if matrix!="alpha" and alpha!=0: raise ValueError("alpha is used only with matrix='alpha'")
    w=[exact_scalar(v) for v in (h.weights if weights is None else weights)]
    if len(w)!=h.size(): raise ValueError("One exact weight per edge required")
    d=rank-1; expected=n*d**(n-1)
    if expected>limits.max_polynomial_degree: raise EliminationLimitError("Characteristic polynomial degree exceeds configured limit")
    diagonal=[sum(w[j] for j,e in enumerate(h.Edges) if v in e) for v in h.Vertices]
    override=h.vertex_degrees if vertex_degrees is None else vertex_degrees
    if override is not None:
        if len(override)!=n: raise ValueError("One diagonal degree per vertex required")
        diagonal=[exact_scalar(v) for v in override]
    diag_scale,edge_scale={"A":(0,1),"L":(1,-1),"Q":(1,1),"alpha":(alpha,1-alpha)}[matrix]
    rows=[{} for _ in range(n)]
    for i in range(n):
        powers=tuple(d if j==i else 0 for j in range(n))
        if diag_scale*diagonal[i]!=0: rows[i][powers]=diag_scale*diagonal[i]
    for edge,coefficient in zip(h.Edges,w):
        for v in edge:
            powers=[0]*n
            for u in edge:
                if u!=v: powers[h._index[u]]+=1
            row=rows[h._index[v]]; key=tuple(powers)
            row[key]=row.get(key,0)+edge_scale*coefficient
    rows,variable=_validate_action(rows,rank,variable)
    components=nx.Graph(); components.add_nodes_from(range(n))
    for edge in h.Edges:
        indices=[h._index[v] for v in edge]
        components.add_edges_from((indices[0],i) for i in indices[1:])
    blocks=[sorted(block) for block in nx.connected_components(components)]
    result=sp.Poly(1,variable); records=[]
    for block in blocks:
        budget.check(); size=len(block); exponent=d**(n-size)
        if size==1:
            i=block[0]; value=rows[i].get(tuple(d if j==i else 0 for j in range(n)),0)
            sub=EliminationResult(sp.Poly(variable-value,variable),{"method":"isolated_diagonal","dimension":1})
        else:
            local=[{tuple(p[j] for j in block):c for p,c in rows[i].items()} for i in block]
            sub=_macaulay(local,rank,variable,budget)
        result*=sub.polynomial**exponent
        records.append({"vertices":[h.Vertices[i] for i in block],"multiplicity_exponent":exponent,**sub.metadata})
    if result.degree()!=expected or sp.simplify(result.LC()-1)!=0: raise ArithmeticError("Disjoint-component degree/normalization check failed")
    metadata={"method":"componentwise_macaulay_resultant","dimension":n,"tensor_order":rank,
              "matrix":matrix,"alpha":str(alpha) if matrix=="alpha" else None,"expected_characteristic_degree":expected,
              "components":records,"exact_division":True,"monic_checked":True,"degree_checked":True,
              "elapsed_seconds":time.monotonic()-budget.start,
              "normalization":"A[e permutations]=weight/(k-1)!",
              "definition":"Res(lambda*x_i^(k-1) - (T*x^(k-1))_i)",
              "coefficient_policy":"Exact rational/parameter arithmetic; floats mean exact decimal rationals"}
    value=EliminationResult(result,metadata)
    return value if details else value.polynomial


def comp_charpoly(matrix,variable="x",limits=None):
    """Exact matrix characteristic polynomial, including isolated zero blocks."""
    array=np.asarray(matrix,dtype=object)
    if array.ndim!=2 or array.shape[0]!=array.shape[1]: raise ValueError("Square matrix required")
    limits=limits or EliminationLimits()
    if array.shape[0]>limits.max_macaulay_size: raise EliminationLimitError("Matrix size exceeds configured limit")
    variable=sp.Symbol(variable) if isinstance(variable,str) else variable
    entries={}
    for i,j in np.ndindex(array.shape):
        value=exact_scalar(array[i,j])
        if variable in value.free_symbols: raise ValueError("Matrix contains its spectral variable")
        if value!=0: entries[i,j]=value
    return _matrix_charpoly(len(array),entries,variable,_Budget(limits))[0]


def charpoly_H(h,variable="x",**kwargs):
    return hypergraph_characteristic_polynomial(h,variable=variable,**kwargs)


def charpoly_system(h):
    """Adjacency action polynomials in x0,...,x(n-1); no spectral variable."""
    variables=sp.symbols(f"x0:{h.order()}")
    h.uniform()
    return [sp.Poly(sum(exact_scalar(w)*sp.prod(variables[h._index[u]] for u in e if u!=v)
                for e,w in zip(h.Edges,h.weights) if v in e),*variables) for v in h.Vertices]
