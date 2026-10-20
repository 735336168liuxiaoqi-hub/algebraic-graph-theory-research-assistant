"""Positive Newton–Noda for sparse uniform hypergraph H-Perron pairs.

Algorithm 1 and halving condition (3), eta=1, of C.-H. Guo (2023):
https://uregina.ca/~chguo/Note_NNI.pdf . This is not unconstrained Newton.
Tensor actions use edge lists, never an n**k array. A dense n-by-n *scaled*
Jacobian is solved by subtraction-free elimination of an M-matrix represented
by its nonnegative off-diagonal magnitudes and row sums. Floating actions use
logaddexp; Decimal is a bounded precision fallback, not a second root algorithm.
"""
import json
import math
from decimal import Decimal, localcontext

import numpy as np


class PerronConvergenceError(ArithmeticError):
    """Uncertified diagnostics only; never an accepted approximate eigenpair."""
    def __init__(self, reason, diagnostics):
        self.diagnostics = {**diagnostics, 'stop_reason': reason, 'certified': False}
        super().__init__('Newton-Noda solver unresolved: '+json.dumps(self.diagnostics, allow_nan=False))


def _finite_diagnostic(value):
    number=float(value)
    return number if math.isfinite(number) else None


def _positive_solve(off_diagonal, row_sums, rhs):
    """Solve (diag(C1+s)-C)z=b without subtracting nearly equal pivots.

    C has zero diagonal and nonnegative entries; s>=0, b>0. Irreducibility
    and a nonzero s make this a nonsingular M-matrix. Do not regularize it or
    replace a negative/zero pivot by an arbitrary floor.
    """
    c=off_diagonal.copy();s=row_sums.copy();b=rhs.copy();n=len(s)
    if np.any(c<0) or np.any(s<0) or np.any(b<=0) or np.any(np.diag(c)!=0):
        raise ArithmeticError('Invalid M-matrix representation')
    pivots=np.zeros(n)
    with np.errstate(over='raise',divide='raise',invalid='raise'):
        for j in range(n):
            pivot=s[j]+c[j,j+1:].sum();pivots[j]=pivot
            if not math.isfinite(pivot) or pivot<=0:raise ArithmeticError('Nonpositive M-matrix pivot')
            if j==n-1:break
            factors=c[j+1:,j]/pivot
            c[j+1:,j+1:]+=factors[:,None]*c[j,j+1:][None,:]
            np.fill_diagonal(c[j+1:,j+1:],0)
            s[j+1:]+=factors*s[j];b[j+1:]+=factors*b[j]
        z=np.zeros(n)
        for j in range(n-1,-1,-1):z[j]=(b[j]+c[j,j+1:]@z[j+1:])/pivots[j]
    if not np.isfinite(z).all() or np.any(z<=0):raise ArithmeticError('Nonpositive Newton direction')
    return z


class _LogAction:
    def __init__(self, graph, alpha):
        self.n=graph.order();self.k=graph.rank
        self.edges=np.asarray([[graph._index[v] for v in e] for e in graph.Edges],dtype=int)
        self.weights=np.asarray(graph.weights)
        self.degrees=graph.incidence_matrix()@self.weights if graph.vertex_degrees is None else np.asarray(graph.vertex_degrees)
        if not np.isfinite(self.degrees).all():raise ValueError('Degree diagonal exceeds the finite binary64 input range')
        self.edge_logs=np.log(self.weights)+math.log1p(-alpha)
        with np.errstate(divide='ignore'):
            self.diagonal_logs=np.log(self.degrees)+math.log(alpha) if alpha else np.full(self.n,-np.inf)

    def evaluate(self, vector):
        """Return log Collatz ratios and log edge contributions, without x**k."""
        lx=np.log(vector)
        terms=self.edge_logs[:,None]+lx[self.edges].sum(axis=1)[:,None]-self.k*lx[self.edges]
        adjacency=np.full(self.n,-np.inf)
        np.logaddexp.at(adjacency,self.edges.ravel(),terms.ravel())
        return np.logaddexp(self.diagonal_logs,adjacency),terms

    def off_diagonal(self, terms, scale):
        rates=np.exp(terms-scale)
        if np.any(rates==0):raise ArithmeticError('Scaled derivative underflow')
        c=np.zeros((self.n,self.n))
        for i in range(self.k):
            for j in range(self.k):
                if i!=j:np.add.at(c,(self.edges[:,i],self.edges[:,j]),rates[:,i])
        return c


