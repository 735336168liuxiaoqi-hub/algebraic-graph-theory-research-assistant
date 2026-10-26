"""Experiment phase 1: bounded drafts, explicit gaps, no search or model execution."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import jsonschema

from graph_research.experiments import prepare_experiment,experiment_contracts
from graph_research.experiments.research_contract import validate_problem
from graph_research.assistant.task_contract import validate_task,TaskProtocolError,contracts

ROOT=Path(__file__).resolve().parents[1]


def sample(name='clique-free'):
    return json.loads((ROOT/'examples/research-experiments'/(name+'-prepare.json')).read_text(encoding='utf-8'))


class ExperimentContractTests(unittest.TestCase):
    def test_both_families_use_same_contract_and_need_no_numeric_parameter_values(self):
        for name in ('clique-free','hypertree-distance'):
            task=validate_task(sample(name));report=prepare_experiment(task['execution']['experiment'])
            self.assertTrue(report['plan']['cases']);self.assertFalse(report['executed'])
            self.assertFalse(report['plan']['executable']);self.assertNotIn('approved',report['plan'])
            self.assertFalse(report['plan']['scientific_results']);self.assertFalse(report['claims'])
            jsonschema.validate(task,contracts()['task_input'])
            jsonschema.validate(report['plan'],experiment_contracts()['plan'])

    def test_hypertree_degree_count_order_and_distance_matrix_semantics_remain_distinct(self):
        report=prepare_experiment(sample('hypertree-distance')['execution']['experiment'])
        for case in report['plan']['cases']:
            p=case['parameters'];self.assertEqual(case['derived']['order'],1+(p['k']-1)*p['m'])
            self.assertLessEqual(p['q'],case['derived']['order']);self.assertGreaterEqual(p['Delta'],3)
        self.assertEqual(report['problem']['objective']['metric'],'distance_spectral_radius')
        bad=copy.deepcopy(report['problem']);bad['object']['order']={'parameter':'q'}
        with self.assertRaises(TaskProtocolError):validate_problem(bad)

    def test_deterministic_bounded_sampling_and_honest_estimates(self):
        request=sample()['execution']['experiment'];request['max_cases']=3
        a=prepare_experiment(request);b=prepare_experiment(request)
        self.assertEqual(a,b);self.assertLessEqual(len(a['plan']['cases']),3)
        self.assertFalse(a['plan']['coverage']['enumeration_complete'])
        self.assertIsNone(a['plan']['estimate']['wall_seconds_prediction'])
        self.assertEqual(a['plan']['estimate']['candidate_evaluations'],0)
        self.assertEqual(a['literature_status'],'not_searched')

    def test_unknown_capability_is_a_gap_not_executable_code(self):
        request=sample()['execution']['experiment'];request['problem']['objective']['metric']='unregistered_metric'
        report=prepare_experiment(request)
        self.assertEqual(report['plan']['status'],'capability_gap');self.assertFalse(report['executed'])

    def test_invalid_numbers_references_authority_and_modes_are_rejected(self):
        for update in ({'value':'__import__("os")'},{'value':'1/0'},{'value':float('nan')},{'value':True},{'value':'1/2'}):
            problem=sample()['execution']['experiment']['problem'];problem['parameters']['n']={'kind':'integer','role':'fixed','meaning':'order',**update}
            with self.subTest(update=update),self.assertRaises(TaskProtocolError):validate_problem(problem)
        task=sample();task['execution']['experiment']['problem']['object']['order']={'parameter':'missing'}
        with self.assertRaises(TaskProtocolError):validate_task(task)
        for key,value in [('approved',True),('operation','execute')]:
            task=sample();task['execution']['experiment'][key]=value
            with self.assertRaises(TaskProtocolError):validate_task(task)
        task=sample();task['execution']['steps']=[{'id':'x','tool':'graph_invariants','arguments':{}}]
        with self.assertRaises(TaskProtocolError):validate_task(task)

    def test_boolean_constraints_are_not_flattened_into_mandatory_requirements(self):
        request=sample()['execution']['experiment'];p=request['problem'];p['constraints']={'any':[
            {'predicate':'edge_count','arguments':{'value':999}},
            {'predicate':'edge_count','arguments':{'value':0}}]}
        self.assertTrue(prepare_experiment(request)['plan']['cases'])
        p['constraints']={'all':p['constraints']['any']}
        report=prepare_experiment(request)
        self.assertFalse(report['plan']['cases']);self.assertFalse(report['plan']['scientific_results'])

    def test_unfixed_global_extremum_requires_mathematical_interpretation(self):
        request=sample()['execution']['experiment'];request['problem']['intent']='extremum'
        self.assertEqual(prepare_experiment(request)['plan']['status'],'needs_clarification')

    def test_preparation_imports_no_training_or_external_runtime_packages(self):
        script="""
