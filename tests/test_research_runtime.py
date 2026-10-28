"""Long budgets, persistent kernels and streamed evidence without large runs."""
import copy
import base64
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.runtime.runner import TaskLimits,clean_environment
from graph_research.runtime.resources import host_profile,MAX_WALL_SECONDS,MAX_MEMORY_MB
from graph_research.assistant import create_subagent,SubagentLimits,verify_bundle
from graph_research.assistant.task_contract import validate_task,TaskProtocolError
from graph_research.experiments.search_contract import compile_study
from graph_research.experiments.search_engine import run_round
from graph_research.experiments.search_segments import run_segment,verify_segment,round_records
from graph_research.experiments.interpretation import analyze_streamed
from tests.test_experiment_study import study,task,round_args
from tests.test_experiment_execution import advance

TORCH=importlib.util.find_spec('torch') is not None


class HostAutonomyTests(unittest.TestCase):
    def connection(self,folder,confirm=False,**options):
        return create_subagent(folder,user_id='autonomy-test',limits=SubagentLimits(
            max_model_calls=0,max_tool_calls=10,allow_extensions=False,confirm_experiments=confirm,**options))

    def request(self,spec):
        value=task(spec);value['constraints'].update(max_tool_calls=10)
        value['constraints'].pop('require_review',None)
        spec['pause_at_checkpoints']=False
        return value

    def assert_direct(self,parent,final,ledger_key):
        self.assertEqual(final['status'],'completed',final.get('error'))
        record=parent._service.read(final['task_id']);ledger=record[ledger_key]
        self.assertEqual(record['event_receipts'],{})
        self.assertNotIn('experiment_confirmation',record)
        self.assertFalse({'approved','host_authorization','approval_event_id'}&set(ledger))
        self.assertEqual(ledger['version'],2)
        self.assertNotIn('approved',final['summary']['experiment'])
        self.assertFalse((parent._service.root/'.host-events.key').exists())
        return record

    def test_normal_collection_runs_directly_without_approval_state(self):
        from tests.test_experiment_execution import task as explicit_task
        from tests.test_experiment_evaluation import execution,PATH
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder)
            spec=execution([PATH,{'n':4,'edges':[[0,1],[0,2],[0,3]]}]);spec.update(pause_at_checkpoints=False,segment_chunks=1)
            request=explicit_task(spec);request['constraints'].pop('require_review')
            final=parent.submit(request);self.assert_direct(parent,final,'experiment_ledger')
            self.assertEqual(final['budget']['used'],{'model_calls':0,'tool_calls':2})
            self.assertEqual(parent.submit(request)['budget']['used'],final['budget']['used'])

    def test_segmentation_does_not_mean_human_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder);spec=study('random');spec.update(rounds=3,segment_rounds=1)
            final=parent.submit(self.request(spec));self.assert_direct(parent,final,'study_ledger')
            self.assertEqual(final['summary']['experiment']['rounds_completed'],3)
            self.assertEqual(final['budget']['used']['tool_calls'],3)

    @unittest.skipUnless(TORCH,'Optional CPU torch missing')
    def test_cem_runs_without_fake_approval_or_model_request(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder);final=parent.submit(self.request(study('cem')))
            self.assert_direct(parent,final,'study_ledger')
            self.assertTrue(final['summary']['experiment']['training_performed'])
            self.assertEqual(final['budget']['used'],{'model_calls':0,'tool_calls':2})

    def test_existing_host_budget_is_not_rechecked_against_old_soft_thresholds(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder,tool_limits=TaskLimits(memory_mb=2048,cpu_threads=2))
            spec=study('random');spec.update(rounds=3,segment_rounds=1,cpu_threads=2)
            spec['budget'].update(wall_seconds=600,cpu_seconds=600,memory_mb=2048)
            final=parent.submit(self.request(spec));self.assert_direct(parent,final,'study_ledger')
            self.assertEqual(final['budget']['used']['tool_calls'],3)

    def test_one_initial_confirmation_does_not_enable_checkpoint_pauses(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,portal=self.connection(folder);spec=study('random');spec.update(rounds=3,segment_rounds=1)
            request=self.request(spec);request['constraints']['require_review']=True
            first=parent.submit(request);self.assertEqual(first['status'],'waiting_for_user')
            self.assertEqual(first['budget']['used']['tool_calls'],0)
            final=advance(parent,portal,first);self.assertEqual(final['status'],'completed',final.get('error'))
            record=parent._service.read(final['task_id'])
            self.assertIn('experiment_confirmation',record)
            self.assertEqual(len(record['event_receipts']),1)
            self.assertEqual(final['budget']['used']['tool_calls'],3)
            self.assertNotIn('approved',record['study_ledger'])

    def test_checkpoint_feedback_does_not_create_initial_permission_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,portal=self.connection(folder);spec=study('random');spec['segment_rounds']=1
            request=self.request(spec);spec['pause_at_checkpoints']=True
            paused=parent.submit(request)
            self.assertEqual(paused['status'],'waiting_for_user')
            self.assertEqual(paused['interaction']['kind'],'experiment_continue')
            self.assertEqual(paused['budget']['used']['tool_calls'],1)
            self.assertNotIn('experiment_confirmation',parent._service.read(paused['task_id']))
            event=portal.study_feedback(paused['task_id'],paused['interaction']['interaction_id'],paused['revision'],{'knobs':{'exploration':.3}})
            final=parent.resume(paused['task_id'],event['event_id']);self.assertEqual(final['status'],'completed')
            self.assertNotIn('experiment_confirmation',parent._service.read(final['task_id']))

    def test_authorized_model_planning_runs_and_unformalized_conditions_are_rejected(self):
        from tests.test_feature_workflow import ScriptedModel
        with tempfile.TemporaryDirectory() as folder:
            model=ScriptedModel([{'action':'run','run_id':'run1','reason':'one authorized generation'}])
            parent,_=create_subagent(folder,user_id='model-pilot',limits=SubagentLimits(max_model_calls=1,max_tool_calls=4,allow_extensions=False),model_factory=lambda:model)
            spec=study('random');spec.update(planner='model',rounds=1,pause_at_checkpoints=False)
            request=task(spec);request['constraints'].update(max_model_calls=1,max_tool_calls=4);request['constraints'].pop('require_review')
            bad=copy.deepcopy(request);bad['definitions']=['Additional condition not yet represented in problem.']
            with self.assertRaises(TaskProtocolError) as caught:validate_task(bad)
            self.assertEqual(caught.exception.code,'unformalized_experiment')
            request['objective']+=' Context: the structured problem defines the actual constraints.'
            final=parent.submit(request);self.assert_direct(parent,final,'study_ledger')
            self.assertEqual(final['budget']['used']['model_calls'],1)

    def test_confirmation_cannot_raise_host_limits_and_inputs_cannot_self_approve(self):
        limits=SubagentLimits(max_model_calls=0,max_tool_calls=16,allow_extensions=False,confirm_experiments=True)
        request=self.request(study('random'));request['constraints']['require_review']=False
        policy=limits.resolve(validate_task(request));self.assertTrue(policy['confirm_experiments'])
        self.assertFalse(limits.accepts({**policy,'confirm_experiments':False}))
        request['constraints']['confirm_experiments']=False
        with self.assertRaises(TaskProtocolError):validate_task(request)
        request['constraints'].pop('confirm_experiments');request['constraints']['max_tool_calls']=17
        with self.assertRaises(TaskProtocolError):limits.resolve(validate_task(request))

    def test_budget_identity_and_real_confirmation_remain_pinned(self):
        from graph_research.assistant.experiment_execution import _validate_ledger
        from graph_research.experiments.execution_contract import compile_execution
        from tests.test_experiment_execution import task as explicit_task
        with tempfile.TemporaryDirectory() as folder:
            parent,portal=self.connection(folder);request=explicit_task();final=advance(parent,portal,parent.submit(request))
            self.assertEqual(final['status'],'completed',final.get('error'))
            record=parent._service.read(final['task_id']);compiled=compile_execution(record['request']['execution']['experiment'])
            ledger=record['experiment_ledger'];core=ledger['core_sha256']
            for key in ('request_sha256','core_sha256','policy_sha256'):
                bad=copy.deepcopy(ledger);bad[key]='0'*64
                with self.assertRaises(TaskProtocolError):_validate_ledger(bad,compiled,record,core)
            record['experiment_confirmation']['event_id']='0'*32
            with self.assertRaises(TaskProtocolError):_validate_ledger(ledger,compiled,record,core)

    def test_python_cli_and_mcp_defaults_agree_and_legacy_config_is_only_an_adapter(self):
        from graph_research.mcp.runtime import HostConfiguration
        from graph_research.mcp.cli import parser,configuration
        self.assertFalse(SubagentLimits().confirm_experiments)
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(HostConfiguration(folder,'direct').confirm_experiments)
            old=HostConfiguration(folder,'compat').public();old.pop('confirm_experiments');old['review_policy']='always'
            self.assertTrue(HostConfiguration.from_public(old).confirm_experiments)
            options=parser().parse_args(['--root',folder,'--user','new','--results-root',folder])
            self.assertFalse(configuration(options).confirm_experiments)

    def test_known_startup_blockage_does_not_ask_user_to_confirm_retry(self):
        from graph_research.runtime.runner import WorkerFailure
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder);error=WorkerFailure('fixture access denied',exit_code=107,phase='before_worker_entry')
            with patch('graph_research.assistant.experiment_study.run_worker',side_effect=error):
                final=parent.submit(self.request(study('random')))
            self.assertEqual(final['status'],'blocked')
            self.assertIsNone(final['interaction'])
            self.assertEqual(final['budget']['used']['tool_calls'],1)

    def test_unneeded_confirmation_store_does_not_block_normal_computation(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'.host-events.key').write_bytes(b'broken fixture key')
            parent,portal=self.connection(folder)
            final=parent.submit(self.request(study('random')))
            self.assertEqual(final['status'],'completed',final.get('error'))
            request=self.request(study('random'));request['request_id']='review-with-broken-key';request['constraints']['require_review']=True
            pending=parent.submit(request);self.assertEqual(pending['budget']['used']['tool_calls'],0)
            with self.assertRaises(TaskProtocolError) as caught:
                portal.continue_task(pending['task_id'],pending['interaction']['interaction_id'],pending['revision'])
            self.assertEqual(caught.exception.code,'host_key_invalid')

    def test_event_storage_is_initialized_once_under_concurrent_first_use(self):
        from concurrent.futures import ThreadPoolExecutor
        import time
        with tempfile.TemporaryDirectory() as folder:
            parent,_=self.connection(folder);store=object()
            def create(*args):time.sleep(.01);return store
            with patch('graph_research.assistant.subagent.HostEventStore',side_effect=create) as factory:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    values=list(executor.map(lambda _:parent._service.events,range(4)))
            self.assertTrue(all(value is store for value in values));self.assertEqual(factory.call_count,1)

    def test_pure_planning_error_returns_diagnostic_instead_of_user_confirmation(self):
        from tests.test_feature_workflow import ScriptedModel
        with tempfile.TemporaryDirectory() as folder:
            model=ScriptedModel([{'action':'run','run_id':'unknown','reason':'invalid plan'}])
            parent,_=create_subagent(folder,user_id='bad-planner',limits=SubagentLimits(max_model_calls=1,max_tool_calls=4,allow_extensions=False),model_factory=lambda:model)
            spec=study('random');spec.update(planner='model',pause_at_checkpoints=False)
            request=task(spec);request['constraints'].update(max_model_calls=1,max_tool_calls=4);request['constraints'].pop('require_review')
            final=parent.submit(request)
            self.assertEqual(final['status'],'blocked');self.assertIsNone(final['interaction'])
            self.assertEqual(final['budget']['used'],{'model_calls':1,'tool_calls':0})
            self.assertFalse((Path(folder)/'.host-events.key').exists())

    def test_scope_proposal_returns_to_caller_without_human_approval_or_false_completion(self):
        from tests.test_feature_workflow import ScriptedModel
        with tempfile.TemporaryDirectory() as folder:
            model=ScriptedModel([{'action':'run','run_id':'run1','reason':'pilot'},
                                 {'action':'request_scope_change','reason':'Suggest another finite parameter range.'}])
            parent,_=create_subagent(folder,user_id='scope-proposal',limits=SubagentLimits(max_model_calls=2,max_tool_calls=4,allow_extensions=False),model_factory=lambda:model)
            spec=study('random');spec.update(planner='model',pause_at_checkpoints=False)
            request=task(spec);request['constraints'].update(max_model_calls=2,max_tool_calls=4);request['constraints'].pop('require_review')
            final=parent.submit(request)
            self.assertEqual(final['status'],'analysis_only');self.assertIsNone(final['interaction'])
            self.assertFalse(final['summary']['experiment']['study_complete'])
            self.assertEqual(final['budget']['used'],{'model_calls':2,'tool_calls':1})


