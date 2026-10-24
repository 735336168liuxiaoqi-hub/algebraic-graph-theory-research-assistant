"""Phase 3: genuine protected computation, trusted review and durable accounting."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import create_subagent,SubagentLimits,verify_bundle
from graph_research.assistant.task_contract import RESULT_SCHEMA,TaskProtocolError
from graph_research.assistant import experiment_execution as engine
from graph_research.runtime.runner import run_worker
from graph_research.runtime.storage import atomic_text
from tests.test_experiment_evaluation import execution,PATH,STAR,LOOSE_PATH,LOOSE_CYCLE,problem
import jsonschema


def task(spec=None):
    return {'version':1,'request_id':'explicit-collection','objective':'Evaluate a finite explicit collection',
        'execution':{'mode':'experiment','experiment':spec or execution()},
        'constraints':{'max_model_calls':0,'max_tool_calls':4,'allow_extensions':False}}


def advance(parent,portal,response):
    event=portal.continue_task(response['task_id'],response['interaction']['interaction_id'],response['revision'])
    return parent.resume(response['task_id'],event['event_id'])


class ExecutionTests(unittest.TestCase):
    def test_invalid_candidates_have_precise_paths_without_starting_a_worker(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'mcp'),'fields'))
        prefix=['task','execution','experiment','cases',0,'candidates',0,'edges']
        variants=[([[0,0]],'self_loop',[0]),([[0,1],[1,0]],'duplicate_edge',[1]),
                  ([[0,4]],'vertex_out_of_range',[0,1])]
        with patch.object(engine,'run_worker',side_effect=AssertionError('Invalid input must not compute')):
            for edges,code,suffix in variants:
                with self.subTest(code=code):
                    spec=execution();spec['cases'][0]['candidates']=[{'n':4,'edges':edges}]
                    for parent in (self.parent,runtime):
                        response=parent.dispatch({'operation':'submit','task':task(spec)}) if parent is self.parent else parent.call('research_submit',{'task':task(spec)})
                        self.assertEqual(response['status'],'protocol_error')
                        self.assertEqual(response['error']['cause_code'],code)
                        self.assertEqual(response['error']['field_path'],prefix+suffix)
        self.assertEqual(runtime.list_tasks()['tasks'],[])

    def test_schema_errors_choose_real_operation_branch_and_redact_values(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'schema-mcp'),'fields'))
        spec=execution();spec['cases'][0]['candidates'][0]['edges']=[[-1,1]]
        for response in (self.parent.dispatch({'operation':'submit','task':task(spec)}),runtime.call('research_submit',{'task':task(spec)})):
            self.assertEqual(response['error']['field_path'],['task','execution','experiment','cases',0,'candidates',0,'edges',0,0])
            self.assertEqual(response['error']['validation'],{'minimum':0})
        request=task();request['constraints']['max_tool_calls']='PRIVATE_SECRET_VALUE'
        result=self.parent.dispatch({'operation':'submit','task':request})
        self.assertEqual(result['error']['field_path'],['task','constraints','max_tool_calls'])
        self.assertNotIn('PRIVATE_SECRET_VALUE',json.dumps(result))

    def test_unsupported_hypergraph_metric_is_an_input_error_with_location(self):
        spec=execution();spec['problem']=problem('alpha_spectral_radius','hypergraph')
        spec['problem']['objective']['arguments']={'alpha':'1/2'}
        response=self.parent.dispatch({'operation':'submit','task':task(spec)})
        self.assertEqual(response['status'],'protocol_error')
        self.assertEqual(response['error']['field_path'],['task','execution','experiment','problem','objective','metric'])
        self.assertIn('distance_spectral_radius',response['error']['validation']['enum'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.parent,self.portal=self.create()

    def create(self,**options):
        return create_subagent(self.root,user_id='experiment',limits=options.pop('limits',SubagentLimits(max_model_calls=0,max_tool_calls=4,allow_extensions=False)),
            model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model permitted')),**options)

    def test_first_review_has_zero_calls_then_real_worker_and_verified_bundle(self):
        with patch.object(engine,'run_worker',side_effect=AssertionError('Must wait')):
            first=self.parent.submit(task())
        self.assertEqual(first['status'],'waiting_for_user');self.assertEqual(first['interaction']['kind'],'experiment_review')
        self.assertEqual(first['budget']['used'],{'model_calls':0,'tool_calls':0})
        self.assertEqual(first['interaction']['plan']['evaluations'],1)
        self.assertEqual(self.parent.dispatch({'operation':'resume','task_id':first['task_id'],'approved':True})['status'],'protocol_error')
        result=advance(self.parent,self.portal,first);jsonschema.validate(result,RESULT_SCHEMA)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['summary']['verified_calls'],1)
        self.assertTrue(result['summary']['experiment']['collection_complete'])
        self.assertFalse(result['summary']['experiment']['enumeration_complete'])
        self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':1})
        artifact=next(a for a in result['artifacts'] if a['kind']=='result_bundle')
        self.assertTrue(verify_bundle(artifact['path'],artifact['sha256'])['ok'])
        with zipfile.ZipFile(artifact['path']) as z:
            for name in ('experiment-results.json','experiment-input.json','experiment-ledger.json'):self.assertIn(name,z.namelist())
            self.assertEqual(json.loads(z.read('results.json'))['calculations'][0]['evidence_status'],'verified_execution')

    def test_segment_restart_reuses_prior_success_and_keeps_budgets(self):
        spec=execution([PATH,{'n':4,'edges':[[0,1],[0,2],[0,3]]}]);spec['segment_chunks']=1
        first=self.parent.submit(task(spec));second=advance(self.parent,self.portal,first)
        self.assertEqual(second['interaction']['kind'],'experiment_continue');self.assertEqual(second['summary']['experiment']['evaluations_completed'],1)
        old=second['summary']['experiment']['attempts'][0]
        parent,portal=self.create()
        with patch.object(engine,'run_worker',wraps=run_worker) as worker:
            final=advance(parent,portal,second)
        self.assertEqual(worker.call_count,1);self.assertEqual(final['status'],'completed')
        self.assertEqual(final['summary']['experiment']['evaluations_completed'],2)
        self.assertEqual(final['summary']['experiment']['attempts'][0],old)
        self.assertEqual(final['budget']['experiment']['evaluation_reservations'],2)

    def test_cancel_before_review_does_not_approve_on_resume(self):
        first=self.parent.submit(task(),defer=True)
        cancelled=self.parent.cancel(first['task_id'])
        resumed=advance(self.parent,self.portal,cancelled)
        self.assertEqual(resumed['interaction']['kind'],'experiment_review')
        self.assertEqual(resumed['budget']['used']['tool_calls'],0)
        self.assertFalse(resumed['summary']['experiment']['approved'])

    def test_failure_retry_reserves_both_attempts_no_automatic_retry(self):
        first=self.parent.submit(task())
        with patch.object(engine,'run_worker',side_effect=RuntimeError('simulated failure')) as worker:
            failed=advance(self.parent,self.portal,first)
        self.assertEqual(worker.call_count,1);self.assertEqual(failed['status'],'interrupted')
        self.assertEqual(failed['budget']['used']['tool_calls'],1)
        self.assertEqual(failed['budget']['experiment']['wall_seconds'],30)
        self.assertEqual(failed['results'][0]['error_details']['exception_type'],'RuntimeError')
        final=advance(self.parent,self.portal,failed)
        self.assertEqual(final['status'],'partial')
        self.assertTrue(final['summary']['experiment']['collection_complete'])
        self.assertEqual(final['budget']['experiment']['evaluation_reservations'],2)
        self.assertEqual(final['budget']['used']['tool_calls'],2)

    def test_uncertain_attempt_cannot_reset_evaluation_or_cpu_budget(self):
        for budget in ({'max_evaluations':1},{'cpu_seconds':1}):
            spec=execution();spec['budget'].update(budget)
            request=task(spec);request['request_id']='limit-'+next(iter(budget))
            first=self.parent.submit(request)
            with patch.object(engine,'run_worker',side_effect=RuntimeError()):failed=advance(self.parent,self.portal,first)
            with patch.object(engine,'run_worker',side_effect=AssertionError('Budget exhausted')):
                final=advance(self.parent,self.portal,failed)
            self.assertEqual(final['status'],'budget_exhausted');self.assertEqual(final['budget']['used']['tool_calls'],1)

    def test_pinned_receipt_recovers_after_crash_without_recompute(self):
        first=self.parent.submit(task());original=engine.check_chunk;calls=[]
        def crash_before_observation(*args):
            calls.append(1)
            if len(calls)==2:raise KeyboardInterrupt()
            return original(*args)
        with patch.object(engine,'check_chunk',side_effect=crash_before_observation):
            stopped=advance(self.parent,self.portal,first)
        self.assertEqual(stopped['status'],'cancelled');self.assertEqual(stopped['summary']['experiment']['evaluations_completed'],0)
        with patch.object(engine,'run_worker',side_effect=AssertionError('Must recover pinned receipt')):
            final=advance(self.parent,self.portal,stopped)
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],1)
        record=self.parent._service.read(final['task_id']);session=self.parent._service.session(record)
        self.assertTrue(session.state['observations'][0]['reused_execution'])

    def test_unpinned_completed_files_are_not_reused_without_new_attempt(self):
        first=self.parent.submit(task())
        def crash_after_worker(*args,**kwargs):
            run_worker(*args,**kwargs);raise KeyboardInterrupt()
        with patch.object(engine,'run_worker',side_effect=crash_after_worker):stopped=advance(self.parent,self.portal,first)
        self.assertEqual(stopped['status'],'cancelled')
        self.assertNotIn('receipt_sha256',stopped['summary']['experiment']['attempts'][0])
        final=advance(self.parent,self.portal,stopped)
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],2)
        self.assertEqual(final['budget']['experiment']['evaluation_reservations'],2)

    def test_cancel_between_chunks_keeps_first_evidence(self):
        spec=execution([PATH,PATH]);first=self.parent.submit(task(spec))
        def cancel_after_worker(*args,**kwargs):
            result=run_worker(*args,**kwargs);atomic_text(kwargs['cancel_file'],'cancel',overwrite=True);return result
        with patch.object(engine,'run_worker',side_effect=cancel_after_worker):stopped=advance(self.parent,self.portal,first)
        self.assertEqual(stopped['status'],'cancelled');self.assertEqual(stopped['summary']['experiment']['evaluations_completed'],1)
        final=advance(self.parent,self.portal,stopped)
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],2)

    def test_changed_receipt_rejects_resume_without_recomputation(self):
        spec=execution([PATH,PATH]);spec['segment_chunks']=1
        paused=advance(self.parent,self.portal,self.parent.submit(task(spec)))
        record=self.parent._service.read(paused['task_id']);session=self.parent._service.session(record)
        receipt=Path(session.state['observations'][0]['execution']['directory'])/'execution.json'
        receipt.write_text('{}',encoding='utf-8')
        with patch.object(engine,'run_worker',side_effect=AssertionError('No recomputation')):
            with self.assertRaises(TaskProtocolError):advance(self.parent,self.portal,paused)
        self.assertEqual(self.parent._service.read(paused['task_id'])['usage']['tool_calls'],1)

    def test_corrupted_ledger_and_scope_fail_closed(self):
        for corruption in ('scope','counter'):
            request=task();request['request_id']='corruption-'+corruption
            first=self.parent.submit(request)
            event=self.portal.continue_task(first['task_id'],first['interaction']['interaction_id'],first['revision'])
            record=self.parent._service.read(first['task_id'])
            if corruption=='scope':record['experiment_ledger']['request_sha256']='0'*64
            else:record['usage']['tool_calls']=1
            self.parent._service.save(record,bump=False)
            with patch.object(engine,'run_worker',side_effect=AssertionError('No computation')):
                final=self.parent.resume(first['task_id'],event['event_id'])
            self.assertEqual(final['status'],'failed')

    def test_preflight_honors_host_whitelist_memory_and_chunk_limits(self):
        for limits in (SubagentLimits(max_tool_calls=0),SubagentLimits(allowed_tools=('graph_spectrum',))):
            parent,_=self.create(limits=limits)
            request=task();request['constraints'].pop('max_tool_calls')
            with self.assertRaises(TaskProtocolError):parent.submit(request)
        request=task();request['execution']['experiment']['budget']['memory_mb']=2048
        with self.assertRaises(TaskProtocolError):self.parent.submit(request)

    def test_failure_diagnostic_retains_windows_path_code_without_input_contents(self):
        error=FileNotFoundError('Long workspace path');error.winerror=206
        first=self.parent.submit(task())
        with patch.object(engine,'run_worker',side_effect=error):failed=advance(self.parent,self.portal,first)
        self.assertEqual(failed['results'][0]['error_details']['winerror'],206)
        self.assertEqual(failed['results'][0]['error_details']['phase'],'experiment.chunk_execution')

    def test_shipped_execute_examples_validate_through_public_task_contract(self):
        from graph_research.assistant.task_contract import validate_task
        root=Path(__file__).resolve().parents[1]/'examples/research-experiments'
        for family in ('clique-free','hypertree-distance','hypergraph-distance'):
            sample=json.loads((root/(family+'-execute.json')).read_text(encoding='utf-8'))
            self.assertEqual(validate_task(sample)['execution']['mode'],'experiment')
            self.assertEqual(json.loads((root/(family+'-execute-request.json')).read_text(encoding='utf-8')),{'operation':'submit','task':sample})

    def test_uniform_hypertree_execution_has_feasible_and_rejected_candidates(self):
        spec=execution([STAR,LOOSE_PATH]);spec['problem']=problem('distance_spectral_radius','uniform_hypertree')
        spec['problem']['constraints']={'predicate':'max_degree','arguments':{'value':3}}
        spec['chunk_size']=2
        final=advance(self.parent,self.portal,self.parent.submit(task(spec)))
        self.assertEqual(final['status'],'completed')
        rows=final['summary']['experiment']['rows'];self.assertEqual([r['feasible'] for r in rows],[True,False])

    def test_cyclic_uniform_and_nonuniform_hypergraphs_use_protected_execution(self):
        for kind,graph in [('uniform_hypergraph',LOOSE_CYCLE),('hypergraph',{'n':5,'edges':[[0,1,2],[1,3],[2,3,4]]})]:
            spec=execution([graph]);spec['problem']=problem('distance_spectral_radius',kind)
            if kind=='uniform_hypergraph':spec['problem']['object']['uniformity']=3
            request=task(spec);request['request_id']='general-'+kind
            first=self.parent.submit(request);self.assertEqual(first['budget']['used']['tool_calls'],0)
            final=advance(self.parent,self.portal,first)
            self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],1)
            row=final['summary']['experiment']['rows'][0]
            self.assertTrue(row['feasible']);self.assertFalse(row['properties']['hypertree']);self.assertTrue(row['verification']['passed'])

    def test_mcp_background_execute_reviews_and_compacts_without_assistant_api(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'mcp-experiment',max_tool_calls=4))
        def wait(task_id):
            deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                result=runtime.get(task_id,wait_seconds=1,until='terminal',detail='full')
                if not result.get('transport',{}).get('active'):return result
            self.fail('MCP experiment timed out')
        try:
            spec=execution([LOOSE_CYCLE]);spec['problem']=problem('distance_spectral_radius','uniform_hypergraph');spec['problem']['object']['uniformity']=3
            first=wait(runtime.submit(task(spec))['task_id'])
            self.assertEqual(first['status'],'waiting_for_user');self.assertEqual(first['budget']['used']['tool_calls'],0)
            _,portal=create_subagent(self.root,user_id='mcp-experiment',limits=runtime.configuration.limits())
            event=portal.continue_task(first['task_id'],first['interaction']['interaction_id'],first['revision'])
            runtime.resume(first['task_id'],event['event_id']);final=wait(first['task_id'])
            self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['model_calls'],0)
            self.assertFalse(final['summary']['experiment']['rows'][0]['properties']['hypertree'])
            compact=runtime.get(first['task_id']);experiment=compact['summary']['experiment']
            self.assertNotIn('rows',experiment);self.assertNotIn('attempts',experiment);self.assertEqual(experiment['row_count'],1)
            self.assertEqual(len(runtime.catalog()['tools']),47)
        finally:
            for process in runtime.children.values():
                if process.poll() is None:process.terminate();process.wait(5)


if __name__=='__main__':unittest.main()
