import builtins
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np
import sympy as sp

from graph_research import Hypergraph, HyperPath, HyperCycle, HyperStar, Tensor, HyperMatrix
from graph_research import graphs, combinatorics, polynomials, linear_algebra, utilities
from graph_research.tensors import zeros_hypermatrix, identity_hypermatrix, DiagonalTensor
from graph_research.registry import ToolRegistry
from graph_research.extensions import ToolStore, RestrictedPython
from graph_research.agent import build_agent
from graph_research.workflow import build_workflow
from tests.feature_helpers import approve_for_tests


class NativeMathematicsTests(unittest.TestCase):
    def test_graph_spectra_against_analytic_formulas(self):
        for n in (2,3,7):
            for kind,expected in [("path",2*math.cos(math.pi/(n+1))),("complete",n-1),("star",math.sqrt(n-1))]:
                with self.subTest(kind=kind,n=n):
                    self.assertAlmostEqual(graphs.graph_spectrum(kind,n)["rho"],expected,places=10)
        for alpha in (0,0.4,0.9):
            self.assertAlmostEqual(graphs.graph_spectrum("cycle",7,matrix="alpha",alpha=alpha)["rho"],2,places=10)

    def test_hypergraph_spectra_and_full_incidence(self):
        for rank in (2,3,4):
            h = HyperStar(3,rank)
            result = h.alpha_spectrum(0)
            self.assertAlmostEqual(result["rho"],3**(1/rank),places=9)
            self.assertLessEqual(result["relative_residual"],1e-11)
            incidence = h.weighted_incidence_from_result(result)
            np.testing.assert_allclose(incidence.sum(axis=1),1,atol=1e-9)
        self.assertAlmostEqual(HyperCycle(3,3).alpha_spectrum(0)["rho"],2**(2/3),places=9)
        self.assertAlmostEqual(Hypergraph([[0,1,2]],weights=[2]).alpha_spectrum(0.6)["rho"],2,places=9)

    def test_relabeling_and_perron_vector_order(self):
        h = Hypergraph([["a","b","c"],["a","d","e"]])
        result = h.alpha_spectrum(0)
        self.assertEqual(result["vertex_order"],["a","b","c","d","e"])
        self.assertAlmostEqual(result["rho"],2**(1/3),places=9)
        self.assertEqual(len(h.incidence_edges(["a","b"])),1)

    def test_generator_structure(self):
        self.assertEqual((HyperPath(4,3).order(),HyperPath(4,3).size()),(9,4))
        self.assertEqual(HyperCycle(4,3).order(),8)
        self.assertEqual(HyperCycle(2,3).order(),4)
        with self.assertRaises(ValueError): HyperCycle(2,2)

    def test_hypergraph_rejects_invalid_inputs_and_nonconvergence(self):
        for edges in ([[0,0]],[[0,1],[1,0]]):
            with self.assertRaises(ValueError): Hypergraph(edges)
        with self.assertRaises(ValueError): Hypergraph([[0,1],[2,3]]).alpha_spectrum(0)
        self.assertEqual(HyperPath(2,3).alpha_spectrum(1)["rho"],2)
        with self.assertRaises(ArithmeticError): HyperStar(3,3).alpha_spectrum(0,max_iterations=1)

    def test_sparse_tensor_action_agrees_with_dense_tensor(self):
        h = HyperPath(2,3)
        a = h.adjacency_tensor()
        self.assertTrue(a.is_symmetric())
        for edge in h.Edges:
            self.assertEqual(a[tuple(edge)],0.5)
        rho, x = a.SpectralRadius()
        self.assertAlmostEqual(rho,h.alpha_spectrum()["rho"],places=8)
        diagonal = DiagonalTensor([2,5],3)
        self.assertAlmostEqual(diagonal.SpectralRadius()[0],5)
        self.assertEqual((diagonal**-1).shape,(2,2,2))

    def test_tensor_generalized_products_and_zero_bugfix(self):
        a,b = np.array([[1,2],[3,4]]),np.array([[2,0],[1,2]])
        np.testing.assert_array_equal(Tensor(a).shao_mul(Tensor(b)).array,a@b)
        np.testing.assert_array_equal((HyperMatrix(a)*HyperMatrix(b)).array,a@b)
        self.assertEqual(float(zeros_hypermatrix((2,2,2)).array.sum()),0)
        self.assertEqual(float(identity_hypermatrix((2,2,2)).array.sum()),2)
        sym = Tensor(np.arange(8).reshape(2,2,2)).symmetrized()
        self.assertTrue(sym.is_symmetric())

    def test_characteristic_polynomial_and_inertia(self):
        x=sp.Symbol("x")
        self.assertEqual(graphs.charpolys_for_graph(nx.path_graph(3),"A").as_expr(),x**3-2*x)
        self.assertEqual(graphs.inertias_of_graph(nx.path_graph(3)),(1,1,1))
        np.testing.assert_allclose(graphs.normalized_laplace_matrix(nx.empty_graph(2)),np.zeros((2,2)))

    def test_quotient_matrix_and_graph_operations(self):
        g=nx.complete_bipartite_graph(2,3)
        q=graphs.Quotient_Matrix(graphs.alpha_matrix(g),[[0,1],[2,3,4]])
        np.testing.assert_array_equal(q,[[0,3],[2,0]])
        self.assertEqual(len(graphs.coalescence_graphs([nx.path_graph(3)]*2,[0,0])),5)
        self.assertEqual(graphs.join_graphs([nx.empty_graph(2),nx.empty_graph(3)]).number_of_edges(),6)
        self.assertTrue(nx.is_isomorphic(graphs.seidel_switching(graphs.seidel_switching(g,[0]),[0]),g))
        self.assertEqual(graphs.Count_Subgraph(nx.complete_graph(3),nx.path_graph(3)),3)

    def test_exact_combinatorics(self):
        self.assertEqual(combinatorics.Partition_Number(8,3),5)
        self.assertEqual(combinatorics.divMatrix(5)*combinatorics.mobuisMatrix(5),sp.eye(5))
        x=sp.Symbol("x")
        self.assertEqual(combinatorics.matching_generating_function(nx.path_graph(4)).as_expr(),x**2+3*x+1)
        self.assertEqual(combinatorics.rook_polynomial([[1,1],[1,1]]).as_expr(),2*x**2+4*x+1)
        self.assertEqual(combinatorics.num_cycletype([2,1]),3)

    def test_roots_include_multiple_roots_and_endpoints(self):
        x=sp.Symbol("x"); f=sp.Poly((x-1)**2*(x+1),x)
        self.assertEqual(polynomials.num_realroots(f,-1,1),2)
        self.assertEqual(polynomials.find_all_roots(f,-1,1),[-1,1])
        self.assertEqual(polynomials.num_chg([1,0,-1,0,1]),2)

    def test_symbolic_matrix_function(self):
        a=sp.Matrix([[1,1],[0,1]])
        self.assertEqual(linear_algebra.matrix_function_Jordan(a,lambda x:x**2),a**2)
        self.assertEqual(linear_algebra.charmat([[0,1],[1,0]]).det(),sp.Symbol("x")**2-1)
        self.assertEqual(utilities.Gensubs(sp.Symbol("x")+1,{sp.Symbol("x"):2}),3)
        self.assertEqual(utilities.seq_iter(3,lambda x:x+2,1),7)

    def test_no_sage_or_subprocess_needed_for_native_workflow(self):
        real_import=builtins.__import__
        def native_import(name,*args,**kwargs):
            if name=="sage" or name.startswith("sage."): raise AssertionError("Sage dependency")
            return real_import(name,*args,**kwargs)
        with patch("builtins.__import__",side_effect=native_import),patch("subprocess.run",side_effect=AssertionError("External process")):
            result=build_workflow().invoke({"task":{"graphs":[{"name":"star","edges":[[0,1,2],[0,3,4]]}],"alphas":[0,0.5]}})
        self.assertEqual(result["status"],"complete")
        self.assertTrue(all(row["result"]["backend"]=="native-python" for row in result["rows"]))

    def test_frozen_sage_nine_case_regression(self):
        path=Path(__file__).resolve().parents[1]/"graph_research/data/sage_reference.json"
        old=json.loads(path.read_text(encoding="utf-8"))
        native=build_workflow().invoke({"task":old["task"]})
        self.assertEqual(native["status"],"complete")
        for before,after in zip(old["rho_values"],native["rows"]):
            self.assertAlmostEqual(before,after["result"]["rho"],places=8)


