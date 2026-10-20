"""Algorithm, conditioning, scientific evidence and host integration regressions."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from graph_research.hypergraphs import Hypergraph,HyperCycle
from graph_research.hypergraphs.newton_noda import _LogAction,_positive_solve,PerronConvergenceError
from graph_research.hypergraphs.spectral_certificate import verify_spectrum_certificate
from graph_research.tools import ToolRegistry
from graph_research.assistant import create_subagent,SubagentLimits


FIXTURES=Path(__file__).parent/'data'


class NewtonNodaTests(unittest.TestCase):
    def test_scaled_jacobian_matches_independent_edge_polynomial_derivative(self):
        graph=Hypergraph([[0,1,2],[1,2,3]],weights=[.7,1.4],vertex_degrees=[2,3,4,5]);alpha=.71
        x=np.array([.12,.19,.3,.39]);action=_LogAction(graph,alpha);logs,terms=action.evaluate(x)
        scale=float(logs.max());q=np.exp(logs-scale);c=action.off_diagonal(terms,scale)
        b=np.diag(c.sum(axis=1)+2*(1-q))-c
        upper=math.exp(scale)
        def residual(v):
            adj=np.zeros(4)
            for edge,w in zip(graph.Edges,graph.weights):
                for i in edge:adj[i]+=w*math.prod(v[j] for j in edge if j!=i)
            return (upper-alpha*graph.vertex_degrees)*v**2-(1-alpha)*adj
        step=1e-6
        jacobian=np.column_stack([(residual(x+step*np.eye(4)[i])-residual(x-step*np.eye(4)[i]))/(2*step) for i in range(4)])
        np.testing.assert_allclose(b,jacobian*x[None,:]/x[:,None]**2/upper,rtol=1e-8,atol=1e-9)
        z=_positive_solve(c,2*(1-q),np.ones(4))
        np.testing.assert_allclose(b@z,np.ones(4),rtol=1e-10,atol=1e-10)

    def test_m_matrix_elimination_preserves_tiny_positive_row_sums(self):
        c=np.array([[0.,1.],[1.,0.]])
        z=_positive_solve(c,np.array([0.,1e-25]),np.ones(2))
        np.testing.assert_allclose(z,[2e25,2e25],rtol=1e-14)
        for s in (np.array([-1.,0.]),np.array([0.,0.])):
            with self.assertRaises(ArithmeticError):_positive_solve(c,s,np.ones(2))

    def test_log_action_does_not_form_underflowing_edge_products(self):
        graph=Hypergraph([list(range(5))]);action=_LogAction(graph,0)
        logs,terms=action.evaluate(np.full(5,1e-100))
        self.assertEqual(float(np.prod(np.full(5,1e-100))),0.)
        np.testing.assert_allclose(logs,0,atol=5e-13);self.assertTrue(np.isfinite(terms).all())

    def test_graph_case_matches_symmetric_matrix_eigenvalue(self):
        edges=[[i,i+1] for i in range(6)];h=Hypergraph(edges)
        a=np.zeros((7,7))
        for i,j in edges:a[i,j]=a[j,i]=1
        for alpha in (0,.3,.99,.999999):
            result=h.alpha_spectrum(alpha,method='newton_noda')
            expected=float(np.linalg.eigvalsh(alpha*np.diag(a.sum(axis=1))+(1-alpha)*a)[-1])
            self.assertAlmostEqual(result['rho'],expected,places=10)
            self.assertTrue(result['verification']['passed']);self.assertEqual(result['method'],'newton_noda')

    def test_uniform_cycle_formula_and_regular_tensor(self):
        graph=HyperCycle(6,4)
        for alpha in (0,.5,.99,.999999):
            result=graph.alpha_spectrum(alpha,method='newton_noda')
            expected=(3*alpha+math.sqrt(alpha*alpha+8*(1-alpha)**2))/2
            self.assertAlmostEqual(result['rho'],expected,places=10)
        regular=Hypergraph([[0,1,2],[0,1,3],[0,2,3],[1,2,3]])
        self.assertAlmostEqual(regular.alpha_spectrum(.999,method='newton_noda')['rho'],3,places=10)

    def test_weights_independent_diagonal_and_incidence_output(self):
        edges=[[0,1,2],[2,3,4]]
        for kwargs in ({'weights':[.1,.23]},{'weights':[1,2],'vertex_degrees':[2,3,4,5,6]}):
            graph=Hypergraph(edges,**kwargs)
            for alpha in (.1,.99,.999999):
                result=graph.alpha_spectrum(alpha,method='newton_noda')
                self.assertTrue(verify_spectrum_certificate(edges,result,**kwargs)['passed'])
        result=ToolRegistry().call('hypergraph_spectrum',{'edges':edges,'alpha':.999,'method':'newton_noda','weighted_incidence':True})
        np.testing.assert_allclose(np.array(result['weighted_incidence']).sum(axis=1),1,atol=1e-10)

    def test_weighted_incidence_avoids_underflow_and_is_scale_invariant(self):
        graph=Hypergraph([list(range(5))],weights=[2.])
        for alpha in (0.,.5,.999999):
            for scale in (1.,1e-200,1e200):
                candidate={'alpha':alpha,'rho':2.,'vertex_order':graph.vertices(),'perron_vector':[scale]*5}
                matrix=graph.weighted_incidence_from_result(candidate)
                self.assertTrue(np.isfinite(matrix).all());np.testing.assert_allclose(matrix,np.ones((5,1)),atol=1e-13)

    def test_weighted_incidence_rejects_malformed_or_unrepresentable_candidate(self):
        graph=Hypergraph([[0,1,2]])
        base={'alpha':0.,'rho':1.,'vertex_order':[0,1,2],'perron_vector':[1.,1.,1.]}
        for change in ({'rho':0},{'rho':float('inf')},{'alpha':float('nan')},
                       {'vertex_order':[1,0,2]},{'perron_vector':[0,1,1]},{'perron_vector':[1,1]}):
            with self.assertRaises(ValueError):graph.weighted_incidence_from_result({**base,**change})
        with self.assertRaises(ArithmeticError):graph.weighted_incidence_from_result({**base,'perron_vector':[1e-300,1,1]})
        mismatched=Hypergraph([[0,1,2]],vertex_degrees=[1,1,1+1e-7])
        with self.assertRaises(ValueError):mismatched.weighted_incidence_from_result(base)

    def test_total_budget_covers_failed_continuation_and_precision_work(self):
        case=next(c for c in json.loads((FIXTURES/'high_alpha_pilot.json').read_text(encoding='utf-8'))['cases'] if c['case_id']=='G11q6_13_k3')
        graph=Hypergraph(case['edges'])
        with self.assertRaises(PerronConvergenceError) as caught:graph.alpha_spectrum(.999,max_iterations=140,method='newton_noda')
        self.assertLessEqual(caught.exception.diagnostics['iterations'],140)
        self.assertFalse(caught.exception.diagnostics['certified'])
        result=graph.alpha_spectrum(.999999,method='newton_noda')
        detail=result['solver_diagnostics'];self.assertTrue(detail['failed_stages']);self.assertTrue(detail['precision_switches'])
        total=sum(s['iterations'] for s in detail['continuation_stages']+detail['failed_stages'])
        self.assertEqual(result['iterations'],total)
        self.assertEqual(detail['continuation_stages'][-1]['alpha'],.999999)
        self.assertTrue(all(s['verification']=='exact_rational_collatz' for s in detail['continuation_stages']))

    def test_warm_solution_scaling_seed_reproducibility_and_invalid_input(self):
        graph=Hypergraph([[0,1,2],[2,3,4],[4,5,6]])
        cold=graph.alpha_spectrum(.999,method='newton_noda')
        again=graph.alpha_spectrum(.999,method='newton_noda')
        self.assertEqual(cold['perron_vector'],again['perron_vector'])
        warm=graph.alpha_spectrum(.999,initial_vector=cold['perron_vector'],method='newton_noda')
        self.assertEqual(warm['iterations'],1)
        scaled=graph.alpha_spectrum(.3,initial_vector=[1e250]*graph.order(),method='newton_noda')
        self.assertTrue(scaled['verification']['passed'])
        for vector in ([1],[-1]*graph.order(),[float('inf')]*graph.order()):
            with self.assertRaises(ValueError):graph.alpha_spectrum(.999,initial_vector=vector,method='newton_noda')
        self.assertEqual(graph.alpha_spectrum(1,method='newton_noda')['method'],'degree_diagonal')

    def test_external_28_unresolved_inputs_are_now_certified(self):
        cases=json.loads((FIXTURES/'high_alpha_unresolved.json').read_text(encoding='utf-8'))['cases'];count=0
        for case in cases:
            for alpha in case['alphas']:
                with self.subTest(case=case['case_id'],alpha=alpha):
                    result=Hypergraph(case['edges']).alpha_spectrum(float(alpha),method='newton_noda')
                    self.assertTrue(result['verification']['passed'])
                    self.assertLessEqual(result['iterations'],20000);count+=1
        self.assertEqual(count,28)

    def test_default_auto_uses_nni_for_general_high_alpha_and_keeps_explicit_iteration(self):
        graph=Hypergraph([[0,1,2],[2,3,4],[4,5,6]])
        self.assertEqual(graph.alpha_spectrum(.999)['method'],'newton_noda')
        self.assertEqual(graph.alpha_spectrum(.1,method='iteration')['method'],'shifted_power_iteration')
        definition=ToolRegistry().describe('hypergraph_spectrum')
        self.assertIn('newton_noda',definition['parameters']['properties']['method']['enum'])

    def test_host_scan_accepts_method_and_charges_only_declared_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            parent,_=create_subagent(directory,user_id='nni',limits=SubagentLimits(max_tool_calls=2,max_model_calls=0))
            request={'version':1,'request_id':'nni-scan','objective':'NNI budget validation',
                     'execution':{'mode':'scan','scan':{'edges':[[0,1,2],[2,3,4],[4,5,6]],'alphas':[.999,1],'method':'newton_noda'}},
                     'constraints':{'max_tool_calls':2,'max_model_calls':0,'allow_extensions':False}}
            result=parent.submit(request)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['budget']['used']['tool_calls'],2)
            self.assertEqual(result['budget']['used']['model_calls'],0)
            rows=result['summary']['scan']['points'];self.assertEqual(rows[0]['method'],'newton_noda');self.assertEqual(rows[1]['method'],'degree_diagonal')


if __name__=='__main__':unittest.main()
