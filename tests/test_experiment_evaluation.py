"""Phase 2: object semantics and independently rebuilt spectral enclosures."""
import copy
from fractions import Fraction
import unittest
from unittest.mock import patch

from graph_research.experiments.adapters import evaluate_candidate
from graph_research.experiments import prepare_experiment,experiment_contracts
from graph_research.experiments.verification import verify_evaluation,independent_matrix
from graph_research.experiments.generation import generate_hypertree
from graph_research.experiments.execution_contract import validate_execute
from graph_research.errors import TaskProtocolError


def problem(metric='alpha_spectral_radius',kind='simple_graph'):
    return {'version':1,'question':'Evaluate explicit candidate objects','intent':'parameterized_extremum',
        'object':{'type':kind,**({'uniformity':3} if kind=='uniform_hypertree' else {})},
        'parameters':{},'objective':{'metric':metric,'direction':'maximize',
            **({'arguments':{'alpha':'1/2'}} if metric=='alpha_spectral_radius' else {})}}


PATH={'n':4,'edges':[[0,1],[1,2],[2,3]]}
STAR={'n':7,'edges':[[0,1,2],[0,3,4],[0,5,6]]}
LOOSE_PATH={'n':7,'edges':[[0,1,2],[2,3,4],[4,5,6]]}
LOOSE_CYCLE={'n':6,'edges':[[0,1,2],[2,3,4],[0,4,5]]}


def execution(candidates=None):
    return {'operation':'execute','problem':problem(),
        'cases':[{'id':'sample','parameters':{},'candidates':copy.deepcopy(candidates or [PATH])}],
        'chunk_size':1,'pause_at_checkpoints':True,'budget':{'max_evaluations':8,'wall_seconds':120,'cpu_seconds':120,'memory_mb':512}}