class ToolAndExtensionTests(unittest.TestCase):
    def setUp(self):
        self.registry=ToolRegistry()
        path=Path(__file__).resolve().parents[1]/"graph_research/data/h_index_proposal.json"
        self.proposal=json.loads(path.read_text(encoding="utf-8"))

    def test_all_catalog_tools(self):
        examples={"generate_hypergraph":{"family":"path","m":2,"k":3},
                  "hypergraph_spectrum":{"edges":[[0,1,2]],"alpha":0.3,"weighted_incidence":True},
                  "graph_spectrum":{"kind":"path","n":3},"graph_invariants":{"kind":"cycle","n":4},
                  "graph_characteristic_polynomial":{"kind":"path","n":3},
                  "matching_polynomial":{"kind":"path","n":4},"matrix_analysis":{"matrix":[[1,2],[2,1]]},
                  "polynomial_roots":{"coefficients":[1,0,-1],"a":-1,"b":1},
                  "quotient_matrix":{"matrix":[[0,1],[1,0]],"blocks":[[0],[1]]},
                  "tensor_spectrum":{"data":[[0,1],[1,0]]},
                  "combinatorial_calculation":{"operation":"partition_number","n":8,"k":3},
                  "graph_edit":{"operation":"complement","kind":"path","n":4},
                  "exact_matrix_operation":{"matrix":[[1,2],[3,4]],"operation":"inverse"},
                  "tensor_operation":{"data":[[1,2],[3,4]],"operation":"symmetrize"}}
        examples.update({"graph_construction":{"family":"theta","lengths":[2,2,2]},
                         "graph_symmetry":{"kind":"star","n":5},
                         "graph_spectral_analysis":{"operation":"alpha_charpoly","kind":"path","n":3,"symbolic_alpha":True},
                         "compare_graphs":{"left":{"kind":"path","n":3},"right":{"kind":"star","n":3}},
                         "graph_enumeration":{"operation":"cycles","kind":"cycle","n":4,"length":4},
                         "hypergraph_structure":{"edges":[[0,1,2]],"operation":"matching_poly"},
                         "hypergraph_transform":{"edges":[[0,1,2]],"operation":"expand_edges","count":1},
                         "hypergraph_quotient_spectrum":{"edges":[[0,1,2],[0,3,4]],"alpha":0.3},
                         "directed_graph_spectrum":{"n":3,"arcs":[[0,1],[1,2],[2,0]]}})
        examples.update({"hypergraph_tensor_charpoly":{"edges":[[0,1,2]]},"tensor_charpoly":{"data":[[0,1],[1,0]]}})
        examples["hypergraph_plot"]={"edges":[[0,1,2],[2,3]]}
        examples["hypergraph_editor"]={"edges":[[0,1,2],[2,3]]}
        examples["hypergraph_tikz"]={"edges":[[0,1,2],[2,3]]}
        examples["graph_tikz"]={"edges":[[0,1],[1,2]]}
        examples['hypergraph_schematic']=self.registry.describe('hypergraph_schematic')['documentation']['examples'][0]['arguments']
        examples["linear_recurrence"]={"coefficients":[-1,-1,1],"initial_values":[0,1]}
        examples["integer_linear_system"]={"matrix":[[2]],"rhs":[1]}
        for name in ('weighted_graph_spectrum','graph_recipe','hypergraph_path_analysis','graph_batch_study','symbolic_analysis','block_matrix_analysis','graph_class_certificate','graph_energy_study','research_environment','combinatorial_plot','graph_layout'):
            examples[name]=self.registry.describe(name)['documentation']['examples'][0]['arguments']
        self.assertEqual(set(examples),set(self.registry.tools))
        for name,args in examples.items():
            with self.subTest(tool=name): json.dumps(self.registry.call(name,args),allow_nan=False)

    def test_tool_argument_schema_rejects_unknown_and_nonfinite(self):
        with self.assertRaises(Exception): self.registry.call("graph_spectrum",{"n":3,"arbitrary_code":"..."})
        with self.assertRaises(ValueError): self.registry.call("graph_spectrum",{"alpha":float("nan")})

    def test_new_tool_is_tested_persisted_and_reloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ToolStore(directory)
            receipt=store.install(self.proposal,self.registry,approve_for_tests(store,self.proposal,self.registry))
            self.assertEqual(receipt["tests_passed"],3)
            result=self.registry.call("degree_h_index",{"degrees":[2,2,2,2,2]})
            self.assertEqual(result['h_index'],2)
            fresh=ToolRegistry(); store.load_into(fresh)
            self.assertEqual(fresh.call("degree_h_index",{"degrees":[]}),{"h_index":0})

    def test_failed_fixtures_never_register_a_tool(self):
        bad=copy.deepcopy(self.proposal); bad["tests"][0]["expected"]={"h_index":123}
        with tempfile.TemporaryDirectory() as directory:
            store=ToolStore(directory)
            with self.assertRaises(ArithmeticError): store.install(bad,self.registry,approve_for_tests(store,bad,self.registry))
            self.assertNotIn(bad["name"],self.registry.tools)
            self.assertFalse(Path(directory,bad["name"]).exists())

    def test_generated_code_cannot_import_or_access_attributes(self):
        for source in ["def run(args):\n    import os\n    return 1", "def run(args):\n    return args.__class__", "def run(args):\n    return open('x')"]:
            with self.subTest(source=source),self.assertRaises(ValueError): RestrictedPython(source,self.registry)

    def test_instruction_budget(self):
        runner=RestrictedPython("def run(args):\n    i = 0\n    while True:\n        i += 1",self.registry,budget=100)
        with self.assertRaises(RuntimeError): runner.run({})

    def test_agent_composes_existing_tools_without_creating_a_package(self):
        decisions=[{"action":"call","tool":"graph_invariants","arguments":{"kind":"cycle","n":5}},
                   {"action":"call","tool":"graph_spectrum","arguments":{"kind":"cycle","n":5}},
                   {"action":"final","answer":"已有工具已给出结构和谱，边密度可由顶点和边数计算，无需新增包。"}]
        class ScriptedModel:
            def complete(self,messages): return decisions.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            result=build_agent(ScriptedModel(),ToolRegistry(),ToolStore(directory)).invoke({"question":"求C5边密度"})
        self.assertEqual(result["status"],"tool_results_available")
        self.assertTrue(all(row["ok"] for row in result["observations"]))
        self.assertEqual(result["observations"][0]["result"]['size'],5)


if __name__=="__main__": unittest.main()