import builtins,json,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name.split('.')[0] in {'torch','jpype','jdk4py','sage'}:raise AssertionError('Unexpected dependency: '+name)
 return original(name,*args,**kwargs)
builtins.__import__=guarded
from graph_research.experiments import prepare_experiment
task=json.loads(sys.stdin.read())
assert prepare_experiment(task['execution']['experiment'])['executed'] is False
"""
        result=subprocess.run([sys.executable,'-X','utf8','-c',script],input=json.dumps(sample()),capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)


class ExperimentEntryTests(unittest.TestCase):
    def test_documented_cli_envelopes_match_tasks_and_run_without_api(self):
        for name in ('clique-free','hypertree-distance'):
            path=ROOT/'examples/research-experiments'/(name+'-request.json')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),{'operation':'submit','task':sample(name)})
        with tempfile.TemporaryDirectory() as folder:
            result=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','subagent','--root',folder,'--user','experiment',
                                   '--input',str(path)],capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
            self.assertEqual(result.returncode,0,result.stderr)
            value=json.loads(result.stdout);self.assertEqual(value['status'],'analysis_only')
            self.assertEqual(value['budget']['used'],{'model_calls':0,'tool_calls':0})

    def test_mcp_accepts_prepare_without_internal_api_and_summary_remains_bounded(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        with tempfile.TemporaryDirectory() as folder:
            runtime=MCPResearchRuntime(HostConfiguration(folder,'experiment',max_tool_calls=0))
            try:
                with patch.object(runtime,'_launch') as launch:
                    submitted=runtime.submit(sample());self.assertEqual(launch.call_count,1)
                runtime.parent.start_queued(submitted['task_id'])
                full=runtime.get(submitted['task_id'],detail='full')
                compact=runtime.get(submitted['task_id'])
                self.assertEqual(full['status'],'analysis_only')
                self.assertIn('problem',full['summary']['experiment']);self.assertNotIn('problem',compact['summary']['experiment'])
                self.assertLessEqual(len(compact['summary']['experiment']['plan']['cases']),8)
                self.assertFalse(full['summary']['experiment']['executed'])
            finally:
                for process in runtime.children.values():
                    if process.poll() is None:process.terminate();process.wait(5)
    def test_subagent_prepare_replays_and_bundles_without_model_or_tool_calls(self):
        from graph_research.assistant import create_subagent,SubagentLimits
        with tempfile.TemporaryDirectory() as folder:
            parent,_=create_subagent(folder,user_id='experiment',limits=SubagentLimits(max_model_calls=0,max_tool_calls=0,allow_extensions=False),
                                    model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model')))
            with patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('No computation')):
                response=parent.submit(sample());again=parent.submit(sample())
            self.assertEqual(response['status'],'analysis_only');self.assertTrue(response['terminal'])
            self.assertFalse(response['summary']['execution_complete']);self.assertTrue(response['summary']['preparation_complete'])
            self.assertEqual(response['budget']['used'],{'tool_calls':0,'model_calls':0})
            self.assertEqual(response['task_id'],again['task_id']);self.assertEqual(response['revision'],again['revision'])
            archive=next(a for a in response['artifacts'] if a['kind']=='result_bundle')['path']
            with zipfile.ZipFile(archive) as z:
                self.assertIn('experiment-plan.json',z.namelist());self.assertIn('experiment-problem.json',z.namelist())
                self.assertFalse(json.loads(z.read('experiment-preparation.json'))['executed'])

    def test_text_definitions_are_not_silently_accepted_as_constraints(self):
        from graph_research.assistant import create_subagent,SubagentLimits
        with tempfile.TemporaryDirectory() as folder:
            parent,_=create_subagent(folder,user_id='experiment',limits=SubagentLimits(max_model_calls=0,max_tool_calls=0,allow_extensions=False))
            task=sample();task['definitions']=['还需要满足某个未形式化的条件']
            result=parent.submit(task)
            issues=result['summary']['experiment']['plan']['issues']
            self.assertTrue(any(item['code']=='text_definitions' and item['kind']=='notice' for item in issues))
            self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':0})


if __name__=='__main__':unittest.main()