def _decimal_solve(c, s):
    """Same M-matrix elimination at the active Decimal precision."""
    n=len(s);c=[row[:] for row in c];s=s[:];b=[Decimal(1)]*n;pivots=[]
    for j in range(n):
        pivot=s[j]+sum(c[j][j+1:]);pivots.append(pivot)
        if pivot<=0:raise ArithmeticError('Nonpositive Decimal M-matrix pivot')
        for i in range(j+1,n):
            factor=c[i][j]/pivot
            if not factor:continue
            for t in range(j+1,n):
                if i!=t:c[i][t]+=factor*c[j][t]
            s[i]+=factor*s[j];b[i]+=factor*b[j]
    z=[Decimal(0)]*n
    for j in range(n-1,-1,-1):z[j]=(b[j]+sum(c[j][i]*z[i] for i in range(j+1,n)))/pivots[j]
    return z


def _decimal_refine(graph, alpha, vector, tolerance, remaining, diagnostics):
    """NNI at 60 decimal digits; inputs retain their exact binary64 meaning."""
    with localcontext() as context:
        context.prec=60
        zero=Decimal(0);one=Decimal(1);a=Decimal.from_float(float(alpha));eps=one-a
        k=graph.rank;p=k-1;n=graph.order();weights=[Decimal.from_float(float(w)) for w in graph.weights]
        edges=[[graph._index[v] for v in e] for e in graph.Edges]
        degrees=[zero]*n
        for edge,w in zip(edges,weights):
            for i in edge:degrees[i]+=w
        if graph.vertex_degrees is not None:degrees=[Decimal.from_float(float(d)) for d in graph.vertex_degrees]
        x=[Decimal.from_float(float(v)) for v in vector];norm=sum(v*v for v in x).sqrt();x=[v/norm for v in x]
        target=Decimal.from_float(float(tolerance)) / 4
        def evaluate(values, derivative=False):
            q=[a*d for d in degrees];c=[[zero]*n for _ in range(n)] if derivative else None
            for edge,w in zip(edges,weights):
                product=eps*w
                for j in edge:product*=values[j]
                for i in edge:
                    term=product/values[i]**k;q[i]+=term
                    if derivative:
                        for j in edge:
                            if i!=j:c[i][j]+=term
            return q,c
        for _ in range(remaining):
            diagnostics['iterations']+=1;q,c=evaluate(x,True);lower=min(q);upper=max(q);rho=(lower+upper)/2
            residual=(upper-lower)/2/max(one,abs(rho))
            diagnostics.update(last_lower=_finite_diagnostic(lower),last_upper=_finite_diagnostic(upper),last_relative_residual=_finite_diagnostic(residual),precision_digits=60)
            if residual<=target:return _finish(graph,alpha,x,rho,diagnostics)
            z=_decimal_solve(c,[p*(upper-v) for v in q]);diagnostics['linear_solves']+=1
            w=[v*t for v,t in zip(x,z)]
            norm=sum(v*v for v in w).sqrt();y=[v/norm for v in w];theta=one
            for _ in range(80):
                trial=[(k-2)*v+theta*t for v,t in zip(x,y)];nq,_=evaluate(trial)
                if all(upper-value>=theta/(2*norm)*(v/t)**p for value,v,t in zip(nq,x,trial)):break
                theta/=2;diagnostics['backtracks']+=1
            else:raise PerronConvergenceError('line_search_stalled',diagnostics)
            norm=sum(v*v for v in trial).sqrt();x=[v/norm for v in trial]
        raise PerronConvergenceError('iteration_budget_exhausted',diagnostics)


def _finish(graph,alpha,vector,rho,diagnostics):
    total=sum(vector);x=[float(v/total) for v in vector]
    if any(v<=0 or not math.isfinite(v) for v in x) or not math.isfinite(float(rho)):
        raise PerronConvergenceError('output_vector_outside_binary64_range',diagnostics)
    adjacent=graph.incidence_matrix()@graph.weights
    diagonal=adjacent if graph.vertex_degrees is None else graph.vertex_degrees
    rows=alpha*diagonal+(1-alpha)*adjacent
    return {'rho':float(rho),'perron_vector':x,'vertex_order':graph.vertices(),'alpha':float(alpha),
            'relative_residual':diagnostics['last_relative_residual'],'collatz_lower':diagnostics['last_lower'],
            'collatz_upper':diagnostics['last_upper'],'min_degree':float(min(rows)),'max_degree':float(max(rows)),
            'matrix_edge_order':[list(e) for e in graph.Edges],
            'source_function':'graph_research.hypergraphs.Hypergraph.alpha_spectrum','seed':diagnostics['seed'],
            'iterations':diagnostics['iterations'],'method':'newton_noda','normalization':'A[e permutations] = weight/(k-1)!; vector L1',
            'initialization':diagnostics['initialization'],'stop_reason':'collatz_tolerance',
            'solver_diagnostics':{**diagnostics,'vector_log_range':math.log(max(x))-math.log(min(x))},
            'sources':['https://uregina.ca/~chguo/Note_NNI.pdf']}


