"""Search, CPU CEM recovery, planning limits, feedback and scoped counterevidence."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import create_subagent,SubagentLimits
from graph_research.assistant.task_contract import TaskProtocolError
from graph_research.experiments.search_contract import compile_study
from graph_research.experiments.search_engine import run_round,verify_round
from graph_research.experiments.search_space import random_candidate,mutate,decisions
from graph_research.experiments.controller import propose,checked_action
from graph_research.experiments.interpretation import features,isomorphic,analyze
from graph_research.assistant import experiment_study as engine
from tests.test_experiment_evaluation import problem
from tests.test_experiment_execution import advance
from tests.test_feature_workflow import ScriptedModel

TORCH=importlib.util.find_spec('torch') is not None


def study(method='random',kind='simple_graph'):
    p=problem('edge_count',kind);p['object']['order']=4
    if kind in ('uniform_hypergraph','uniform_hypertree'):p['object'].update(order=7,uniformity=3)
    return {'operation':'study','problem':p,'cases':[{'id':'case1','parameters':{}}],'methods':[method],'seeds':[11],
        'rounds':2,'batch_size':4,'max_edges':4,'adaptive':False,
        'budget':{'max_evaluations':64,'wall_seconds':120,'cpu_seconds':120,'memory_mb':1024}}


def task(spec):
    return {'version':1,'request_id':'study-test','objective':'Test finite reviewed research',
        'execution':{'mode':'experiment','experiment':spec},'constraints':{'max_model_calls':8 if spec.get('planner')=='model' else 0,'max_tool_calls':16,'allow_extensions':False}}


def round_args(spec):
    c=compile_study(spec);return c,{'problem':c['spec']['problem'],'run':c['runs'][0],
        'settings':{k:c['spec'][k] for k in ('max_edges','max_actions','edge_sizes') if k in c['spec']},
        'knobs':c['spec']['knobs'],'round':1,'checkpoint':None,'limit':c['spec']['batch_size']}


class SearchTests(unittest.TestCase):
    def test_enumeration_is_complete_labelled_and_tamper_resistant(self):
        s=study('enumerate');s['problem']['object']['order']=3;s['max_edges']=3;s['batch_size']=8
        c,a=round_args(s);result=run_round(a)
        self.assertTrue(verify_round(a,result));self.assertTrue(result['enumeration']['complete'])
        self.assertEqual(len({r['candidate_sha256'] for r in result['rows']}),8)
        bad=copy.deepcopy(result);bad['rows'][0]=bad['rows'][1]
        with self.assertRaises(ValueError):verify_round(a,bad)

    def test_same_seed_random_local_and_resume_are_reproducible(self):
        for method in ('random','local'):
            _,a=round_args(study(method));first=run_round(a);self.assertEqual(first,run_round(a))
            b={**a,'round':2,'checkpoint':json.loads(json.dumps(first['checkpoint']))}
            second=run_round(b);self.assertTrue(verify_round(b,second));self.assertEqual(second,run_round(b))

    def test_uniform_and_nonuniform_generators_allow_cycles_not_just_trees(self):
        for kind in ('uniform_hypergraph','hypergraph'):
            _,a=round_args(study('random',kind));domain=a['run']['space'];seen_cycle=False
            for seed in range(20):
                g=random_candidate(domain,random.Random(seed));seen_cycle|=not features(g,kind)['hypertree']
            self.assertTrue(seen_cycle);self.assertFalse(domain['tree'])
        s=study('local','uniform_hypertree');_,a=round_args(s);g=random_candidate(a['run']['space'],random.Random(1))
        self.assertTrue(features(mutate(a['run']['space'],g,random.Random(2)),'uniform_hypertree')['hypertree'])

    def test_connected_constructions_cover_large_order_without_impossible_default_edge_cap(self):
        for kind,k in [('simple_graph',None),('uniform_hypergraph',3),('hypergraph',None)]:
            s=study('random',kind);s['problem']['objective']['metric']='distance_spectral_radius';s['problem']['object']['order']=128;s.pop('max_edges')
            if k:s['problem']['object']['uniformity']=k
            c=compile_study(s);g=random_candidate(c['runs'][0]['space'],random.Random(11))
            self.assertEqual(features(g,kind)['component_count'],1)
            self.assertEqual(g['n'],128)

    def test_resource_bound_and_sparse_hypergraph_representation(self):
        s=study('cem','uniform_hypergraph');s['problem']['object'].update(order=128,uniformity=3);s['max_edges']=4
        _,a=round_args(s);steps=[]
        g=decisions(a['run']['space'],lambda f,legal:(steps.append(len(f)) or legal[0]))
        self.assertLessEqual(len(steps),17);self.assertTrue(all(length==260 for length in steps))
        s=study('cem');s['problem']['object']['order']=128
        with self.assertRaises(TaskProtocolError):compile_study(s)

    def test_guidance_change_rescores_elites_without_changing_raw_metrics(self):
        _,a=round_args(study());first=run_round(a)
        b={**a,'round':2,'checkpoint':first['checkpoint'],'knobs':{**a['knobs'],'penalty_weight':2}}
        second=run_round(b);self.assertTrue(verify_round(b,second))
        self.assertNotEqual(first['reward_version'],second['reward_version']);self.assertGreater(second['cached_elites_rescored'],0)

    def test_symmetric_hypergraph_has_incidence_skeleton_and_max_degree_profile(self):
        graph={'n':7,'edges':[[0,1,2],[2,3,4],[4,5,6]]}
        f=features(graph,'uniform_hypergraph')
        self.assertEqual(f['maximum_degree_vertices'],[2,4]);self.assertEqual(f['maximum_degree_distance_profile'],[1])
        self.assertTrue(f['incidence_skeleton'])

    def test_equal_evaluation_fixed_and_adaptive_controls_keep_raw_metrics(self):
        s=study();c,a=round_args(s);fixed=[];adaptive=[];last=None
        for i in range(1,3):
            args={**a,'round':i,'checkpoint':last};result=run_round(args);fixed.extend(result['rows']);last=result['checkpoint']
        last=None
        for i in range(1,3):
            args={**a,'round':i,'checkpoint':last,'knobs':{**a['knobs'],'exploration':0.25}};result=run_round(args);adaptive.extend(result['rows']);last=result['checkpoint']
        self.assertEqual(len(fixed),len(adaptive));self.assertTrue(all('objective_estimate' in r and 'training_score' in r for r in fixed+adaptive))

    def test_structure_recognition_is_not_degree_sequence_isomorphism(self):
        cycle={'n':6,'edges':[[i,(i+1)%6] for i in range(6)]}
        triangles={'n':6,'edges':[[0,1],[1,2],[0,2],[3,4],[4,5],[3,5]]}
        self.assertEqual(features(cycle,'simple_graph')['degree_histogram'],features(triangles,'simple_graph')['degree_histogram'])
        self.assertIsNone(isomorphic(cycle,triangles,'simple_graph'))
        permuted={'n':6,'edges':[[5-u,5-v] for u,v in cycle['edges']]}
        self.assertIsNotNone(isomorphic(cycle,permuted,'simple_graph'))

    def test_numeric_and_structure_hypotheses_have_actual_counterwitnesses(self):
        s=study('enumerate');s['problem']['object']['order']=3;s['max_edges']=3;s['batch_size']=8
        s['hypotheses']=[{'id':'bound','type':'metric_bound','relation':'le','value':1},
            {'id':'structure','type':'universal_structure','property':'bipartite','expected':True},
            {'id':'pattern','type':'candidate_pattern','property':'bipartite','expected':True}]
        c,a=round_args(s);r=run_round(a);report=analyze(c,[r])
        self.assertEqual([h['status'] for h in report['hypothesis_checks']],['verified_counterexample','verified_counterexample','pattern_contradicted'])
        self.assertTrue(report['finite_coverage']);self.assertFalse(report['general_theorem_proved'])
        self.assertTrue(all(not h['proven'] for h in report['hypothesis_checks']))
        self.assertTrue(all(c['independent_seeds']==0 for c in report['candidate_conjectures']))

    def test_free_parameters_get_reviewable_cases_without_fixed_values(self):
        sample=json.loads((Path(__file__).resolve().parents[1]/'examples/research-experiments/clique-free-prepare.json').read_text(encoding='utf-8'))['execution']['experiment']['problem']
        s=study();s.pop('cases');s['problem']=sample;s['case_limit']=2
        c=compile_study(s);self.assertEqual(len(c['spec']['cases']),2)
        with self.assertRaises(ValueError):checked_action({'action':'run','run_id':'notapproved','reason':'try big n'},c,[])

    @unittest.skipUnless(TORCH,'Optional CPU torch not installed')
    def test_cpu_cem_json_checkpoint_preserves_weights_momentum_and_trajectory_sequence(self):
        for kind in ('simple_graph','uniform_hypergraph','uniform_hypertree'):
            _,a=round_args(study('cem',kind));first=run_round(a);self.assertTrue(verify_round(a,first))
            b={**a,'round':2,'checkpoint':first['checkpoint']};continuous=run_round(b)
            resumed=run_round({**b,'checkpoint':json.loads(json.dumps(first['checkpoint']))})
            self.assertEqual(continuous,resumed);self.assertGreater(resumed['checkpoint']['neural']['updates'],0)
            self.assertIn('momentum',resumed['checkpoint']['neural']);self.assertTrue(verify_round(b,resumed))
            bad=copy.deepcopy(b);bad['checkpoint']['neural']['torch_version']='different'
            with self.assertRaises(ValueError):run_round(bad)


class StudyEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def create(self,model=None):return create_subagent(self.root,user_id='study',limits=SubagentLimits(max_model_calls=8,max_tool_calls=16,allow_extensions=False),model_factory=lambda:model)

    def test_review_then_protected_search_segment_feedback_and_bundle(self):
        s=study();s['segment_rounds']=1;p,u=self.create()
        with patch.object(engine,'run_worker',side_effect=AssertionError('Must review')):first=p.submit(task(s))
        self.assertEqual(first['budget']['used']['tool_calls'],0)
        paused=advance(p,u,first);self.assertEqual(paused['interaction']['kind'],'experiment_continue')
        event=u.study_feedback(paused['task_id'],paused['interaction']['interaction_id'],paused['revision'],
            {'knobs':{'exploration':0.3,'penalty_weight':2},'focus_runs':['run1'],'note':'Prefer exploration'})
        final=p.resume(paused['task_id'],event['event_id'])
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],2)
        e=final['summary']['experiment'];self.assertTrue(e['study_complete']);self.assertFalse(e['collection_complete'])
        self.assertEqual(e['feedback'][0]['knobs']['exploration'],0.3)
        self.assertGreater(e['interpretation']['run_statistics'][0]['worker_wall_seconds'],0)
        self.assertGreater(e['interpretation']['run_statistics'][0]['peak_job_memory_bytes'],0)
        bundle=next(a for a in final['artifacts'] if a['kind']=='result_bundle')
        with zipfile.ZipFile(bundle['path']) as z:
            self.assertIn('study-interpretation.json',z.namelist());self.assertIn('study-plan-and-decisions.json',z.namelist())

    def test_scripted_model_can_select_runs_but_cannot_enlarge_scope(self):
        s=study();s['planner']='model';s['rounds']=1
        model=ScriptedModel([{'action':'run','run_id':'run1','reason':'pilot'}]);p,u=self.create(model)
        final=advance(p,u,p.submit(task(s)))
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['model_calls'],1)
        self.assertNotIn('checkpoint',json.dumps(model.contexts))
        self.assertIn('resources',model.contexts[0])
        other=task(s);other['request_id']='invalid-model'
        bad=ScriptedModel([{'action':'run','run_id':'run999','reason':'unauthorized'}]);p,u=self.create(bad)
        result=advance(p,u,p.submit(other));self.assertEqual(result['status'],'waiting_for_user');self.assertEqual(result['budget']['used']['tool_calls'],0)

    def test_failed_attempt_budget_is_retained_on_retry(self):
        s=study();s['rounds']=1;p,u=self.create();first=p.submit(task(s))
        with patch.object(engine,'run_worker',side_effect=RuntimeError()):failed=advance(p,u,first)
        self.assertEqual(failed['status'],'interrupted');self.assertEqual(failed['budget']['experiment']['evaluation_reservations'],4)
        final=advance(p,u,failed);self.assertEqual(final['status'],'partial')
        self.assertEqual(final['budget']['experiment']['evaluation_reservations'],8)

    def test_pinned_search_receipt_survives_crash_before_observation_save(self):
        s=study();s['rounds']=1;p,u=self.create();first=p.submit(task(s));original=engine.receipt
        def interrupted(*args):
            original(*args);raise KeyboardInterrupt()
        with patch.object(engine,'receipt',side_effect=interrupted):stopped=advance(p,u,first)
        self.assertEqual(stopped['status'],'cancelled')
        with patch.object(engine,'run_worker',side_effect=AssertionError('No recomputation')):final=advance(p,u,stopped)
        self.assertEqual(final['status'],'completed');self.assertEqual(final['budget']['used']['tool_calls'],1)

    def test_resource_budget_blocks_extra_planning_call_after_failed_round(self):
        s=study();s['planner']='model';s['budget']['max_evaluations']=8
        model=ScriptedModel([{'action':'run','run_id':'run1','reason':'pilot'}]);p,u=self.create(model);first=p.submit(task(s))
        with patch.object(engine,'run_worker',side_effect=RuntimeError()):failed=advance(p,u,first)
        final=advance(p,u,failed)
        self.assertEqual(final['status'],'budget_exhausted');self.assertEqual(final['budget']['used']['model_calls'],1)

    def test_missing_torch_and_unauthorized_feedback_fail_before_execution(self):
        from importlib.util import find_spec
        p,u=self.create()
        with patch('importlib.util.find_spec',side_effect=lambda name:None if name=='torch' else find_spec(name)):
            with self.assertRaises(TaskProtocolError):p.submit(task(study('cem')))
        s=study();s['segment_rounds']=1;paused=advance(p,u,p.submit(task(s)))
        with self.assertRaises(TaskProtocolError):u.study_feedback(paused['task_id'],paused['interaction']['interaction_id'],paused['revision'],{'knobs':{'exploration':0.9}})
        with self.assertRaises(TaskProtocolError):u.study_feedback(paused['task_id'],paused['interaction']['interaction_id'],paused['revision'],{'budget':{'max_evaluations':999}})
        self.assertEqual(p.get(paused['task_id'])['budget']['used']['tool_calls'],1)

    @unittest.skipUnless(TORCH,'Optional CPU torch not installed')
    def test_actual_protected_cem_round_and_restart(self):
        s=study('cem');s['segment_rounds']=1;p,u=self.create()
        paused=advance(p,u,p.submit(task(s)))
        self.assertEqual(paused['status'],'waiting_for_user',paused.get('error'))
        p,u=self.create();final=advance(p,u,paused)
        self.assertEqual(final['status'],'completed',final.get('error'));self.assertTrue(final['summary']['experiment']['training_performed'])

    def test_mcp_rules_study_runs_without_model_settings(self):
        from graph_research.mcp.runtime import MCPResearchRuntime,HostConfiguration
        s=study();s['rounds']=1;runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'mcp-study',max_tool_calls=16))
        def wait(identifier):
            end=time.monotonic()+40
            while time.monotonic()<end:
                value=runtime.get(identifier,wait_seconds=1,until='terminal',detail='full')
                if not value.get('transport',{}).get('active'):return value
            self.fail('Study MCP worker timed out')
        try:
            first=wait(runtime.submit(task(s))['task_id']);self.assertEqual(first['status'],'waiting_for_user')
            _,portal=create_subagent(self.root,user_id='mcp-study',limits=runtime.configuration.limits())
            e=portal.continue_task(first['task_id'],first['interaction']['interaction_id'],first['revision']);runtime.resume(first['task_id'],e['event_id'])
            final=wait(first['task_id']);self.assertEqual(final['status'],'completed',final.get('error'))
            compact=runtime.get(first['task_id']);self.assertNotIn('interpretation',compact['summary']['experiment'])
        finally:
            for child in runtime.children.values():
                if child.poll() is None:child.terminate();child.wait(5)


if __name__=='__main__':unittest.main()
