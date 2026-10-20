"""Declarative batches: preflight, real protected steps, branches and recovery."""
import copy
import csv
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import create_subagent,SubagentLimits,verify_bundle
from graph_research.assistant.batch_workflow import compile_batch,preflight_batch,summary,summary_csv
from graph_research.assistant.task_contract import TaskProtocolError,validate_task
from graph_research.tools import ToolRegistry


def batch_task(request_id='batch-1',*,independent=False):
    steps=[{'id':'rank','tool':'matrix_analysis','arguments':{},'bindings':{'matrix':{'step':'spectrum','path':['matrix']}}},
           {'id':'spectrum','tool':'graph_spectrum','arguments':{},'bindings':{'kind':{'input':['kind']},'n':{'case':['n']}}}]
    if independent:steps.append({'id':'independent','tool':'graph_invariants','arguments':{'kind':'path','n':3}})
    return {'version':1,'request_id':request_id,'objective':'批量计算路径图谱并核验矩阵秩','inputs':{'kind':'path'},
            'execution':{'mode':'batch','batch':{'cases':[{'id':'P3','inputs':{'n':3}},{'id':'P4','inputs':{'n':4}}],
                'steps':steps,'on_error':'continue_independent',
                'outputs':{'rho':{'step':'spectrum','path':['rho']},'rank':{'step':'rank','path':['rank']}}}},
            'constraints':{'max_model_calls':0,'max_tool_calls':8,'allow_extensions':False}}