class ResearchResourceTests(unittest.TestCase):
    def test_long_study_summary_is_bounded_and_full_view_preserves_all_evidence(self):
        from graph_research.mcp.presentation import result_view
        original={'summary':{'experiment':{'operation':'study','rows_complete':False,'cases':[],
                    'rows':[], 'interpretation':{}}},
                  'artifacts':[{'kind':'scientific_evidence','index':i} for i in range(50)],
                  'results':[{'call_id':f'call-{i:04d}','status':'success','data':{}} for i in range(50)]}
        summary=result_view(original)
        self.assertEqual(len(summary['artifacts']),8)
        self.assertEqual(summary['summary']['artifacts_omitted'],42)
        self.assertEqual(len(summary['results']),8)
        self.assertEqual(summary['results'][0]['call_id'],'call-0042')
        self.assertEqual(summary['summary']['experiment']['result_calls_total'],50)
        self.assertEqual(len(result_view(original,'full')['artifacts']),50)
        self.assertEqual(len(result_view(original,'full')['results']),50)
        self.assertEqual(len(original['results']),50)

    def test_public_research_example_is_valid_and_uses_fifty_calls_without_computation(self):
        example=Path(__file__).resolve().parents[1]/'examples/research-experiments/cem-research-study.json'
        request=validate_task(json.loads(example.read_text(encoding='utf-8')))
        compiled=compile_study(request['execution']['experiment'])
        self.assertEqual((compiled['planned_rounds'],compiled['planned_calls'],compiled['planned_evaluations']),(1000,50,200000))
        self.assertEqual(request['constraints']['max_tool_calls'],50)

    def test_large_research_plan_is_admitted_only_inside_host_authority_without_allocating(self):
        spec=study('cem');spec.update(rounds=1000,batch_size=200,worker_rounds=20,cpu_threads=4)
        spec['budget'].update(max_evaluations=200000,wall_seconds=14400,cpu_seconds=57600,memory_mb=32768)
        compiled=compile_study(spec)
        self.assertEqual((compiled['planned_rounds'],compiled['planned_calls'],compiled['planned_evaluations']),(1000,50,200000))
        request=task(spec);request['constraints']['max_tool_calls']=50
        limits=SubagentLimits(max_model_calls=0,max_tool_calls=50,allow_extensions=False,
            tool_limits=TaskLimits(wall_seconds=900,cpu_seconds=3600,memory_mb=32768,cpu_threads=4))
        if TORCH:
            policy=limits.resolve(validate_task(request));self.assertEqual(policy['tool_limits']['cpu_threads'],4)
        else:
            # Admission can only be observed with the optional CEM dependency present; without
            # it the plan is refused before any budget is consumed, which is the contract here.
            with self.assertRaises(TaskProtocolError) as denied:limits.resolve(validate_task(request))
            self.assertEqual(denied.exception.code,'study_dependency_missing')
        with self.assertRaises(TaskProtocolError) as over_limit:
            SubagentLimits(max_model_calls=0,max_tool_calls=50,allow_extensions=False).resolve(validate_task(request))
        self.assertEqual(over_limit.exception.code,'host_limit_exceeded')
        with self.assertRaises(ValueError):TaskLimits(wall_seconds=MAX_WALL_SECONDS+1)
        with self.assertRaises(ValueError):TaskLimits(memory_mb=MAX_MEMORY_MB+1)

    def test_profiles_and_cpu_wall_units_have_explicit_separate_limits(self):
        with patch('graph_research.runtime.resources.machine_resources',return_value={'logical_cpus':16,'physical_memory_mb':32768}):
            profile=host_profile('research')
        self.assertEqual(profile['tool_memory_mb'],24576)
        self.assertEqual(profile['tool_threads'],15)
        self.assertEqual(profile['tool_cpu_seconds'],15*profile['tool_seconds'])
        self.assertEqual(host_profile('standard')['tool_memory_mb'],1024)
        env=clean_environment('test-workspace',4)
        self.assertEqual(env['OMP_NUM_THREADS'],'4');self.assertEqual(env['OPENBLAS_NUM_THREADS'],'4')

    def test_segment_capacity_and_global_budget_are_checked_before_execution(self):
        spec=study();spec.update(batch_size=4096,worker_rounds=2,rounds=2)
        spec['budget']['max_evaluations']=8192
        with self.assertRaises(TaskProtocolError) as caught:compile_study(spec)
        self.assertEqual(caught.exception.field_path,['worker_rounds'])
        spec=study();spec.update(rounds=1000,batch_size=200,worker_rounds=10)
        with self.assertRaises(TaskProtocolError) as caught:compile_study(spec)
        self.assertEqual(caught.exception.field_path,['budget','max_evaluations'])

    @unittest.skipUnless(TORCH,'Optional CPU torch missing')
    def test_one_policy_survives_multiple_generations_with_identical_trajectory_and_checkpoint(self):
        from graph_research.experiments.neural_search import Policy
        compiled,a=round_args(study('cem'))
        expected=[];previous=None
        for number in range(1,4):
            result=run_round({**a,'round':number,'checkpoint':previous});expected.append(result);previous=result['checkpoint']
        with tempfile.TemporaryDirectory() as folder:
            with patch('graph_research.experiments.neural_search.Policy',side_effect=Policy) as creation:
                result=run_segment({**a,'round_count':3},directory=folder)
            self.assertEqual(creation.call_count,1)
            self.assertEqual(list(round_records(result,folder)),json.loads(json.dumps(expected)))
            self.assertEqual(result['checkpoint'],previous);self.assertEqual(result['evaluations_completed'],12)
            self.assertLessEqual(len(result['rows']),8);self.assertFalse(result['rows_complete'])
            self.assertTrue(verify_segment({**a,'round_count':3},result,folder))

    def test_streamed_analysis_covers_every_candidate_and_archive_tampering_fails(self):
        spec=study('random');spec.update(batch_size=16,rounds=3,worker_rounds=3)
        spec['budget']['max_evaluations']=48
        spec['hypotheses']=[{'id':'bound','type':'metric_bound','relation':'le','value':1}]
        compiled,a=round_args(spec)
        with tempfile.TemporaryDirectory() as folder:
            value=run_segment({**a,'round_count':3},directory=folder)
            def rows():
                for result in round_records(value,folder):
                    for row in result['rows']:yield {'run_id':result['run_id'],'round':result['round'],**row}
            report=analyze_streamed(compiled,[value],rows,spec['hypotheses'])
            self.assertEqual(report['run_statistics'][0]['evaluated'],48)
            self.assertEqual(report['hypothesis_checks'][0]['tested'],48)
            self.assertEqual(report['hypothesis_checks'][0]['status'],'verified_counterexample')
            self.assertTrue(report['analysis_complete'])
            bad=copy.deepcopy(value);bad['rows_archive']['path']='../private.json'
            with self.assertRaises(ValueError):verify_segment({**a,'round_count':3},bad,folder)
            path=Path(folder)/value['rows_archive']['path'];path.write_text('{}\n',encoding='utf-8')
            with self.assertRaises(ValueError):verify_segment({**a,'round_count':3},value,folder)

    @unittest.skipUnless(TORCH,'Optional CPU torch missing')
    def test_protected_multigeneration_resume_feedback_and_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            spec=study('cem');spec.update(rounds=5,worker_rounds=2,segment_rounds=1)
            spec['budget']['max_evaluations']=20
            request=task(spec);request['constraints']['max_tool_calls']=3
            limits=SubagentLimits(max_model_calls=0,max_tool_calls=3,allow_extensions=False)
            def connection():return create_subagent(folder,user_id='persistent-test',limits=limits)
            parent,portal=connection();first=parent.submit(request)
            self.assertEqual(first['budget']['used']['tool_calls'],0)
            paused=advance(parent,portal,first)
            self.assertEqual(paused['status'],'waiting_for_user',paused.get('error'))
            self.assertEqual(paused['summary']['experiment']['rounds_completed'],2)
            self.assertEqual(paused['summary']['experiment']['evaluations_completed'],8)
            receipt=paused['results'][0]['verification']['receipt_sha256']
            parent,portal=connection()
            event=portal.study_feedback(paused['task_id'],paused['interaction']['interaction_id'],paused['revision'],{'knobs':{'exploration':.3}})
            again=parent.resume(paused['task_id'],event['event_id'])
            self.assertEqual(again['summary']['experiment']['rounds_completed'],4)
            final=advance(parent,portal,again)
            self.assertEqual(final['status'],'completed',final.get('error'))
            experiment=final['summary']['experiment']
            self.assertEqual((experiment['evaluations_completed'],experiment['rounds_completed'],experiment['jobs_completed']),(20,5,3))
            self.assertEqual(final['budget']['used'],{'model_calls':0,'tool_calls':3})
            self.assertEqual(final['results'][0]['verification']['receipt_sha256'],receipt)
            self.assertTrue(experiment['interpretation']['analysis_complete'])
            self.assertEqual(experiment['interpretation']['run_statistics'][0]['evaluated'],20)
            artifact=final['artifacts'][0];self.assertTrue(verify_bundle(artifact['path'],artifact['sha256'])['ok'])
            self.assertEqual(len([a for a in final['artifacts'] if a['kind']=='scientific_evidence']),3)
            with zipfile.ZipFile(artifact['path']) as bundle:
                self.assertEqual(len([n for n in bundle.namelist() if n.endswith('search-rounds.jsonl')]),3)

    def test_streamed_evidence_remains_readable_when_the_aggregate_bundle_cannot_export(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        with tempfile.TemporaryDirectory() as folder:
            spec=study('random');spec.update(rounds=2,worker_rounds=2)
            request=task(spec);request['constraints']['max_tool_calls']=1
            parent,portal=create_subagent(folder,user_id='evidence-only',limits=SubagentLimits(max_model_calls=0,max_tool_calls=1,allow_extensions=False))
            with patch('graph_research.assistant.session.ResearchSession._export_results',side_effect=ValueError('fixture aggregate export limit')):
                final=advance(parent,portal,parent.submit(request))
            self.assertEqual(final['status'],'partial')
            self.assertTrue(final['summary']['experiment']['study_complete'])
            self.assertFalse(final['summary']['output_complete'])
            self.assertEqual(final['artifacts'][0]['kind'],'scientific_evidence')
            runtime=MCPResearchRuntime(HostConfiguration(folder,'evidence-only'))
            data=runtime.read_artifact(final['task_id'],0)
            raw=base64.b64decode(data['data_base64'])
            self.assertEqual(json.loads(raw.splitlines()[0])['round'],1)
            if importlib.util.find_spec('mcp') is not None:
                from mcp.client import Client
                from graph_research.mcp.server import create_server
                async def read_resource():
                    async with Client(create_server(runtime),mode='legacy',cache=None) as client:
                        response=await client.read_resource(f'graph-research://tasks/{final["task_id"]}/artifacts/0')
                        self.assertEqual(response.contents[0].mime_type,'application/x-ndjson')
                        self.assertEqual(base64.b64decode(response.contents[0].blob),raw)
                asyncio.run(read_resource())
            target=Path(final['artifacts'][0]['path'])
            with target.open('ab') as stream:stream.write(b'\n')
            with self.assertRaises(TaskProtocolError) as caught:runtime.artifact(final['task_id'],0)
            self.assertEqual(caught.exception.code,'artifact_changed')


if __name__=='__main__':unittest.main()
