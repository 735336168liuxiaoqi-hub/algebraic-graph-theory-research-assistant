"""Declarative alpha scans compiled into the existing protected step executor."""
import copy


def execution_steps(request):
    """A generator costs one attempt; each parameter point costs one attempt."""
    execution=request['execution']
    if execution['mode']=='batch':
        from .batch_workflow import compile_batch
        return compile_batch(request)['steps']
    if execution['mode']!='scan':return execution.get('steps',[])
    scan=execution['scan'];steps=[];earlier=[]
    if 'generator' in scan:steps.append({'id':'scan-graph','tool':'generate_hypergraph','arguments':copy.deepcopy(scan['generator'])})
    for index,alpha in enumerate(scan['alphas']):
        args={key:copy.deepcopy(scan[key]) for key in ('weights','vertex_degrees','tolerance','max_iterations','method','seed') if key in scan}
        args.setdefault('method','auto');args['alpha']=alpha;step={'id':f'scan-{index+1:04d}','tool':'hypergraph_spectrum','arguments':args}
        if 'edges' in scan:args['edges']=copy.deepcopy(scan['edges'])
        else:step['bindings']={'edges':{'step':'scan-graph','path':['edges']}}
        if scan.get('warm_start',True) and alpha<1:step['_warm_candidates']=list(reversed(earlier))
        if alpha<1:earlier.append(step['id'])
        steps.append(step)
    return steps


def scan_summary(request,observations):
    """Progress without vectors or repeated edge tables; full data stays on disk."""
    if request['execution']['mode']!='scan':return None
    scan=request['execution']['scan'];rows=[]
    for index,alpha in enumerate(scan['alphas']):
        step_id=f'scan-{index+1:04d}';item=next((o for o in observations if o.get('step_id')==step_id),None)
        row={'step_id':step_id,'alpha':alpha,'status':'pending'}
        if item:
            data=item.get('result',{});row.update(status='success' if item.get('ok') else 'failed')
            row.update({k:data[k] for k in ('rho','relative_residual','iterations','method','stop_reason') if k in data})
            if not item.get('ok'):row['error']=item.get('error')
            if not item.get('ok') and any(text in str(item.get('error')) for text in ('Perron solver did not converge','root solver unresolved')):
                row.update(status='unresolved',stop_reason='iteration_budget_exhausted')
            if not item.get('ok') and 'Newton-Noda solver unresolved:' in str(item.get('error')):
                row.update(status='unresolved',stop_reason='newton_noda_unresolved')
        rows.append(row)
    return {'points':rows,'completed_points':sum(r['status']!='pending' for r in rows),'total_points':len(rows),
            'successful_points':sum(r['status']=='success' for r in rows),'failed_points':sum(r['status'] in ('failed','unresolved') for r in rows),
            'required_tool_attempts':len(execution_steps(request)),'accounting':'每个参数点和可选构图分别计一次工具尝试；不是一次批量调用抵扣全部预算。'}