class BatchContractTests(unittest.TestCase):
    def test_case_expansion_topology_binding_and_input_immutability(self):
        task=batch_task();original=copy.deepcopy(task);plan=compile_batch(validate_task(task))
        self.assertEqual(task,original);self.assertEqual([s['id'] for s in plan['steps']],['P3::spectrum','P3::rank','P4::spectrum','P4::rank'])
        self.assertEqual(plan['steps'][0]['arguments'],{'kind':'path','n':3})
        self.assertEqual(plan['steps'][1]['bindings']['matrix']['step'],'P3::spectrum')
        self.assertEqual(plan['steps'][1]['_dependencies'],['P3::spectrum'])
        policy=SubagentLimits(max_tool_calls=8,allow_extensions=False).resolve(validate_task(task))
        preflight_batch(validate_task(task),ToolRegistry(),policy)

    def test_cycle_unknown_dependency_duplicate_ids_and_missing_output_rejected(self):
        for mutation in ('cycle','dependency','step_id','case_id','output','collision','case_path'):
            task=batch_task();batch=task['execution']['batch']
            if mutation=='cycle':batch['steps'][1]['depends_on']=['rank']
            elif mutation=='dependency':batch['steps'][1]['depends_on']=['unknown']
            elif mutation=='step_id':batch['steps'][1]['id']='rank'
            elif mutation=='case_id':batch['cases'][1]['id']='P3'
            elif mutation=='output':batch['outputs']['rank']['step']='missing'
            elif mutation=='collision':batch['steps'][1]['arguments']['n']=3
            else:batch['cases'][1]['inputs']={}
            with self.subTest(mutation=mutation),self.assertRaises(TaskProtocolError):validate_task(task)

    def test_ambiguous_ids_and_expressions_are_not_binding_syntax(self):
        for value in ('a::b','../outside','a/b'):
            task=batch_task();task['execution']['batch']['cases'][0]['id']=value
            with self.assertRaises(TaskProtocolError):validate_task(task)
        task=batch_task();task['execution']['batch']['steps'][1]['bindings']['n']={'expression':'__import__("os")'}
        with self.assertRaises(TaskProtocolError):validate_task(task)

    def test_expanded_count_and_size_are_bounded(self):
        task=batch_task();task['execution']['batch']['cases']=[{'id':f'c{i}','inputs':{'n':3}} for i in range(64)]
        with self.assertRaises(TaskProtocolError) as error:validate_task(task)
        self.assertEqual(error.exception.code,'batch_too_large')
        task=batch_task();batch=task['execution']['batch'];task['inputs']['large']='x'*20000
        batch['steps']=[{'id':'a','tool':'graph_invariants','arguments':{},'bindings':{'data':{'input':['large']}}}]
        batch['outputs']={ 'x':{'step':'a','path':[]} };batch['cases']=[{'id':f'c{i}','inputs':{}} for i in range(64)]
        with self.assertRaises(TaskProtocolError) as error:validate_task(task)
        self.assertEqual(error.exception.code,'batch_too_large')

    def test_budget_and_allowlist_are_checked_for_whole_expansion(self):
        task=validate_task(batch_task());task['constraints']['max_tool_calls']=3
        with self.assertRaises(TaskProtocolError) as error:SubagentLimits(max_tool_calls=8,allow_extensions=False).resolve(task)
        self.assertEqual(error.exception.code,'batch_budget_insufficient')
        task['constraints'].pop('max_tool_calls');task['constraints']['allowed_tools']=['graph_spectrum']
        with self.assertRaises(TaskProtocolError) as error:SubagentLimits(allow_extensions=False).resolve(task)
        self.assertEqual(error.exception.code,'tool_not_permitted')

    def test_non_batch_modes_do_not_accept_batch_configuration(self):
        task=batch_task();task['execution']['mode']='tools'
        with self.assertRaises(TaskProtocolError):validate_task(task)
        task=batch_task();task['execution']['steps']=task['execution']['batch']['steps']
        with self.assertRaises(TaskProtocolError):validate_task(task)

    def test_preflight_rejects_late_unknown_tool_static_type_and_bound_parameter(self):
        for mutation in ('tool','type','parameter'):
            task=batch_task();step=task['execution']['batch']['steps'][0]
            if mutation=='tool':step['tool']='not_installed'
            elif mutation=='type':step['arguments']['operation']=123
            else:step['bindings']={'not_a_parameter':{'step':'spectrum','path':['matrix']}}
            request=validate_task(task);policy=SubagentLimits(allow_extensions=False).resolve(request)
            with self.subTest(mutation=mutation),self.assertRaises(TaskProtocolError):preflight_batch(request,ToolRegistry(),policy)

    def test_default_single_case_outputs_reference_large_values_and_csv_is_safe(self):
        task=batch_task();batch=task['execution']['batch'];batch.pop('cases');batch['steps']=[{'id':'data','tool':'graph_invariants','arguments':{'n':3}}]
        batch['outputs']={'text':{'step':'data','path':['text']},'large':{'step':'data','path':['large']}}
        request=validate_task(task)
        state={'observations':[{'step_id':'default::data','tool':'graph_invariants','ok':True,'result':{'text':'=HYPERLINK("bad")','large':list(range(1000))}}]}
        value=summary(request,state);self.assertEqual(value['rows'][0]['outputs']['large']['status'],'available')
        self.assertNotIn('value',value['rows'][0]['outputs']['large'])
        rows=list(csv.DictReader(io.StringIO(summary_csv(value).decode('utf-8-sig'))))
        by_name={row['output']:row for row in rows}
        self.assertTrue(by_name['text']['value'].startswith("'="));self.assertEqual(by_name['large']['call_id'],'call-0001')

    def test_compact_mcp_preview_is_bounded_and_keeps_full_record_unchanged(self):
        from graph_research.mcp.presentation import result_view
        task=batch_task();batch=task['execution']['batch'];batch['cases']=[{'id':f'p{i}','inputs':{'n':3}} for i in range(12)]
        batch_summary=summary(validate_task(task),{})
        full={'summary':{'batch':batch_summary},'results':[]};preview=result_view(full)
        self.assertEqual(len(preview['summary']['batch']['rows']),8);self.assertEqual(preview['summary']['batch']['omitted_rows'],4)
        self.assertEqual(len(preview['summary']['batch']['steps']),20);self.assertEqual(len(full['summary']['batch']['steps']),24)
        self.assertEqual(result_view(full,'full'),full)

    def test_html_batch_table_escapes_output_text(self):
        from graph_research.rendering.results import render_result_report
        task=batch_task();batch=task['execution']['batch'];batch.pop('cases')
        batch['steps']=[{'id':'data','tool':'graph_invariants','arguments':{'n':3}}];batch['outputs']={'text':{'step':'data','path':['text']}}
        state={'observations':[{'step_id':'default::data','tool':'graph_invariants','ok':True,'result':{'text':'<img src=x onerror=bad>'}}]}
        data={'batch_workflow':summary(validate_task(task),state),'summary':{'successful_calls':1,'failed_calls':0,'verified_calls':1,'artifact_count':0,'record_status':'recorded','turn_count':0},
              'calculations':[],'turns':[],'warnings':[],'scope':'conversation','bundle_id':'a'*32,'exported_at':'test'}
        html=render_result_report(data)
        self.assertIn('批量工作流汇总',html);self.assertNotIn('<img src=x',html);self.assertIn('&lt;img',html)


