"""External feedback regressions: coverage, actionable errors and tensor studies."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from graph_research.assistant import create_subagent,SubagentLimits
from graph_research.assistant.task_contract import validate_task,TaskProtocolError
from graph_research.assistant.batch_workflow import compile_batch
from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
from graph_research.mcp.presentation import result_view
from graph_research.runtime.observability import error_details
from graph_research.experiments import prepare_experiment
from graph_research.experiments.adapters import evaluate_candidate
from graph_research.experiments.verification import verify_evaluation
from tests.test_experiment_evaluation import problem,STAR,LOOSE_PATH,LOOSE_CYCLE
from tests.test_experiment_study import study,round_args


def fixed(request_id='failure',on_error=None):
    task={'version':1,'request_id':request_id,'objective':'核对失败、依赖与独立步骤',
        'execution':{'mode':'tools','steps':[
            {'id':'first','tool':'graph_invariants','arguments':{'kind':'path','n':2}},
            {'id':'bad','tool':'graph_invariants','arguments':{'kind':'path','n':999}},
            {'id':'dependent','tool':'matrix_analysis','arguments':{},'bindings':{'matrix':{'step':'bad','path':['matrix']}}},
            {'id':'independent','tool':'graph_invariants','arguments':{'kind':'path','n':4}}]}}
    if on_error:task['execution']['on_error']=on_error
    return task


class FixedCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.parent,_=create_subagent(self.tmp.name,user_id='audit',limits=SubagentLimits(max_model_calls=0,max_tool_calls=8,allow_extensions=False))

    def test_stop_reports_every_step_without_charging_skips(self):
        result=self.parent.submit(fixed())
        self.assertEqual([r['status'] for r in result['results']],['success','failed','skipped','skipped'])
        self.assertEqual(result['budget']['used']['tool_calls'],2)
        self.assertFalse(result['summary']['execution_complete']);self.assertFalse(result['summary']['output_complete'])
        self.assertTrue(result['warnings'])
        self.assertNotIn('call_id',result['results'][-1])

    def test_basic_tools_do_not_enter_experiment_or_learning_workflow(self):
        task=fixed('basic-isolation');task['execution']['steps']=task['execution']['steps'][:1]
        with patch('graph_research.assistant.experiment.run_experiment',side_effect=AssertionError('Basic tools must not enter experiments')):
            result=self.parent.submit(task)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':1})

    def test_continue_independent_skips_only_dependencies_and_replay_is_read_only(self):
        task=fixed(on_error='continue_independent');result=self.parent.submit(task)
        states={r['step_id']:r['status'] for r in result['results']}
        self.assertEqual(states,{'first':'success','bad':'failed','dependent':'skipped','independent':'success'})
        self.assertEqual(result['budget']['used']['tool_calls'],3)
        self.assertFalse(result['summary']['execution_complete']);self.assertFalse(result['summary']['output_complete'])
        with patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('Replay must not compute')):
            again=self.parent.submit(task)
        self.assertEqual(again['results'],result['results']);self.assertEqual(again['budget']['used']['tool_calls'],3)

    def test_budget_fail_fast_is_admission_and_both_modes_keep_coverage_honest(self):
        task=fixed();task['constraints']={'max_tool_calls':1,'fail_fast':True}
        with self.assertRaises(TaskProtocolError) as caught:self.parent.submit(task)
        self.assertEqual(caught.exception.code,'tools_budget_insufficient')
        task['constraints']['fail_fast']=False
        result=self.parent.submit(task)
        self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(len(result['results']),4)
        self.assertFalse(result['summary']['execution_complete']);self.assertFalse(result['summary']['output_complete'])

    def test_explicit_outputs_are_checked_and_advisory_text_cannot_claim_delivery(self):
        task=fixed('outputs');task['execution']['steps']=task['execution']['steps'][:1]
        task['expected_outputs']=[{'name':'order','step':'first','path':['order']}]
        good=self.parent.submit(task);self.assertTrue(good['summary']['output_complete'])
        task['request_id']='missing';task['expected_outputs'][0]['path']=['bogus_key_xyz']
        bad=self.parent.submit(task)
        self.assertEqual(bad['status'],'partial');self.assertTrue(bad['summary']['execution_complete'])
        self.assertFalse(bad['summary']['output_complete']);self.assertEqual(bad['summary']['expected_outputs']['status'],'missing')
        task['request_id']='advisory';task['expected_outputs']=['order','bogus_key_xyz']
        hints=self.parent.submit(task)
        self.assertTrue(hints['summary']['computed_outputs_complete']);self.assertFalse(hints['summary']['output_complete'])
        self.assertEqual(hints['summary']['expected_outputs']['status'],'not_validated')

    def test_missing_binding_path_continues_without_retrying_or_charging(self):
        task=fixed(on_error='continue_independent');task['execution']['steps'][1]['arguments']['n']=3
        task['execution']['steps'][2]['bindings']['matrix']['path']=['not_a_matrix']
        result=self.parent.submit(task)
        self.assertEqual(result['budget']['used']['tool_calls'],3)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(next(r for r in result['results'] if r['step_id']=='dependent')['reason'],'binding_path_unavailable')
        self.assertFalse(result['summary']['output_complete'])


class DiagnosticTests(unittest.TestCase):
    def test_union_error_selects_matching_operation_then_exact_missing_field(self):
        p=problem();p.pop('parameters')
        task={'version':1,'request_id':'invalid','objective':'test','execution':{'mode':'experiment','experiment':{'operation':'prepare','problem':p}}}
        with self.assertRaises(TaskProtocolError) as caught:validate_task(task)
        self.assertEqual(caught.exception.field_path,['execution','experiment','problem','parameters'])
        self.assertIn('required',caught.exception.validation)
        p['parameters']={};p['constraints']=[]
        with self.assertRaises(TaskProtocolError) as caught:validate_task(task)
        self.assertEqual(caught.exception.field_path,['execution','experiment','problem','constraints'])
        self.assertTrue(caught.exception.validation)

    def test_batch_binding_conflict_identifies_step_and_field(self):
        task={'execution':{'mode':'batch','batch':{'steps':[{'id':'broken','tool':'graph_invariants','arguments':{'n':3},'bindings':{'n':{'input':['n']}}}]}}}
        with self.assertRaises(TaskProtocolError) as caught:compile_batch(task)
        detail=error_details(caught.exception)
        self.assertEqual(detail['step_id'],'broken');self.assertEqual(detail['field_path'],['execution','batch','steps',0,'bindings','n'])

    def test_counterexample_constraints_are_actionable_in_protected_worker(self):
        from graph_research.runtime.runner import run_tool
        with tempfile.TemporaryDirectory() as tmp:
            try:run_tool('graph_counterexample_verify',{'reference':{'kind':'path','n':6},'candidate':{'kind':'cycle','n':6}},Path(tmp)/'tools',directory=Path(tmp)/'tasks')
            except Exception as exc:
                detail=error_details(exc);self.assertEqual(detail['phase'],'argument_validation')
                self.assertEqual(detail['field_path'],['candidate','edges']);self.assertEqual(detail['cause_code'],'invalid_field')
            else:self.fail('Invalid candidate accepted')

    def test_catalog_discovers_metrics_unknown_ids_have_suggestions(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog=MCPResearchRuntime(HostConfiguration(tmp,'catalog',approval_ui='off')).catalog()
        metrics=catalog['capabilities']['experiment_preparation']['metrics']
        self.assertIn('adjacency_spectral_radius',[m['id'] for m in metrics])
        p=problem('spectral_radius');plan=prepare_experiment({'operation':'prepare','problem':p})['plan']
        self.assertEqual(plan['capabilities'][0]['status'],'unknown')
        self.assertIn('adjacency_spectral_radius',plan['capabilities'][0]['suggestions'])

    def test_full_inspect_arguments_and_skips_have_no_invented_call_ids(self):
        value={'task_id':'a'*32,'summary':{},'results':[{'status':'success','call_id':'call-0001','data':{'spectrum':list(range(200))}},
            {'status':'skipped','step_id':'later','tool':'graph_spectrum'}]}
        view=result_view(value,'summary')
        self.assertEqual(view['results'][0]['read_more'],{'tool':'research_inspect_result','task_id':'a'*32,'call_id':'call-0001','path':[]})
        self.assertNotIn('read_more',view['results'][1])


class TensorExperimentTests(unittest.TestCase):
    def test_protected_execute_and_study_need_no_model_or_user_confirmation(self):
        p=problem(kind='uniform_hypertree');p['object']['type']='uniform_hypergraph';p['objective']['arguments']['alpha']='999/1000'
        spec={'operation':'execute','problem':p,'cases':[{'id':'sample','parameters':{},'candidates':[STAR,LOOSE_CYCLE]}],
            'chunk_size':1,'budget':{'max_evaluations':2,'wall_seconds':60,'cpu_seconds':60,'memory_mb':1024}}
        with tempfile.TemporaryDirectory() as tmp:
            parent,_=create_subagent(tmp,user_id='tensor',limits=SubagentLimits(max_model_calls=0,max_tool_calls=4,allow_extensions=False))
            task={'version':1,'request_id':'tensor-execute','objective':'高alpha一致超图有限实验','execution':{'mode':'experiment','experiment':spec}}
            result=parent.submit(task)
            self.assertEqual(result['status'],'completed');self.assertTrue(result['summary']['output_complete'])
            self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':2})
            spec=study('random','uniform_hypergraph');spec.update(rounds=1,batch_size=2,pause_at_checkpoints=False)
            spec['problem']['objective']=p['objective']
            task['request_id']='tensor-study';task['execution']['experiment']=spec
            result=parent.submit(task)
            self.assertEqual(result['status'],'completed');self.assertTrue(result['summary']['execution_complete'])
            self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':1})

    def test_high_alpha_endpoints_rational_parameters_and_cyclic_hypergraph(self):
        for alpha in (0,'1/3','99/100','999/1000',1):
            p=problem(kind='uniform_hypertree');p['objective']['arguments']['alpha']=alpha
            for graph in (STAR,LOOSE_PATH):
                with self.subTest(alpha=alpha,graph=graph):
                    row=evaluate_candidate(p,{},graph);self.assertTrue(row['feasible']);self.assertTrue(row['verification']['passed'])
                    self.assertEqual(Fraction(row['certificate']['alpha']),Fraction(alpha))
                    lo,hi=map(Fraction,row['objective_interval']);self.assertLessEqual(lo,hi)
                    self.assertLess(float(hi-lo),1e-7)
        p['object']['type']='uniform_hypergraph';row=evaluate_candidate(p,{},LOOSE_CYCLE)
        self.assertTrue(row['feasible']);self.assertFalse(row['properties']['hypertree'])

    def test_adjacency_tensor_normalization_matches_single_edge_and_rank_two(self):
        p=problem('adjacency_spectral_radius','uniform_hypertree')
        row=evaluate_candidate(p,{}, {'n':3,'edges':[[0,1,2]]});self.assertAlmostEqual(row['objective_estimate'],1)
        p['object']['uniformity']=2
        row=evaluate_candidate(p,{}, {'n':3,'edges':[[0,1],[1,2]]});self.assertAlmostEqual(row['objective_estimate'],2**.5)

    def test_verification_uses_no_solver_and_rejects_tampered_evidence(self):
        p=problem(kind='uniform_hypertree');row=evaluate_candidate(p,{},STAR)
        with patch('graph_research.hypergraphs.Hypergraph.alpha_spectrum',side_effect=AssertionError('Verifier must not solve')):
            self.assertTrue(verify_evaluation(p,{},STAR,row)['passed'])
            for key in ('interval','vector','alpha','score'):
                bad=copy.deepcopy(row)
                if key=='interval':bad['certificate']['interval']=['0','0']
                elif key=='vector':bad['certificate']['vector'][0]=0
                elif key=='alpha':bad['certificate']['alpha']='1'
                else:bad['objective_estimate']=99
                self.assertFalse(verify_evaluation(p,{},STAR,bad)['passed'])

    def test_disconnected_empty_and_nonuniform_domains_are_not_solver_failures(self):
        p=problem(kind='uniform_hypertree');p['object']['type']='uniform_hypergraph'
        graph={'n':6,'edges':[[0,1,2],[3,4,5]]}
        self.assertFalse(evaluate_candidate(p,{},graph)['metric_domain_satisfied'])
        self.assertFalse(evaluate_candidate(p,{}, {'n':3,'edges':[]})['metric_domain_satisfied'])
        p['objective']['arguments']['alpha']=1
        self.assertEqual(evaluate_candidate(p,{},graph)['objective_estimate'],1)
        p['object']['type']='hypergraph';p['object'].pop('uniformity')
        with self.assertRaises(ValueError):evaluate_candidate(p,{},graph)

    def test_simple_graph_output_uses_graph_terms(self):
        from graph_research.experiments.interpretation import features
        row=evaluate_candidate(problem('edge_count'),{}, {'n':3,'edges':[[0,1],[1,2]]})
        self.assertTrue(row['properties']['is_tree']);self.assertNotIn('uniform',row['properties']);self.assertNotIn('hypertree',row['properties'])
        description=features({'n':3,'edges':[[0,1],[1,2]]},'simple_graph')
        self.assertTrue(description['is_tree']);self.assertNotIn('hypertree',description)

    def test_tensor_objective_runs_through_existing_search_and_round_verification(self):
        from graph_research.experiments.search_engine import run_round,verify_round
        spec=study('random','uniform_hypergraph');spec['problem']['objective']={'metric':'alpha_spectral_radius','direction':'maximize','arguments':{'alpha':'99/100'}}
        _,arguments=round_args(spec);arguments['limit']=2
        result=run_round(arguments);self.assertTrue(verify_round(arguments,result))
        self.assertTrue(all(r['verification']['passed'] for r in result['rows']))
