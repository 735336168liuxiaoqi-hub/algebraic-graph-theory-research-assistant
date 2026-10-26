"""Derive completion from plan coverage and evidence, never from a partial status.

Unexecuted entries are presentation records, not observations or charged calls.
Cached successful observations still count as coverage without new tool usage.
"""
from .batch_workflow import read_path


def fixed_outcomes(request,results,status,batch=None,skips=None,*,plan=None):
    from .spectral_scan import execution_steps
    if request['execution']['mode'] not in ('tools','scan','batch'):return None,[]
    if plan is None:plan=execution_steps(request)
    observed={r.get('step_id'):r for r in results}
    ledger={s['step_id']:s for s in batch['steps']} if batch else {}
    terminal=status not in ('queued','running','waiting_for_user','waiting_for_approval')
    details=[];unexecuted=[]
    for step in plan:
        call=observed.get(step['id']);saved=ledger.get(step['id'],{})
        state=call['status'] if call else saved.get('status','pending')
        if not call and step['id'] in (skips or {}):state='skipped'
        if not call and terminal and state in ('pending','running','interrupted'):state='skipped'
        reason=(skips or {}).get(step['id']) or saved.get('reason') or ('stopped_on_error' if status in ('partial','failed') and any(r['status']=='failed' for r in results) else 'task_'+status if terminal else 'not_yet_executed')
        item={'step_id':step['id'],'tool':step['tool'],'status':state,'attempted':bool(call) or saved.get('attempted',False)}
        if call:item['call_id']=call['call_id']
        else:item['reason']=reason
        details.append(item)
        if not call and terminal:
            unexecuted.append({**item,'tool_status':'not_executed','arguments':step['arguments']})
    counts={key:sum(s['status']==key for s in details) for key in ('pending','running','success','failed','skipped','interrupted')}
    return {'total':len(details),'counts':counts,'steps':details,
            'execution_complete':terminal and all(s['status'] in ('success','failed') for s in details),
            'all_succeeded':all(s['status']=='success' for s in details)},unexecuted


def expected_outputs(request,state,*,terminal=True):
    """Text remains advisory; explicit JSON paths are actually checked."""
    hints=[];checks=[]
    observations={o.get('step_id'):o for o in state.get('observations',[]) if 'tool' in o}
    for output in request.get('expected_outputs',[]):
        if isinstance(output,str):hints.append(output);continue
        source=observations.get(output['step']);check={**output,'status':'missing'}
        if source and source.get('ok') is True:
            try:read_path(source['result'],output['path'],copy_value=False);check['status']='available'
            except (KeyError,IndexError):check['reason']='output_path_unavailable'
        else:check['reason']='source_step_not_successful'
        if check['status']=='missing' and not terminal:check['status']='pending'
        checks.append(check)
    status='missing' if any(c['status']=='missing' for c in checks) else 'pending' if any(c['status']=='pending' for c in checks) else 'not_validated' if hints else 'satisfied' if checks else 'not_requested'
    return {'status':status,'advisory':hints,'checks':checks,
            'complete':status in ('satisfied','not_requested'),
            'meaning':'文本交付意图未经自动验证；结构化step/path只核验输出可用性，不证明数学结论。'}
