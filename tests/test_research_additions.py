"""Independent oracles for migrated graph operations, recurrences and integer lattices."""
import copy
import itertools
import json
import random
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np
import sympy as sp

from graph_research import graphs
from graph_research.algebra.expressions import arithmetic_expression
from graph_research.algebra.integer_systems import solve_integer_linear_system
from graph_research.algebra.recurrences import solve_linear_recurrence
from graph_research.hypergraphs import HyperPath,HyperCycle,Gee,Gev,Gvv,GWG,Ca,Cva,IsIsomorphic
from graph_research.tools import ToolRegistry
from graph_research.assistant import OfflineToolSession,ResearchSession,verify_bundle
from tests.test_feature_workflow import ScriptedModel


class BasicGraphMigrationTests(unittest.TestCase):
    def test_core_handles_pendants_isolates_forests_and_preserves_input(self):
        graph=nx.cycle_graph(4);graph.add_edges_from([(0,4),(4,5)]);graph.add_node('isolated');before=copy.deepcopy(graph)
        self.assertEqual(set(graphs.BaseGraph(graph)),set(range(4)))
        self.assertTrue(nx.utils.graphs_equal(graph,before))
        self.assertEqual(len(graphs.BaseGraph(nx.path_graph(5))),0)
        self.assertEqual(len(graphs.BaseGraph(nx.Graph())),0)

    def test_relabel_and_vector_sort_do_not_merge_or_mutate(self):
        graph=nx.Graph();graph.add_nodes_from(['a','b','c']);graph.add_edge('a','c');mapping={'a':2,'b':1,'c':0};before=copy.deepcopy(mapping)
        result=graphs.Relabel(graph,mapping);self.assertEqual(mapping,before);self.assertTrue(result.has_edge(2,0))
        sorted_graph=graphs.sorted_label(graph,[1,1,0]);self.assertTrue(sorted_graph.has_edge(1,0))
        self.assertEqual(list(graph),['a','b','c'])
        with self.assertRaises(ValueError):graphs.Relabel(graph,{'a':'b'})
        with self.assertRaises(ValueError):graphs.sorted_label(graph,[0,float('nan'),1])

    def test_subdivision_preserves_isolates_and_old_incidence_line_graph_formula(self):
        graph=nx.path_graph(3);graph.add_node(3)
        result=graphs.subdivide_edges(graph,[(0,1)],2)
        self.assertEqual(len(result),6);self.assertEqual(result.number_of_edges(),4);self.assertEqual(result.degree(3),0)
        self.assertEqual(graph.number_of_edges(),2)
        with self.assertRaises(ValueError):graphs.subdivide_edges(graph,[(0,1),(1,0)])
        for graph in (nx.path_graph(5),nx.cycle_graph(4),nx.star_graph(4)):
            edges=list(graph.edges);incidence=np.array([[int(v in edge) for edge in edges] for v in graph])
            actual=nx.to_numpy_array(graphs.generalized_line_graph(graph),nodelist=edges)
            np.testing.assert_array_equal(actual,(incidence.T@incidence)%2)

    def test_json_graph_spec_can_chain_after_string_relabel_and_empty_core_is_explicit(self):
        registry=ToolRegistry()
        result=registry.call('graph_edit',{'operation':'relabel','kind':'path','n':4,'labels':['d','a','b','c']})
        self.assertEqual(result['vertices'],['d','a','b','c'])
        self.assertAlmostEqual(registry.call('graph_spectrum',result['graph_spec'])['rho'],2*np.cos(np.pi/5))
        result=registry.call('graph_edit',{'operation':'core','kind':'path','n':4})
        self.assertEqual(result['graph_spec'],{'kind':'edges','n':0,'edges':[]})