class EvaluationTests(unittest.TestCase):
    def test_known_spectra_endpoints_disconnected_and_count(self):
        for alpha,expected in [(0,(1+5**.5)/2),('1/2',1+2**.5/2),(1,2)]:
            p=problem();p['objective']['arguments']['alpha']=alpha
            row=evaluate_candidate(p,{},PATH)
            self.assertAlmostEqual(row['objective_estimate'],expected)
            self.assertTrue(row['verification']['passed'])
            lo,hi=map(Fraction,row['objective_interval']);self.assertLessEqual(lo,hi)
        graph={'n':5,'edges':[[0,1],[2,3]]}
        row=evaluate_candidate(problem('adjacency_spectral_radius'),{},graph)
        self.assertAlmostEqual(row['objective_estimate'],1)
        self.assertTrue(row['verification']['passed'])
        row=evaluate_candidate(problem('edge_count'),{},PATH)
        self.assertEqual(row['objective_interval'],['3','3'])

    def test_clique_free_does_not_restrict_to_multipartite_and_boolean_logic(self):
        p=problem('edge_count');p['constraints']={'predicate':'clique_free','arguments':{'r':3}}
        cycle={'n':5,'edges':[[i,(i+1)%5] for i in range(5)]}
        self.assertTrue(evaluate_candidate(p,{},cycle)['feasible'])
        triangle={'n':3,'edges':[[0,1],[1,2],[0,2]]}
        self.assertFalse(evaluate_candidate(p,{},triangle)['feasible'])
        p['constraints']={'any':[{'predicate':'edge_count','arguments':{'value':99}},
            {'not':{'predicate':'edge_count','arguments':{'value':0}}}]}
        self.assertTrue(evaluate_candidate(p,{},triangle)['feasible'])

    def test_matching_and_distance_domain(self):
        p=problem('edge_count');p['constraints']={'predicate':'matching_number','arguments':{'value':2}}
        row=evaluate_candidate(p,{},PATH);self.assertTrue(row['feasible'])
        self.assertEqual(row['properties']['matching_number'],2)
        row=evaluate_candidate(problem('distance_spectral_radius'),{},{'n':3,'edges':[[0,1]]})
        self.assertFalse(row['metric_domain_satisfied']);self.assertIsNone(row['certificate'])

    def test_hypertree_distance_and_incidence_degree_not_support_degree(self):
        p=problem('distance_spectral_radius','uniform_hypertree')
        p['constraints']={'all':[{'predicate':'max_degree','arguments':{'value':3}},
            {'predicate':'max_degree_vertex_count','arguments':{'value':1}}]}
        row=evaluate_candidate(p,{},STAR)
        self.assertTrue(row['feasible']);self.assertEqual(row['properties']['degrees'],[3,1,1,1,1,1,1])
        matrix=independent_matrix(p,{},STAR)
        self.assertEqual(matrix[1][2],1);self.assertEqual(matrix[1][3],2)
        self.assertFalse(evaluate_candidate(p,{},LOOSE_PATH)['feasible'])
        for graph in [{'n':4,'edges':[[0,1,2],[2,3]]},{'n':4,'edges':[[0,1,2],[1,2,3]]}]:
            self.assertFalse(evaluate_candidate(p,{},graph)['object_valid'])

    def test_verifier_never_calls_primary_graph_library_or_eigensolver(self):
        p=problem();row=evaluate_candidate(p,{},PATH)
        with patch('numpy.linalg.eigvalsh',side_effect=AssertionError()),patch('numpy.linalg.eigh',side_effect=AssertionError()),patch('networkx.Graph',side_effect=AssertionError()):
            self.assertTrue(verify_evaluation(p,{},PATH,row)['passed'])

    def test_tampered_evidence_is_rejected(self):
        p=problem();row=evaluate_candidate(p,{},PATH)
        for change in ('score','interval','vector','hash','parameters','candidate','proof'):
            bad=copy.deepcopy(row)
            if change=='score':bad['objective_estimate']=99
            elif change=='interval':bad['objective_interval']=['0','1']
            elif change=='vector':bad['certificate']['vector'][0]=0
            elif change=='hash':bad['candidate_sha256']='0'*64
            elif change=='parameters':bad['parameters']={'unrequested':1}
            elif change=='proof':bad['mathematical_proof']=True
            else:bad['candidate']['n']=5
            with self.subTest(change=change):self.assertFalse(verify_evaluation(p,{},PATH,bad)['passed'])
        p['objective']['metric']='unknown';self.assertFalse(verify_evaluation(p,{},PATH,row)['passed'])

    def test_constructor_is_legal_seeded_and_cap_is_not_exact_degree(self):
        p=problem('distance_spectral_radius','uniform_hypertree')
        for seed in range(4):
            graph=generate_hypertree(3,8,seed=seed,degree_cap=2)
            self.assertEqual(graph,generate_hypertree(3,8,seed=seed,degree_cap=2))
            row=evaluate_candidate(p,{},graph)
            self.assertTrue(row['feasible']);self.assertEqual(graph['n'],17)
            self.assertLessEqual(row['properties']['max_degree'],2)
        with self.assertRaises(ValueError):generate_hypertree(3,2,degree_cap=1)

    def test_preflight_rejects_bad_graphs_semantics_and_unsupported_metrics(self):
        for graph in [{'n':2,'edges':[[0,0]]},{'n':2,'edges':[[0,2]]},{'n':2,'edges':[[0,1],[1,0]]}]:
            with self.assertRaises(TaskProtocolError):validate_execute(execution([graph]))
        spec=execution();spec['problem']['objective']['metric']='energy'
        with self.assertRaises(TaskProtocolError):validate_execute(spec)
        spec=execution([{'n':17,'edges':[]}]);spec['problem']['constraints']={'predicate':'matching_number','arguments':{'value':0}}
        with self.assertRaises(TaskProtocolError):validate_execute(spec)
        spec=execution();spec['approved']=True
        with self.assertRaises(TaskProtocolError):validate_execute(spec)

    def test_general_uniform_hypergraph_allows_cycles_and_legacy_tree_rejects_them(self):
        p=problem('distance_spectral_radius','uniform_hypergraph');p['object']['uniformity']=3
        row=evaluate_candidate(p,{},LOOSE_CYCLE)
        self.assertTrue(row['object_valid']);self.assertTrue(row['feasible'])
        self.assertTrue(row['properties']['connected']);self.assertFalse(row['properties']['hypertree'])
        self.assertTrue(row['verification']['passed'])
        exact=independent_matrix(p,{},LOOSE_CYCLE)
        # Six vertices: each row sums to 6 or 8, the independent spectrum is 3+sqrt(17).
        self.assertEqual(exact[1][3],2);self.assertEqual(exact[0][4],1)
        self.assertAlmostEqual(row['objective_estimate'],3+17**.5)
        p['object']['type']='uniform_hypertree'
        self.assertFalse(evaluate_candidate(p,{},LOOSE_CYCLE)['object_valid'])

    def test_optional_tree_constraint_and_its_negation_preserve_logic(self):
        p=problem('edge_count','uniform_hypergraph');p['object']['uniformity']=3
        p['constraints']={'predicate':'hypertree'}
        self.assertTrue(evaluate_candidate(p,{},STAR)['feasible'])
        self.assertFalse(evaluate_candidate(p,{},LOOSE_CYCLE)['feasible'])
        p['constraints']={'not':p['constraints']}
        self.assertFalse(evaluate_candidate(p,{},STAR)['feasible'])
        self.assertTrue(evaluate_candidate(p,{},LOOSE_CYCLE)['feasible'])

    def test_nonuniform_hypergraph_distance_is_not_a_tensor_or_tree_assumption(self):
        p=problem('distance_spectral_radius','hypergraph')
        graph={'n':5,'edges':[[0,1,2],[1,3],[2,3,4]]}
        row=evaluate_candidate(p,{},graph)
        self.assertTrue(row['feasible']);self.assertFalse(row['properties']['uniform']);self.assertFalse(row['properties']['hypertree'])
        self.assertEqual(row['properties']['degrees'],[1,2,2,2,1])
        with patch('networkx.Graph',side_effect=AssertionError()),patch('numpy.linalg.eigvalsh',side_effect=AssertionError()):
            self.assertTrue(verify_evaluation(p,{},graph,row)['passed'])
        p['object']={'type':'uniform_hypergraph','uniformity':3}
        self.assertFalse(evaluate_candidate(p,{},graph)['object_valid'])
        p=problem('alpha_spectral_radius','hypergraph')
        with self.assertRaises(ValueError):evaluate_candidate(p,{},graph)

    def test_disconnected_general_hypergraph_can_count_edges_but_not_distance_spectrum(self):
        graph={'n':6,'edges':[[0,1,2],[3,4,5]]}
        p=problem('edge_count','uniform_hypergraph');p['object']['uniformity']=3
        self.assertTrue(evaluate_candidate(p,{},graph)['feasible'])
        p['objective']['metric']='distance_spectral_radius'
        row=evaluate_candidate(p,{},graph)
        self.assertFalse(row['feasible']);self.assertFalse(row['metric_domain_satisfied'])

    def test_preparation_derives_tree_order_only_when_tree_unconditionally_required(self):
        p=problem('distance_spectral_radius','uniform_hypergraph');p['object'].update(uniformity=3,order=6)
        p['constraints']={'predicate':'edge_count','arguments':{'value':3}}
        report=prepare_experiment({'operation':'prepare','problem':p})
        self.assertEqual(report['plan']['cases'][0]['derived']['order'],6)
        self.assertEqual(report['plan']['status'],'draft')
        p['constraints']={'all':[p['constraints'],{'predicate':'hypertree'}]}
        self.assertFalse(prepare_experiment({'operation':'prepare','problem':p})['plan']['cases'])
        p['constraints']={'all':[p['constraints']['all'][0],{'not':{'predicate':'hypertree'}}]}
        report=prepare_experiment({'operation':'prepare','problem':p})
        self.assertTrue(report['plan']['cases']);self.assertEqual(report['plan']['status'],'draft')
        p['object'].pop('order')
        self.assertNotIn('order',prepare_experiment({'operation':'prepare','problem':p})['plan']['cases'][0]['derived'])
        p['constraints']['all'][1]={'predicate':'hypertree'}
        self.assertEqual(prepare_experiment({'operation':'prepare','problem':p})['plan']['cases'][0]['derived']['order'],7)

    def test_catalog_and_hypergraph_limits_are_consistent(self):
        catalog=experiment_contracts()['capabilities']
        for kind in ('hypergraph','uniform_hypergraph','uniform_hypertree'):
            self.assertIn(kind,catalog['objects'])
            self.assertIn(kind,next(p for p in catalog['predicates'] if p['id']=='hypertree')['objects'])
        p=problem('edge_count','hypergraph')
        for constraint in ('clique_free','matching_number'):
            p['constraints']={'predicate':constraint,'arguments':{'r' if constraint=='clique_free' else 'value':3}}
            with self.assertRaises(ValueError):evaluate_candidate(p,{},STAR)
        spec=execution();spec['problem']=problem('edge_count','hypergraph')
        spec['cases'][0]['candidates']=[{'n':20,'edges':[[a,b] for a in range(20) for b in range(a+1,20)][:129]}]
        with self.assertRaises(TaskProtocolError):validate_execute(spec)


if __name__=='__main__':unittest.main()
