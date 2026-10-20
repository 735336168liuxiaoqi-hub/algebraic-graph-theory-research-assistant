"""Independent edge-list certificate checker; never imports a spectral solver.

Nonnegative H-eigenvalue Collatz bounds, not Z-eigenvalues. Mathematical
reference: https://arxiv.org/abs/1111.2138 . Exact rational arithmetic certifies
the binary64 input model; it is not a proof about unspecified rounded data.
"""
from fractions import Fraction
import json
import math
from graph_research.runtime.observability import timed


def _rational(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Expected a finite real number')
    return Fraction(value)


@timed('certificate_verification')
def verify_spectrum_certificate(edges,result,*,weights=None,vertex_degrees=None,tolerance=1e-11,vertices=None):
    """Rebuild every equation using exact rationals, with no solver/model reuse.

    Vector labels must match exactly. Bounds certify the nonnegative tensor
    encoded by the supplied binary64 weights/alpha/diagonal and stored vector.
    A failed residual test is returned as passed=False; malformed input raises.
    """
    if not isinstance(result,dict) or not 0<tolerance<1:raise ValueError('Invalid certificate/tolerance')
    if not edges or len(edges)>128 or not 2<=len(edges[0])<=8:raise ValueError('Certificate size/rank outside budget')
    rank=len(edges[0]);expected=set(vertices) if vertices is not None else set().union(*map(set,edges));vertices=result.get('vertex_order',[])
    if not 1<=len(vertices)<=128 or len(set(vertices))!=len(vertices):raise ValueError('Invalid vertex_order')
    members=set(vertices)
    if any(len(e)!=rank or len(set(e))!=rank or not set(e)<=members for e in edges) or expected!=members:
        raise ValueError('Edges and certificate labels/uniformity disagree')
    if len({frozenset(e) for e in edges})!=len(edges):raise ValueError('Repeated edges')
    w=[_rational(float(t)) for t in (weights if weights is not None else [1]*len(edges))]
    if len(w)!=len(edges) or any(t<=0 for t in w):raise ValueError('Positive edge weights required')
    degrees={v:sum((t for e,t in zip(edges,w) if v in e),Fraction()) for v in vertices}
    diagonal=list(degrees.values()) if vertex_degrees is None else [_rational(float(t)) for t in vertex_degrees]
    if len(diagonal)!=len(vertices) or any(t<0 for t in diagonal):raise ValueError('Invalid diagonal')
    alpha=_rational(result.get('alpha'));rho=_rational(result.get('rho'))
    if not 0<=alpha<=1:raise ValueError('alpha outside [0,1]')
    if alpha==1:
        expected=max(diagonal);passed=abs(rho-expected)/max(1,abs(expected))<=Fraction(float(tolerance))
        return {'passed':passed,'level':'exact_diagonal','lower':math.nextafter(float(expected),-math.inf),'upper':math.nextafter(float(expected),math.inf),
                'exact_lower':str(expected),'exact_upper':str(expected),'relative_residual':float(abs(rho-expected)/max(1,abs(expected))),
                'input_semantics':'exact binary64 diagonal','independent':True}
    vector=result.get('perron_vector')
    if not isinstance(vector,list) or len(vector)!=len(vertices):raise ValueError('Vector length mismatch')
    x={v:_rational(t) for v,t in zip(vertices,vector)}
    if any(t<=0 for t in x.values()):raise ValueError('Strictly positive vector required for Collatz ratios')
    values=[]
    for v,d in zip(vertices,diagonal):
        adjacency=Fraction()
        for e,t in zip(edges,w):
            if v in e:
                term=t
                for u in e:
                    if u!=v:term*=x[u]
                adjacency+=term
        values.append(alpha*d+(1-alpha)*adjacency/x[v]**(rank-1))
    lower=min(values);upper=max(values);residual=max(abs(t-rho) for t in values)/max(1,abs(rho))
    return {'passed':residual<=Fraction(float(tolerance*1.01)), 'level':'exact_rational_collatz',
            'lower':math.nextafter(float(lower),-math.inf),'upper':math.nextafter(float(upper),math.inf),
            'exact_lower':str(lower),'exact_upper':str(upper),'relative_residual':math.nextafter(float(residual),math.inf),
            'input_semantics':'exact rationals of supplied binary64 alpha/weights/diagonal/vector',
            'independent':True,'vector_normalization_sum':float(sum(x.values()))}


def certificate_command(arguments):
    """Verify a user-selected JSON certificate without any solver/model call."""
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='独立核验超图谱证据，不重新求谱')
    parser.add_argument('input',help='JSON含edges、result及可选weights/vertex_degrees/tolerance')
    options=parser.parse_args(arguments);path=Path(options.input)
    if path.stat().st_size>4*1024*1024:raise ValueError('Certificate file exceeds4MiB')
    value=json.loads(path.read_text(encoding='utf-8-sig'));checked=verify_spectrum_certificate(**value)
    print(json.dumps(checked,ensure_ascii=False,indent=2,allow_nan=False));return 0 if checked['passed'] else 2