def _newton_noda_point(graph,alpha,tolerance,max_iterations,seed=42,initial_vector=None):
    """Positive H-Perron solver, sparse action and n-by-n scaled Jacobian.

    Callers validate connectedness, uniformity, alpha<1 and positive inputs.
    Linear solves and precision restarts share max_iterations. Result is a
    candidate until independently checked.
    """
    action=_LogAction(graph,float(alpha));n=graph.order();p=graph.rank-1
    x=np.random.default_rng(seed).uniform(.5,1,n) if initial_vector is None else np.asarray(initial_vector,dtype=float).copy()
    original=x.copy();x/=x.max();x/=np.sqrt(np.dot(x,x))
    diagnostics={'iterations':0,'linear_solves':0,'backtracks':0,'precision_digits':16,'precision_switches':[],'seed':seed,
                 'initialization':'seeded_random' if initial_vector is None else 'provided_vector','action':'logsumexp',
                 'linear_system':'row_column_scaled_subtraction_free_m_matrix',
                 'line_search':'Guo_2023_condition_3_eta_1_halving','history':[]}
    if np.any(x==0):
        diagnostics['precision_switches'].append({'iteration':0,'reason':'normalization_underflow','from_digits':16,'to_digits':60})
        return _decimal_refine(graph,alpha,original,tolerance,max_iterations,diagnostics)
    last_gap=math.inf;stagnant=0
    for _ in range(max_iterations):
        diagnostics['iterations']+=1
        logq,terms=action.evaluate(x);scale=float(logq.max());scaled=np.exp(logq-scale)
        lower=float(scaled.min());mid=(1+lower)/2
        residual=(1-lower)/(2*mid) if scale+math.log(mid)>=0 else math.exp(scale)*(1-lower)/2
        try:upper=math.exp(scale);rho=upper*mid
        except OverflowError:upper=None;rho=None
        diagnostics.update(last_lower=upper*lower if upper is not None else None,last_upper=upper,last_relative_residual=residual)
        if len(diagnostics['history'])<8 or diagnostics['iterations']%16==0:
            diagnostics['history'].append({'iteration':diagnostics['iterations'],'relative_gap':2*residual})
            diagnostics['history']=diagnostics['history'][-16:]
        if rho is not None and residual<=tolerance*.25:return _finish(graph,alpha,x,rho,diagnostics)
        stagnant=stagnant+1 if residual>=last_gap*.9 else 0;last_gap=residual
        try:
            if stagnant>=16:raise ArithmeticError('collatz_stagnation')
            c=action.off_diagonal(terms,scale)
            z=_positive_solve(c,p*(1-scaled),np.ones(n));diagnostics['linear_solves']+=1
            logw=np.log(x)+np.log(z);maximum=float(logw.max());lnorm=maximum+math.log(float(np.linalg.norm(np.exp(logw-maximum))))
            y=np.exp(logw-lnorm);theta=1.
            if np.any(y==0):raise ArithmeticError('Direction normalization underflow')
            for _ in range(60):
                trial=(graph.rank-2)*x+theta*y
                nextlog,_=action.evaluate(trial)
                nq=np.exp(np.minimum(nextlog-scale,700))
                logrhs=math.log(theta)-math.log(2)-lnorm+p*(np.log(x)-np.log(trial))
                slack=1-nq+8*np.finfo(float).eps
                with np.errstate(divide='ignore'):
                    accepted=np.all(np.log(np.maximum(slack,0))>=logrhs)
                if accepted:break
                theta/=2;diagnostics['backtracks']+=1
            else:raise ArithmeticError('line_search_stalled')
            x=trial/np.linalg.norm(trial)
        except (ArithmeticError,FloatingPointError,OverflowError) as error:
            diagnostics['precision_switches'].append({'iteration':diagnostics['iterations'],'reason':str(error),'from_digits':16,'to_digits':60})
            try:return _decimal_refine(graph,alpha,x,tolerance,max_iterations-diagnostics['iterations'],diagnostics)
            except PerronConvergenceError:raise
            except ArithmeticError as precision_error:
                diagnostics['precision_error']=str(precision_error)
                raise PerronConvergenceError('precision_limit_reached',diagnostics) from precision_error
    raise PerronConvergenceError('iteration_budget_exhausted',diagnostics)