class RecurrenceMigrationTests(unittest.TestCase):
    def test_fibonacci_polynomial_forcing_and_factorial_have_independent_exact_terms(self):
        examples=[([-1,-1,1],[0,1],0,['0','1','1','2','3','5','8','13']),
                  ([-1,1],[0],'2*n+1',['0','1','4','9','16','25','36','49']),
                  (['-(n+1)',1],[1],0,['1','1','2','6','24','120','720','5040'])]
        for coefficients,initial,forcing,expected in examples:
            with self.subTest(coefficients=coefficients):
                result=solve_linear_recurrence(coefficients,initial,forcing,terms=8)
                self.assertEqual(result['terms'],expected);self.assertTrue(result['recurrence_verified'])
                self.assertEqual(result['status'],'verified_closed_form')

    def test_fractional_initial_values_start_and_missing_closed_form_are_not_no_solution(self):
        result=solve_linear_recurrence([-2,1],['1/3'],start=2,terms=4)
        self.assertEqual(result['terms'],['1/3','2/3','4/3','8/3'])
        # recurrences.sp is a lazy proxy; patch the real sympy module instead
        # (attribute reads forward at call time, so the patch still applies).
        with patch('sympy.rsolve',return_value=None):
            result=solve_linear_recurrence([-1,1],[2],terms=3)
        self.assertEqual(result['status'],'terms_only');self.assertEqual(result['terms'],['2','2','2'])
        with patch('sympy.rsolve',return_value=sp.Integer(999)):
            result=solve_linear_recurrence([-1,1],[2])
        self.assertEqual(result['status'],'unverified_closed_form');self.assertFalse(result['recurrence_verified'])

    def test_singular_domains_nonlinear_or_executable_data_are_rejected(self):
        for coefficients,forcing in [([-1,'n-2'],0),(['1/(n-1)',1],0),([-1,1],'1/(n-100)'),([-1,1],'factorial(n-2)')]:
            with self.subTest(coefficients=coefficients,forcing=forcing),self.assertRaises(ValueError):solve_linear_recurrence(coefficients,[1],forcing)
        for text in ["__import__('os').getcwd()",'(lambda:1)()','n.__class__','[i for i in [1]]','factorial(1000000000)','2**(2**32)']:
            with self.subTest(text=text),self.assertRaises(ValueError):arithmetic_expression(text,{'n':sp.Symbol('n')},functions=True)


class NewContractPresentationTests(unittest.TestCase):
    def test_parameter_names_reject_keywords_and_non_strings(self):
        from graph_research.algebra.expressions import integer_symbols
        for names in (['lambda'], ['for'], [[]], ['n','n']):
            with self.subTest(names=names),self.assertRaises(ValueError):integer_symbols(names)

    def test_status_display_is_localized_without_changing_vertex_labels(self):
        from graph_research.rendering.results import display_field,display_value,terminal_result
        self.assertEqual(display_field('status','conditional'),'需满足所列条件')
        self.assertEqual(display_value('solved'),'solved')
        self.assertEqual(display_field('vertex','solved'),'solved')
        text=terminal_result({'tool':'integer_linear_system','ok':True,'result':{'status':'no_solution'}})
        self.assertIn('无整数解',text)


class IntegerSystemMigrationTests(unittest.TestCase):
    def test_unique_unsatisfiable_and_full_integer_lattice_solutions(self):
        result=solve_integer_linear_system([[2,4],[0,6]],[2,6]);self.assertEqual(result['solution'],['-1','1'])
        self.assertEqual(solve_integer_linear_system([[2]],[1])['status'],'no_solution')
        self.assertEqual(solve_integer_linear_system([[2],[4]],[2,5])['status'],'no_solution')
        result=solve_integer_linear_system([[2,4]],[2]);particular=sp.Matrix(list(map(sp.Rational,result['particular'])));basis=sp.Matrix(result['kernel_basis'])
        self.assertEqual(basis.cols,1);self.assertEqual(abs(basis[1,0]),1)
        generated={tuple(particular+basis*sp.Matrix([i])) for i in range(-10,11)}
        for y in range(-5,6):self.assertIn((1-2*y,y),generated)

    def test_random_constructed_integer_solutions_and_nullspace_residuals(self):
        randomizer=random.Random(20261017)
        for _ in range(20):
            a=sp.Matrix(2,3,[randomizer.randint(-3,3) for _ in range(6)]);x=sp.Matrix([randomizer.randint(-4,4) for _ in range(3)]);b=a*x
            result=solve_integer_linear_system(a,list(b));self.assertEqual(result['status'],'solved')
            particular=sp.Matrix(list(map(sp.Rational,result['particular'])));basis=sp.Matrix(result['kernel_basis'])
            self.assertEqual(a*particular,b);self.assertEqual(a*basis,sp.zeros(2,basis.cols))
            self.assertTrue(all(value.is_Integer for value in particular));self.assertEqual(basis.cols,3-a.rank())

    def test_parameter_divisibility_zero_rows_and_no_rational_relaxation(self):
        result=solve_integer_linear_system([[2]],['n'],['n']);self.assertEqual(result['status'],'conditional')
        self.assertTrue(any('Mod(n, 2)' in condition for condition in result['conditions']))
        result=solve_integer_linear_system([[1],[0]],[1,'p'],['p']);self.assertEqual(result['conditions'],['Eq(p, 0)'])
        for matrix,rhs,parameters in [([[1.5]],[1],None),([[2]],['1/2'],None),([[2]],['n/2'],['n']),([[1]],['unknown'],[])]:
            with self.subTest(matrix=matrix,rhs=rhs),self.assertRaises(ValueError):solve_integer_linear_system(matrix,rhs,parameters)
        with self.assertRaises(ValueError):solve_integer_linear_system([["__import__('os').getcwd()"]],[1])
        self.assertEqual(solve_integer_linear_system([[1.0]],[2])['solution'],['2'])


