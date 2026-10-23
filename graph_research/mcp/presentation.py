"""Bounded model-facing views; durable records always retain the full data."""
import copy
import json

HEAVY={'perron_vector','expanded_perron_vector','vertex_order','matrix_edge_order','weighted_incidence','quotient_terms','vertex_orbits','orbit_blocks','equitable_blocks'}


def result_view(result,detail='summary'):
    if detail not in ('summary','full'):raise ValueError('detail must be summary or full')
    result=copy.deepcopy(result)
    reuse=result.get('summary',{}).get('reuse')
    if isinstance(reuse,dict):
        reuse['scope']='whole_task_cumulative'
        reuse['cumulative']={'request_replays':reuse.get('task_reused',0),'steps_reused':reuse.get('steps_reused',0),'steps_executed':reuse.get('steps_recomputed',0)}
        reuse['meaning']='Legacy steps_recomputed counts historical executed observations, not new computation in this RPC. Use request_effect for this request and operation.usage for the background job.'
    budget=result.get('budget',{})
    if 'limits' in budget:
        request_mode=result.get('summary',{}).get('execution_mode')
        if request_mode:
            budget['admission_policy']='execute_until_budget_exhausted' if request_mode=='tools' and not result['summary'].get('fail_fast',False) else 'reject_before_execution' if request_mode in ('tools','scan','batch') else 'runtime_budget_enforced'
    if detail=='full':return result
    experiment=result.get('summary',{}).get('experiment')
    if experiment and 'plan' in experiment:
        plan=experiment['plan'];cases=plan['cases'];plan['cases']=cases[:8];plan['omitted_cases']=max(0,len(cases)-8)
        experiment.pop('problem',None)
        experiment['details_location']='research_get(detail=full) or result bundle experiment-preparation.json'
    elif experiment:
        experiment['row_count']=len(experiment.pop('rows',[]))
        experiment['omitted_cases']=max(0,len(experiment['cases'])-8)
        experiment['cases']=[{k:v for k,v in case.items() if k!='selected_candidate'} for case in experiment['cases'][:8]]
        experiment['attempt_count']=len(experiment.pop('attempts',[]))
        if experiment.get('operation')=='study':
            interpretation=experiment.pop('interpretation',{})
            experiment['run_statistics']=interpretation.get('run_statistics',[])[:8]
            experiment['hypothesis_checks']=[{'id':h['hypothesis']['id'],'status':h['status'],'tested':h['tested'],'witness_count':len(h['witnesses'])} for h in interpretation.get('hypothesis_checks',[])]
            experiment['decision_count']=len(experiment.pop('decisions',[]));experiment['feedback_count']=len(experiment.pop('feedback',[]))
        experiment['details_location']='research_get(detail=full), research_inspect_result or experiment-results.json in bundle'
    for entry in result.get('results',[]):
        timing=entry.pop('timings',None)
        if timing:
            stages=(timing.get('worker') or {}).get('stages',{})
            keys=('worker.dispatch_import','worker.registry','tool_function','certificate_verification','artifact_export')
            entry['timing_summary']={key:stages[key]['exclusive_seconds'] for key in keys if key in stages}
            entry['timings_available_in']='research_get(detail=full) or result bundle; summary values are exclusive seconds'
        if result.get('summary',{}).get('scan') and entry.get('tool')=='hypergraph_spectrum' and isinstance(entry.get('data'),dict):
            data=entry['data'];entry['data']={'verification':{k:v for k,v in data.get('verification',{}).items() if k in ('passed','level','independent')}}
            entry['data_location']='summary.scan.points (scalar results); research_inspect_result (full evidence)'
            entry['read_more']={'tool':'research_inspect_result','call_id':entry['call_id'],'path':[]}
        if isinstance(entry.get('measurements'),dict):
            entry['measurements']={k:v for k,v in entry['measurements'].items() if k in ('available','cpu_seconds','peak_job_memory_bytes','host_elapsed_seconds')}
        if 'arguments' in entry:
            entry.pop('arguments');entry['arguments_available_in']='result_bundle'
        if entry.get('status')=='success':
            entry.setdefault('read_more',{'tool':'research_inspect_result','call_id':entry['call_id'],'path':[]})
        data=entry.get('data')
        if isinstance(data,dict):
            omitted=[];shown={}
            for key,value in data.items():
                if key=='verification' and isinstance(value,dict):
                    shown[key]={k:v for k,v in value.items() if k in ('passed','level','lower','upper','relative_residual','independent')}
                    omitted.append('verification (full certificate)');continue
                if key in HEAVY or len(json.dumps(value,ensure_ascii=False).encode('utf-8'))>1024:omitted.append(key)
                else:shown[key]=value
            entry['data']=shown
            if omitted:entry['omitted_fields']=omitted;entry['read_more']={'tool':'research_inspect_result','call_id':entry['call_id'],'path':[]}
    batch=result.get('summary',{}).get('batch')
    if batch:
        rows=batch['rows'];steps=batch['steps']
        batch['rows']=rows[:8];batch['omitted_rows']=max(0,len(rows)-8)
        important=[step for step in steps if step['status'] in ('running','failed','interrupted')]
        preview=important[:20]+[step for step in steps if step not in important][:max(0,20-len(important))]
        batch['steps']=preview;batch['omitted_steps']=len(steps)-len(preview)
        if batch['omitted_rows'] or batch['omitted_steps']:batch['details_location']='detail=full or result bundle batch-summary.json'
    result['summary']['return_detail']='summary'
    return result