@unittest.skipUnless(os.name=='nt','Real Windows protected execution')
class BatchExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.parent,self.portal=create_subagent(self.root,user_id='batch',limits=SubagentLimits(max_tool_calls=8,max_model_calls=0,allow_extensions=False),
            model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model calls')))

    def test_real_multicase_plan_outputs_receipts_and_single_bundle(self):
        result=self.parent.submit(batch_task());self.assertEqual(result['status'],'completed')
        self.assertEqual(result['budget']['used'],{'tool_calls':4,'model_calls':0})
        batch=result['summary']['batch'];self.assertEqual(batch['counts']['success'],4)
        self.assertAlmostEqual(batch['rows'][0]['outputs']['rho']['value'],math.sqrt(2))
        self.assertEqual(batch['rows'][0]['outputs']['rank']['value'],2);self.assertEqual(batch['rows'][1]['outputs']['rank']['value'],4)
        self.assertEqual({r['case_id'] for r in result['results']},{'P3','P4'})
        artifact=result['artifacts'][0];self.assertTrue(verify_bundle(artifact['path'],artifact['sha256'])['ok'])
        with zipfile.ZipFile(artifact['path']) as archive:
            self.assertTrue({'batch-summary.json','batch-plan.json','batch-results.csv'}<=set(archive.namelist()))
            document=json.loads(archive.read('results.json'));self.assertEqual(document['batch_workflow']['successful_cases'],2)
            self.assertEqual(document['summary']['verified_calls'],4)
        repeated=self.parent.submit(batch_task());self.assertEqual(repeated['task_id'],result['task_id'])
        self.assertEqual(repeated['budget']['used']['tool_calls'],4);self.assertEqual(repeated['summary']['reuse']['task_reused'],1)

    def test_late_invalid_step_rejects_entire_plan_before_creating_task(self):
        task=batch_task();task['execution']['batch']['steps'][0]['tool']='missing'
        with patch('graph_research.runtime.runner.run_tool') as run,self.assertRaises(TaskProtocolError):self.parent.submit(task)
        run.assert_not_called();self.assertFalse(list(self.root.glob('users/*/tasks/*/task.json')))

    def test_continue_independent_skips_failed_dependencies_and_keeps_other_case(self):
        task=batch_task(independent=True);task['inputs']['kind']='cycle';task['execution']['batch']['cases'][0]['inputs']['n']=2
        result=self.parent.submit(task);self.assertEqual(result['status'],'partial')
        batch=result['summary']['batch'];self.assertEqual(batch['counts'],{'pending':0,'running':0,'success':4,'failed':1,'skipped':1,'interrupted':0})
        self.assertEqual(result['budget']['used']['tool_calls'],5);self.assertEqual(batch['rows'][1]['status'],'success')
        self.assertTrue(verify_bundle(result['artifacts'][0]['path'],result['artifacts'][0]['sha256'])['ok'])

    def test_stop_marks_remaining_steps_skipped_and_does_not_spend_budget(self):
        task=batch_task(independent=True);task['inputs']['kind']='cycle';batch=task['execution']['batch'];batch['cases'][0]['inputs']['n']=2;batch['on_error']='stop'
        result=self.parent.submit(task);self.assertEqual(result['status'],'failed')
        self.assertEqual(result['summary']['batch']['counts']['skipped'],5);self.assertEqual(result['budget']['used']['tool_calls'],1)

    def test_missing_binding_path_fails_without_starting_the_dependent_tool(self):
        task=batch_task(independent=True);task['execution']['batch']['cases']=task['execution']['batch']['cases'][:1]
        task['execution']['batch']['steps'][0]['bindings']['matrix']['path']=['missing']
        result=self.parent.submit(task);self.assertEqual(result['status'],'partial')
        self.assertEqual(result['budget']['used']['tool_calls'],2)
        failed=next(s for s in result['summary']['batch']['steps'] if s['local_step_id']=='rank')
        self.assertFalse(failed['attempted']);self.assertEqual(failed['reason'],'binding_path_unavailable')

    def test_requested_missing_output_is_not_reported_as_complete(self):
        task=batch_task();task['execution']['batch']['outputs']['rho']['path']=['missing']
        result=self.parent.submit(task);self.assertEqual(result['status'],'partial')
        self.assertFalse(result['summary']['batch']['all_outputs_available'])
        with zipfile.ZipFile(result['artifacts'][0]['path']) as archive:
            self.assertEqual(json.loads(archive.read('results.json'))['summary']['record_status'],'partial')

    def cancel_after_first_success(self):
        from graph_research.runtime.runner import run_tool
        calls=[]
        def run(*args,**kwargs):
            result=run_tool(*args,**kwargs);calls.append(result)
            if len(calls)==1:
                task_id=next(self.root.glob('users/*/tasks/*/task.json')).parent.name
                self.parent.cancel(task_id)
            return result
        with patch('graph_research.runtime.runner.run_tool',side_effect=run):result=self.parent.submit(batch_task())
        self.assertEqual(result['status'],'cancelled');self.assertEqual(result['budget']['used']['tool_calls'],1)
        self.assertEqual(result['summary']['batch']['rows'][0]['status'],'paused')
        return result,calls

    def test_uncertain_interrupted_attempt_is_visible_and_retry_keeps_budget(self):
        with patch('graph_research.runtime.runner.run_tool',side_effect=InterruptedError('interrupted')):result=self.parent.submit(batch_task())
        self.assertEqual(result['status'],'cancelled');self.assertEqual(result['summary']['batch']['counts']['interrupted'],1)
        self.assertEqual(result['summary']['batch']['counts']['running'],0)
        self.assertIn('重新执行未核验步骤',result['interaction']['message']);self.assertIn('重算另计',result['interaction']['message'])
        interaction=result['interaction'];event=self.portal.continue_task(result['task_id'],interaction['interaction_id'],result['revision'])
        done=self.parent.resume(result['task_id'],event['event_id'])
        self.assertEqual(done['status'],'completed');self.assertEqual(done['budget']['used']['tool_calls'],5)

    def test_cancel_restart_and_user_resume_reuses_verified_steps(self):
        result,_=self.cancel_after_first_success()
        self.parent,self.portal=create_subagent(self.root,user_id='batch',limits=SubagentLimits(max_tool_calls=8,max_model_calls=0,allow_extensions=False))
        interaction=result['interaction'];event=self.portal.continue_task(result['task_id'],interaction['interaction_id'],result['revision'])
        finished=self.parent.resume(result['task_id'],event['event_id']);self.assertEqual(finished['status'],'completed')
        self.assertEqual(finished['budget']['used']['tool_calls'],4);self.assertEqual(finished['summary']['reused_calculations'],1)

    def test_tampered_receipt_stops_recovery_without_recomputation(self):
        result,calls=self.cancel_after_first_success()
        receipt=Path(calls[0]['execution']['directory'])/'execution.json';receipt.write_bytes(receipt.read_bytes()+b' ')
        interaction=result['interaction'];event=self.portal.continue_task(result['task_id'],interaction['interaction_id'],result['revision'])
        with patch('graph_research.runtime.runner.run_tool') as run:
            finished=self.parent.dispatch({'operation':'resume','task_id':result['task_id'],'event_id':event['event_id']})
        run.assert_not_called();self.assertEqual(finished['status'],'protocol_error');self.assertEqual(finished['error']['code'],'receipt_changed')
        self.assertEqual(self.parent._service.read(result['task_id'])['usage']['tool_calls'],1)