def newton_noda_spectrum(graph,alpha,tolerance,max_iterations,seed=42,initial_vector=None):
    """NNI with recorded near-endpoint continuation, one total iteration budget.

    Above .8, positive NNI solves follow decreasing 1-alpha, by at most a factor
    of five per stage; unresolved stages halve the step in -log(1-alpha).
    Every stage is independently checked where the certificate
    size budget permits. No A answers, graph-family-specific rules, extra host
    tool invocations, or silent budget increase. Computational work at all stages
    remains inside the same protected invocation and wall/CPU/memory limits.
    """
    if alpha<=.8:
        return _newton_noda_point(graph,alpha,tolerance,max_iterations,seed,initial_vector)
    # A verified warm solution should not be displaced by lower-alpha work.
    if initial_vector is not None:
        action=_LogAction(graph,alpha);logs,_=action.evaluate(np.asarray(initial_vector,dtype=float))
        scale=float(logs.max());lower=math.exp(float(logs.min())-scale)
        if (1-lower)/(1+lower)<=tolerance*.125:
            return _newton_noda_point(graph,alpha,tolerance,max_iterations,seed,initial_vector)
    used=0;records=[];x=initial_vector;solves=0;backtracks=0;switches=[];failed=[];previous=None
    value=.5;log_step=math.log(5)
    while True:
        remaining=max_iterations-used
        if remaining<=0:
            raise PerronConvergenceError('iteration_budget_exhausted',{'iterations':used,'continuation_stages':records})
        try:result=_newton_noda_point(graph,value,tolerance,min(128,remaining),seed,x)
        except PerronConvergenceError as error:
            used+=error.diagnostics['iterations'];solves+=error.diagnostics.get('linear_solves',0);backtracks+=error.diagnostics.get('backtracks',0)
            switches.extend({**s,'alpha':value} for s in error.diagnostics.get('precision_switches',[]))
            failed.append({'alpha':value,'iterations':error.diagnostics['iterations'],'stop_reason':error.diagnostics['stop_reason'],
                           'precision_digits':error.diagnostics.get('precision_digits',16)})
            if previous is not None and used<max_iterations and len(failed)<=32:
                log_step=min(log_step,math.log((1-previous)/(1-value)))*.5
                middle=1-(1-previous)*math.exp(-log_step)
                if previous<middle<value:
                    value=middle
                    continue
            error.diagnostics.update(iterations=used,continuation_stages=records,failed_stages=failed,stage_alpha=value,target_alpha=alpha)
            raise PerronConvergenceError(error.diagnostics['stop_reason'],error.diagnostics) from error
        result=graph._verified_spectrum(result,tolerance)
        detail=result['solver_diagnostics'];used+=result['iterations'];solves+=detail['linear_solves'];backtracks+=detail['backtracks']
        switches.extend({**s,'alpha':value} for s in detail['precision_switches'])
        records.append({'alpha':value,'iterations':result['iterations'],'linear_solves':detail['linear_solves'],
                        'precision_digits':detail['precision_digits'],'rho':result['rho'],
                        'relative_residual':result['relative_residual'],'verification':result['verification']['level']})
        x=result['perron_vector'];previous=value
        if value==alpha:break
        value=min(alpha,1-(1-value)*math.exp(-log_step))
        if value<=previous:raise PerronConvergenceError('continuation_step_underflow',{'iterations':used,'continuation_stages':records})
    result['iterations']=used
    result['initialization']='seeded_random' if initial_vector is None else 'provided_vector'
    result['solver_diagnostics'].update(iterations=used,linear_solves=solves,backtracks=backtracks,precision_switches=switches,
                                        continuation_stages=records,failed_stages=failed,initialization=result['initialization'],
                                        max_precision_digits=max(s['precision_digits'] for s in records+failed))
    return result
