"""Independent numerical, structural and certificate checks for research tasks."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np
import sympy as sp

from graph_research.tools import ToolRegistry
from graph_research.graphs.weighted import weighted_graph_spectrum,weighted_matrices
from graph_research.graphs.classification import graph_class_certificate,verify_generalized_line_certificate
from graph_research.workflows.recipes import build_recipe,graph_recipe
from graph_research.workflows.internal_paths import hypergraph_path_analysis
from graph_research.workflows.batch import graph_batch_study
from graph_research.workflows.energy import graph_energy_study,energy_interval,verify_energy_interval
from graph_research.workflows.environment import research_environment
from graph_research.algebra.analysis import symbolic_analysis,mathematical_expression
from graph_research.algebra.blocks import block_matrix_analysis


class WeightedTests(unittest.TestCase):
    def test_hermitian_complex_weights_isolates_and_exact_polynomial(self):
        result=weighted_graph_spectrum(3,[{'u':0,'v':1,'weight':{'real':3,'imag':4}}],exact=True)
        np.testing.assert_allclose(result['spectrum'],[5,-5,0]);self.assertEqual(result['energy'],10)
        x=sp.Symbol('x');self.assertEqual(sp.sympify(result['polynomial']),x**3-25*x)
        np.testing.assert_allclose(result['matrix'],[[0,3+4j,0],[3-4j,0,0],[0,0,0]])
        self.assertLess(result['max_relative_residual'],1e-14)

    def test_directed_complex_and_negative_dominant_residual(self):
        # Eigenvalues ±2i, not the positive real spectral radius 2.
        result=weighted_graph_spectrum(2,[{'u':0,'v':1,'weight':2},{'u':1,'v':0,'weight':-2}],directed=True)
        self.assertFalse(result['hermitian']);self.assertNotIn('energy',result)
        self.assertAlmostEqual(result['rho'],2);self.assertLess(result['max_relative_residual'],1e-14)
        self.assertAlmostEqual(result['dominant_eigenvalue'].real,0)

    def test_laplacian_degree_conventions(self):
        edges=[{'u':0,'v':1,'weight':-2}]
        absolute,_,_,_=weighted_matrices(2,edges,matrix='L')
        signed,_,_,_=weighted_matrices(2,edges,matrix='L',degree_mode='sum')
        np.testing.assert_array_equal(absolute,[[2,2],[2,2]])
        np.testing.assert_array_equal(signed,[[-2,2],[2,-2]])
        laplacian=weighted_graph_spectrum(2,edges,matrix='L')
        self.assertNotIn('energy',laplacian);self.assertEqual(laplacian['spectral_modulus_sum'],4)
        for edges in ([{'u':0,'v':1,'weight':1},{'u':1,'v':0,'weight':1}],[{'u':0,'v':0,'weight':1}]):
            with self.assertRaises(ValueError):weighted_matrices(2,edges)
        with self.assertRaises(ValueError):weighted_matrices(2,[{'u':0,'v':1,'weight':{'real':0,'imag':1}}],degree_mode='sum')
        with self.assertRaises(ValueError):weighted_graph_spectrum(9,[],exact=True)


class RecipesAndPathsTests(unittest.TestCase):
    def test_graph_recipe_matches_independent_construction_and_does_not_mutate_input(self):
        source={'graph_type':'graph','base':{'kind':'path','n':'t+2'},'parameters':{'t':2},'steps':[{'operation':'attach_star','roots':[0],'count':'t'}]}
        before=copy.deepcopy(source);g,trace=build_recipe(**source)
        expected=nx.path_graph(4);expected.add_edges_from([(0,4),(0,5)])
        self.assertTrue(nx.is_isomorphic(g,expected));self.assertEqual(source,before)
        self.assertEqual(trace[0]['resolved']['roots'],[0])

    def test_nonuniform_base_and_structure_assertions(self):
        result=graph_recipe('hypergraph',{'edges':[['a','b'],['b','c','d']],'vertices':['a','b','c','d','isolated'],'weights':[2,3]},assertions={'uniform':False,'linear':True,'order':5,'cycle_rank':0,'connected':False})
        self.assertEqual(result['hypergraph_spec']['weights'],[2,3]);self.assertIn('isolated',result['hypergraph_spec']['vertices'])
        with self.assertRaisesRegex(ValueError,'断言失败'):graph_recipe('graph',{'kind':'path','n':3},assertions={'cycle_rank':1})

    def test_structural_selectors_and_subdivision_count_zero(self):
        from graph_research.hypergraphs import HyperPath
        for count in (0,1,2):
            g,trace=build_recipe('hypergraph',{'family':'path','m':2,'k':3},[{'operation':'subdivide_edge','edge_index':0,'count':count}],assertions={'size':2+count,'uniform':True,'cycle_rank':0})
            self.assertEqual(g.size(),2+count)
        g,_=build_recipe('hypergraph',{'family':'path','m':2,'k':3},[{'operation':'attach_path','roots':[{'kind':'leaf','edge':0}],'length':2}],assertions={'order':9,'size':4,'linear':True,'uniform':True})
        self.assertEqual(g.size(),HyperPath(4,3).size())

    def test_connect_copies_and_unsafe_recipe_rejected(self):
        g,_=build_recipe('graph',{'kind':'path','n':3},[{'operation':'connect','left':[0],'right':[2],'length':2},{'operation':'disjoint_copies','copies':2}],assertions={'order':8,'size':8,'cycle_rank':2,'connected':False})
        self.assertEqual(nx.number_connected_components(g),2)
        for steps in ([{'operation':'exec','code':'1'}],[{'operation':'attach_star','roots':[True]}],[{'operation':'attach_path','length':'__import__("os")'}]):
            with self.assertRaises(ValueError):build_recipe('graph',{'kind':'path','n':3},steps)

    def test_internal_path_orientation_submatrix_and_full_normalization(self):
        from graph_research.hypergraphs import Hypergraph
        edges=[[0,1,2],[2,3,4],[4,5,6]]
        result=hypergraph_path_analysis(edges,6,0,weighted_incidence=True)
        self.assertEqual(result['spine_vertices'],[6,4,2,0]);self.assertEqual(result['edge_indices'],[2,1,0])
        np.testing.assert_array_equal(result['incidence_submatrix'],[[1,0,0],[1,1,0],[0,1,1],[0,0,1]])
        h=Hypergraph(edges);s=h.alpha_spectrum();b=h.weighted_incidence_from_result(s)
        np.testing.assert_allclose(result['weighted_incidence_submatrix'],b[[6,4,2,0]][:,[2,1,0]],atol=1e-9)

    def test_path_branches_ambiguity_and_nonuniform(self):
        result=hypergraph_path_analysis([[0,1,2],[2,3],[1,5]],0,3,edge_indices=[0,1])
        self.assertFalse(result['internal_loose_path']);self.assertEqual(result['violations'][0]['vertex'],1)
        cycle=[[0,1],[1,2],[2,0]]
        with self.assertRaisesRegex(ValueError,'歧义'):hypergraph_path_analysis(cycle,0,2)
        self.assertTrue(hypergraph_path_analysis(cycle,0,2,edge_indices=[2])['internal_loose_path'])
        with self.assertRaises(ValueError):hypergraph_path_analysis([[0,1,2],[1,2,3]],0,3,edge_indices=[0,1])


class AlgebraWorkflowTests(unittest.TestCase):
    def test_finite_symbolic_and_infinite_sums_keep_status(self):
        result=symbolic_analysis('summation','x^2',upper=10)
        self.assertEqual(result['result'],'385');self.assertEqual(result['status'],'evaluated')
        result=symbolic_analysis('summation','x^2',upper='n',parameters=['n'])
        self.assertEqual(result['status'],'conditional');self.assertEqual(result['conditions'],['n >= 0'])
        n=sp.Symbol('n');self.assertEqual(sp.expand(sp.sympify(result['result'])-n*(n+1)*(2*n+1)/6),0)
        self.assertEqual(symbolic_analysis('summation','1/2^x',upper='oo')['result'],'2')
        self.assertEqual(symbolic_analysis('summation','1',upper='oo')['status'],'divergent')
        self.assertEqual(symbolic_analysis('summation','factorial(x)',upper='n',parameters=['n'])['status'],'unevaluated')

    def test_series_taylor_laurent_and_whitelist(self):
        x=sp.Symbol('x')
        result=symbolic_analysis('series','exp(x)',order=5)
        self.assertEqual(sp.sympify(result['truncated']),1+x+x**2/2+x**3/6+x**4/24)
        from graph_research.rendering.results import terminal_result,display_field
        presented=terminal_result({'tool':'symbolic_analysis','ok':True,'result':result})
        self.assertIn('展开阶数',presented);self.assertNotIn('顶点数',presented)
        self.assertEqual(display_field('status','conditional'),'需满足所列条件')
        self.assertEqual(symbolic_analysis('series','1/x+sin(x)',order=3)['truncated'],'x + 1/x')
        for expression in ('__import__("os")','x.__class__','[x][0]','open("a")','factorial(129)','1/0'):
            with self.assertRaises(ValueError):mathematical_expression(expression,{'x':x})
        with self.assertRaises(ValueError):symbolic_analysis('summation','x',lower=2,upper=1)

    def test_block_extraction_permutation_and_product(self):
        a=sp.Matrix([[1,2,3],[4,5,6],[7,8,9]])
        result=block_matrix_analysis('extract',a.tolist(),[1,2],[2,1])
        self.assertEqual(result['blocks'][1][0],sp.Matrix([[4,5],[7,8]]))
        result=block_matrix_analysis('permute',a.tolist(),[1,2],[2,1],row_order=[1,0],column_order=[1,0])
        self.assertEqual(result['matrix'],a.extract([1,2,0],[2,0,1]))
        result=block_matrix_analysis('multiply',a.tolist(),[1,2],[2,1],right=sp.eye(3).tolist())
        self.assertEqual(result['matrix'],a);self.assertTrue(result['verified'])
        with self.assertRaises(ValueError):block_matrix_analysis('extract',a.tolist(),[1,1],[3])

    def test_symbolic_companion_blocks_independent_determinant(self):
        t=sp.Symbol('t',integer=True);x=sp.Symbol('x')
        result=block_matrix_analysis('companion_blocks',polynomials=[[2,0,-4],[1,'-t']],parameters=['t'])
        self.assertEqual(result['blocks'][0],sp.Matrix([[0,2],[1,0]]))
        self.assertEqual(sp.expand(result['matrix'].charpoly(x).as_expr()-(x*x-2)*(x-t)),0)
        self.assertTrue(result['verified'])
        with self.assertRaises(ValueError):block_matrix_analysis('companion_blocks',polynomials=[['t',1]],parameters=['t'])


class CertificateTests(unittest.TestCase):
    def test_generalized_line_claw_positive_star_five_negative_and_budget(self):
        for n,expected in [(4,True),(5,True),(6,False)]:
            result=graph_class_certificate('star',n)
            self.assertIs(result['generalized_line_graph'],expected);self.assertTrue(result['verified'])
            self.assertTrue(verify_generalized_line_certificate(nx.star_graph(n-1),result['certificate']))
        result=graph_class_certificate('cycle',6,search_budget=1)
        self.assertEqual(result['status'],'indeterminate');self.assertIsNone(result['generalized_line_graph']);self.assertNotIn('certificate',result)

    def test_independent_cocktail_party_construction_and_corrupt_certificates(self):
        # Root triangle, CP(1) at a vertex: 3 root-edge vertices plus a private missing pair.
        g=nx.line_graph(nx.cycle_graph(3));root_edges=list(g);g=nx.convert_node_labels_to_integers(g)
        incident=[i for i,edge in enumerate(root_edges) if 0 in edge]
        g.add_nodes_from([3,4]);g.add_edges_from((i,j) for i in incident for j in (3,4))
        result=graph_class_certificate('edges',len(g),list(g.edges));self.assertTrue(result['generalized_line_graph'])
        certificate=copy.deepcopy(result['certificate']);certificate['blocks'][0]['vertices'].append(99)
        self.assertFalse(verify_generalized_line_certificate(g,certificate))
        certificate=copy.deepcopy(result['certificate']);certificate['graph_sha256']='bad'
        self.assertFalse(verify_generalized_line_certificate(g,certificate))
        for n in (2,3,4):
            cp=nx.complete_multipartite_graph(*([2]*n))
            self.assertTrue(graph_class_certificate('edges',len(cp),list(cp.edges))['generalized_line_graph'])

    def test_negative_certificate_survives_node_and_edge_insertion_order(self):
        g=nx.from_graph6_bytes(b'DNw');certificate=graph_class_certificate('edges',len(g),list(g.edges))['certificate']
        reordered=nx.Graph();reordered.add_nodes_from(reversed(list(g)));reordered.add_edges_from(reversed(list(g.edges)))
        self.assertTrue(verify_generalized_line_certificate(reordered,certificate))
        for corrupted in (None,{'type':'constructive_cover','graph_sha256':certificate['graph_sha256'],'blocks':[None]},
                          {**certificate,'search_budget':10**9}):
            self.assertFalse(verify_generalized_line_certificate(g,corrupted))

    def test_legacy_31_obstructions_and_all_vertex_deletions(self):
        # Reference graph data only; recognition does not execute Sage or trust this list.
        codes=['DIk','DFw','DNw','E?Fg','E?Bw','E?Fw',r'EC\w','E?^w','E?~w','E@~w','EF~w','E@QW','EHQW','E@`w','E@]o','E@Rw','EAMw','E`]o','E@^W','E@Vw','EK]w','EBjw',r'EK\w','E@^w','ELrw','EBnw','EJ]w','EK~w','EJnw','EL~w','EN~w']
        for code in codes:
            g=nx.from_graph6_bytes(code.encode())
            with self.subTest(code=code):
                self.assertFalse(graph_class_certificate('edges',len(g),list(g.edges))['generalized_line_graph'])
                for vertex in g:
                    sub=nx.convert_node_labels_to_integers(g.subgraph(set(g)-{vertex}))
                    self.assertTrue(graph_class_certificate('edges',len(sub),list(sub.edges))['generalized_line_graph'])

    def test_energy_intervals_multiplicity_and_rejection_of_tampering(self):
        x=sp.Symbol('x');p=sp.Poly((x*x-2)**2*x,x);certificate=energy_interval(p)
        self.assertTrue(verify_energy_interval(p,certificate))
        lower,upper=map(sp.Rational,certificate['bounds'])
        self.assertLess(float(upper-lower),1e-10);self.assertLessEqual(float(lower),4*2**.5);self.assertGreaterEqual(float(upper),4*2**.5)
        bad=copy.deepcopy(certificate);bad['root_intervals'][0]['multiplicity']+=1
        self.assertFalse(verify_energy_interval(p,bad))
        bad=copy.deepcopy(certificate);bad['bounds'][0]='1234'
        self.assertFalse(verify_energy_interval(p,bad))

    def test_finite_parameter_energy_and_cospectral_equality(self):
        result=graph_energy_study({'recipe':{'base':{'kind':'path','n':'t+2'}}},{'recipe':{'base':{'kind':'complete','n':'t+2'}}},values=[0,1,2])
        self.assertEqual([row['comparison'] for row in result['rows']],['equal_cospectral','less','less'])
        self.assertEqual(result['domain'],[0,1,2]);self.assertEqual(result['status'],'certified_finite_domain')
        greater=graph_energy_study({'weighted':{'n':2,'edges':[{'u':0,'v':1,'weight':2}]}},{'kind':'path','n':2})
        self.assertEqual(greater['rows'][0]['comparison'],'greater')
        with self.assertRaises(ValueError):graph_energy_study({'weighted':{'n':2,'directed':True,'edges':[{'u':0,'v':1,'weight':1}]}},{'kind':'path','n':2})
        with self.assertRaisesRegex(ValueError,'仅用邻接矩阵'):graph_energy_study({'weighted':{'n':2,'matrix':'L','edges':[{'u':0,'v':1,'weight':1}]}},{'kind':'path','n':2})


class BatchAndIntegrationTests(unittest.TestCase):
    def test_batch_receipts_files_partial_failure_and_csv_injection(self):
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            result=graph_batch_study([{'name':'=danger','input':{'kind':'path','n':3}},{'name':'bad','input':{'kind':'path','n':0}}],['structure','spectrum','charpoly'])
            self.assertEqual(result['status'],'partial');self.assertEqual(result['rows'][1]['status'],'failed')
            saved=json.loads(Path(result['files']['json']).read_text(encoding='utf-8'));self.assertEqual(saved['rows'],result['rows'])
            with Path(result['files']['csv']).open(encoding='utf-8',newline='') as file:rows=list(csv.reader(file))
            self.assertEqual(rows[1][1],"'=danger");self.assertAlmostEqual(float(rows[1][6]),2*2**.5,places=12)
            for path in result['files'].values():self.assertTrue(Path(path).is_relative_to(Path(directory)/'outputs'))

    def test_batch_plots_nonuniform_isolates_and_weighted_data(self):
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            result=graph_batch_study([{'name':'P3','input':{'kind':'path','n':3}},
                {'name':'hyper','graph_type':'hypergraph','input':{'edges':[[0,1],[1,2,3]],'vertices':[0,1,2,3,4]}},
                {'name':'weighted','graph_type':'weighted','input':{'n':2,'edges':[{'u':0,'v':1,'weight':2}]}}],['structure'],plot=True)
            self.assertEqual(result['status'],'complete');self.assertEqual(result['rows'][1]['results']['structure']['order'],5)
            self.assertTrue({'png','svg','pdf'}<=set(result['files']))
            self.assertTrue(Path(result['files']['png']).read_bytes().startswith(b'\x89PNG'))

    def test_missing_plot_dependency_keeps_numeric_results_and_export_error(self):
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)),patch('graph_research.workflows.batch._plot_batch',side_effect=ImportError('matplotlib missing')):
            result=graph_batch_study([{'name':'P3','input':{'kind':'path','n':3}}],plot=True)
            self.assertEqual(result['status'],'partial');self.assertIn('spectrum',result['rows'][0]['results'])
            saved=json.loads(Path(result['files']['json']).read_text(encoding='utf-8'))
            self.assertEqual(saved,result);self.assertIn('plot',saved['export_errors'])

    def test_environment_detection_is_readonly_and_not_compilation_claim(self):
        with patch('subprocess.run',side_effect=AssertionError('must not launch')),patch('shutil.which',return_value=None):
            result=research_environment()
        self.assertEqual(result['three_dimensional_workflow'],'assessment_only')
        self.assertTrue(all(not row['detected'] for row in result['tex_compilers']))

    def test_new_tools_share_manual_and_model_catalog(self):
        registry=ToolRegistry()
        names={'weighted_graph_spectrum','graph_recipe','hypergraph_path_analysis','graph_batch_study','symbolic_analysis','block_matrix_analysis','graph_class_certificate','graph_energy_study','research_environment'}
        self.assertTrue(names<=set(registry.tools))
        for name in names:self.assertEqual(registry.describe(name)['documentation']['coverage'],'reviewed_native')

    def test_real_protected_calls_and_portable_result_bundle(self):
        from graph_research.assistant import OfflineToolSession,verify_bundle
        from graph_research.runtime.integrity import verify
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session=OfflineToolSession(root/'manual',root/'extensions')
            registry=ToolRegistry()
            for name in ('weighted_graph_spectrum','graph_recipe','graph_batch_study','symbolic_analysis','block_matrix_analysis','graph_class_certificate','graph_energy_study','research_environment'):
                session.call_tool(name,registry.describe(name)['documentation']['examples'][0]['arguments'])
                observation=session.state['observations'][-1]
                self.assertIn('result',observation);self.assertNotIn('error',observation)
            self.assertEqual(session.result_bundle['summary']['verified_calls'],8)
            self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])
            self.assertTrue(verify()['ok'])


if __name__=='__main__':unittest.main()
