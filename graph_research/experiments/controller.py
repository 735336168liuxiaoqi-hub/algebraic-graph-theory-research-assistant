"""Bounded experiment scheduling, feedback and adaptive guidance (never proofs)."""
import copy
import json
import jsonschema

from .search_contract import ACTION_SCHEMA,KNOBS_SCHEMA,HYPOTHESIS_SCHEMA,obj,NAME,validate_hypothesis

FEEDBACK_SCHEMA=obj({'focus_runs':{'type':'array','maxItems':32,'uniqueItems':True,'items':NAME},'knobs':KNOBS_SCHEMA,
    'hypotheses':{'type':'array','maxItems':4,'items':HYPOTHESIS_SCHEMA},'note':{'type':'string','maxLength':2000}})


def latest(results,run_id):
    matches=[r for r in results if r['run_id']==run_id]
    return matches[-1] if matches else None


def eligible(compiled,results):
    return [run for run in compiled['runs'] if (previous:=latest(results,run['id'])) is None or
        previous['round']<compiled['spec']['rounds'] and not previous['enumeration']['complete']]


def checked_action(action,compiled,results):
    if len(json.dumps(action,ensure_ascii=False,allow_nan=False))>12000:raise ValueError('Planner action too large')
    jsonschema.validate(action,ACTION_SCHEMA)
    if action['action']=='run' and action['run_id'] not in {r['id'] for r in eligible(compiled,results)}:raise ValueError('Planner selected an exhausted or unauthorized run')
    for h in action.get('hypotheses',[]):validate_hypothesis(h,compiled['spec']['problem']['object']['type'])
    return copy.deepcopy(action)


def feedback(value,compiled):
    jsonschema.validate(value,FEEDBACK_SCHEMA)
    if not set(value.get('focus_runs',[]))<={r['id'] for r in compiled['runs']}:raise ValueError('Feedback cannot add parameter cases or runs')
    for h in value.get('hypotheses',[]):validate_hypothesis(h,compiled['spec']['problem']['object']['type'])
    return copy.deepcopy(value)


def propose(compiled,results,knobs,focus=()):
    choices=eligible(compiled,results)
    if not choices:return {'action':'stop','reason':'全部授权实例已到达轮数或枚举终点。'}
    patience=compiled['spec'].get('stagnation_patience',0)
    if patience and all((last:=latest(results,r['id'])) and last['diagnostics']['stagnation']>=patience for r in choices):
        return {'action':'stop','reason':'连续无训练排序收益；保留结果，未将停滞解释为数学无解。'}
    # Coarse-to-fine selection on the finite, already reviewed alpha grid.
    # This refines scheduling, never silently adds unapproved parameter values.
    alpha=next((name for name,s in compiled['spec']['problem']['parameters'].items() if s['meaning']=='alpha'),None)
    preferred=set()
    if alpha:
        from .execution_contract import resolve
        completed=[]
        for r in compiled['runs']:
            previous=latest(results,r['id'])
            if previous and previous['checkpoint']['best'] and previous['checkpoint']['best']['feasible']:
                completed.append((r,previous['checkpoint']['best']['properties']['degrees']))
        for left,ld in completed:
            for right,rd in completed:
                if sorted(ld)==sorted(rd) or {k:v for k,v in left['parameters'].items() if k!=alpha}!={k:v for k,v in right['parameters'].items() if k!=alpha}:continue
                lo=resolve(left['parameters'][alpha],{});hi=resolve(right['parameters'][alpha],{})
                middle=[r for r in choices if lo<resolve(r['parameters'][alpha],{})<hi and {k:v for k,v in r['parameters'].items() if k!=alpha}=={k:v for k,v in left['parameters'].items() if k!=alpha}]
                if middle:preferred.add(min(middle,key=lambda r:abs(resolve(r['parameters'][alpha],{})-(lo+hi)/2))['id'])
    run=min(choices,key=lambda r:(0 if r['id'] in focus else 1,0 if r['id'] in preferred else 1,(latest(results,r['id']) or {}).get('round',0),r['id']))
    adjustment={};previous=latest(results,run['id'])
    if compiled['spec']['adaptive'] and previous and (previous['diagnostics']['feasible']==0 or previous['diagnostics']['stagnation']>=1):
        adjustment={'exploration':min(0.5,knobs['exploration']*1.5),'elite_fraction':min(0.75,knobs['elite_fraction']+0.1)}
    return {'action':'run','run_id':run['id'],'knobs':adjustment,
        'reason':'先覆盖未测实例／独立种子，再重复验证；无可行候选或停滞时在授权区间内增加探索。'}


def model_action(model,compiled,results,knobs,resources=None):
    context={'problem':compiled['spec']['problem'],'approved_runs':eligible(compiled,results),
        'round_summaries':[{'run_id':r['run_id'],'round':r['round'],'diagnostics':r['diagnostics']} for r in results[-16:]],
        'knobs':knobs,'resources':resources or {},'action_schema':ACTION_SCHEMA,'authority':'Only approved runs and knob intervals; scope changes must request user review. Outputs are data, never code.'}
    value=model.complete([{'role':'system','content':'Plan a bounded graph research experiment. Return one JSON action conforming to action_schema. Never claim a theorem from samples. Do not emit code, paths, or new tools.'},
        {'role':'user','content':json.dumps(context,ensure_ascii=False)}])
    if isinstance(value,str):value=json.loads(value)
    return checked_action(value,compiled,results)