class ResearchFamilyMigrationTests(unittest.TestCase):
    def test_family_counts_degrees_and_paths_use_existing_composition(self):
        for constructor in (Gee,Gev,Gvv):
            h=constructor(3,[1,2],[1,1],k=4)
            self.assertEqual(h.size(),8);self.assertEqual(h.order(),25);self.assertEqual(h.uniform(),4);self.assertTrue(h.is_connected())
        gee=Gee(2,[1,1],[1,1]);gvv=Gvv(2,[1,1],[1,1]);self.assertEqual(max(gee.degree_sequence()),2);self.assertEqual(max(gvv.degree_sequence()),3)
        leaf,joint=Ca(3,2),Cva(3,2)
        self.assertEqual(max(leaf.degree_sequence()),2);self.assertEqual(max(joint.degree_sequence()),3)
        self.assertEqual(Cva(4,1,k=2).uniform(),2)
        with self.assertRaises(ValueError):Ca(4,1,k=2)

    def test_single_edge_rank_stays_explicit_and_inputs_are_not_modified(self):
        left,right=[1,0],[2];before=(left.copy(),right.copy())
        h=Gee(1,left,right,k=3);self.assertEqual(h.uniform(),3);self.assertEqual((left,right),before)
        with self.assertRaises(ValueError):Gee(1,[1,1],[1,1],k=3)
        de,dv={0:[1,2]},{1:[2]};before=copy.deepcopy((de,dv));h=GWG(3,de,dv,k=3)
        self.assertEqual((de,dv),before);self.assertEqual(h.size(),8)
        with self.assertRaises(ValueError):GWG(3,{1:[1,2]},k=3)

    def test_exact_structural_composition_and_registry_examples(self):
        expected=HyperPath(2,3).add_paths({0:1,3:2,2:1})
        self.assertTrue(IsIsomorphic(Gee(2,[1,2],[1]),expected))
        registry=ToolRegistry()
        for family in ('gee','gev','gvv','gwg','ca','cva'):
            result=registry.call('generate_hypergraph',{'family':family,'m':3,'k':3,'left_lengths':[1],'right_lengths':[2]})
            self.assertEqual(result['rank'],3);self.assertTrue(result['vertices'])
        with self.assertRaises(ValueError):registry.call('generate_hypergraph',{'family':'gvv','m':32,'k':8,'left_lengths':[16]*8})


class NewToolWorkflowTests(unittest.TestCase):
    def test_offline_protected_calls_and_model_composition_do_not_create_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session=OfflineToolSession(root/'offline',root/'packages')
            a=session.call_tool('linear_recurrence',{'coefficients':[-1,-1,1],'initial_values':[0,1]})
            b=session.call_tool('integer_linear_system',{'matrix':[[2]],'rhs':[1]})
            self.assertTrue(a['ok']);self.assertEqual(a['result']['terms'][8],'21')
            self.assertTrue(b['ok']);self.assertEqual(b['result']['status'],'no_solution')
            self.assertTrue(verify_bundle(session.result_bundle['archive'])['ok'])
            model=ScriptedModel([{'action':'call','tool':'generate_hypergraph','arguments':{'family':'ca','m':3,'k':3}},
                                 {'action':'final','answer':'已由现有构图操作生成结构，未新增算法。'}])
            research=ResearchSession(root/'chat',root/'packages');state=research.ask('构造带悬挂路的超圈',model)
            self.assertEqual(state['status'],'tool_results_available');self.assertFalse((root/'packages').exists())


if __name__=='__main__':unittest.main()
