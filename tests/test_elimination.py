import itertools
import unittest
from unittest.mock import patch
import networkx as nx
import numpy as np
import sympy as sp
from graph_research import Hypergraph,HyperPath,Tensor
from graph_research.elimination import (action_characteristic_polynomial,tensor_characteristic_polynomial,
    hypergraph_characteristic_polynomial,comp_charpoly,exact_scalar,EliminationLimits,EliminationLimitError)
from graph_research.registry import ToolRegistry


L=sp.Symbol("lambda")


class ExactEliminationTests(unittest.TestCase):
    def test_rank_two_matches_ordinary_exact_matrix_polynomial(self):
        for graph in [nx.path_graph(4),nx.complete_graph(3),nx.empty_graph(3)]:
            h=Hypergraph(graph)
            actual=hypergraph_characteristic_polynomial(h,rank=2)
            expected=sp.Matrix(nx.to_numpy_array(graph,dtype=int)).charpoly(L).as_poly()
            self.assertEqual(actual,expected)

    def test_single_edges_and_algebraic_multiplicities(self):
        for rank in (2,3,4):
            actual=Hypergraph([list(range(rank))]).characteristic_polynomial()
            total=rank*(rank-1)**(rank-1); exponent=rank**(rank-2)
            expected=sp.Poly(L**(total-rank*exponent)*(L**rank-1)**exponent,L)
            self.assertEqual(actual,expected)

    def test_laplacian_signless_and_symbolic_alpha(self):
        h=Hypergraph([[0,1,2]]); a=sp.Symbol("alpha")
        for matrix,shift,scale in [("L",1,-1),("Q",1,1),("alpha",a,1-a)]:
            actual=hypergraph_characteristic_polynomial(h,matrix=matrix,alpha=a if matrix=="alpha" else 0)
            expected=sp.Poly((L-shift)**3*((L-shift)**3-scale**3)**3,L)
            self.assertTrue(sp.Poly(actual.as_expr()-expected.as_expr(),L).is_zero)

    def test_complete_three_uniform_four_vertex_hypergraph(self):
        h=Hypergraph(list(itertools.combinations(range(4),3)))
        p=h.characteristic_polynomial()
        self.assertEqual(p.degree(),32)
        self.assertEqual(p.nth(29),-24)
        self.assertEqual(p.nth(28),-42)
        self.assertEqual(p.eval(3),0)
        expected=L**4*(L-3)*(L-1)**10*(L+1)**9*(L**2+L+4)**4
        self.assertEqual(p,sp.Poly(expected,L))

    def test_complete_five_vertex_hypergraph_and_three_loose_edges(self):
        p=Hypergraph(list(itertools.combinations(range(5),3))).characteristic_polynomial()
        self.assertEqual((p.degree(),p.nth(77),p.nth(76),p.eval(6)),(80,-120,-420,0))
        p=HyperPath(3,3).characteristic_polynomial()
        self.assertEqual((p.degree(),p.nth(445)),(448,-144))

    def test_one_dimensional_tensor_has_linear_characteristic_polynomial(self):
        self.assertEqual(tensor_characteristic_polynomial([[[2]]]),sp.Poly(L-2,L))

    def test_two_loose_edges(self):
        p=HyperPath(2,3).characteristic_polynomial()
        self.assertEqual(p,sp.Poly(L**35*(L**3-1)**6*(L**3-2)**9,L))
        self.assertEqual(p.degree(),80)

    def test_isolated_vertices_and_disjoint_component_exponents(self):
        h=Hypergraph([[0,1,2]],vertices=range(4))
        self.assertEqual(h.characteristic_polynomial(),sp.Poly(L**14*(L**3-1)**6,L))
        h=Hypergraph([[0,1,2],[3,4,5]])
        self.assertEqual(h.characteristic_polynomial(),sp.Poly(L**48*(L**3-1)**48,L))

    def test_zero_tensor_and_alpha_one_diagonal_keep_all_zero_factors(self):
        self.assertEqual(tensor_characteristic_polynomial(np.zeros((3,3,3),dtype=int)),sp.Poly(L**12,L))
        h=HyperPath(2,3)
        self.assertEqual(h.characteristic_polynomial(matrix="alpha",alpha=1),sp.Poly((L-1)**64*(L-2)**16,L))
        self.assertEqual(comp_charpoly([[0,0,0],[0,0,0],[0,0,2]],variable=L),sp.Poly(L**2*(L-2),L))

    def test_independent_binary_univariate_resultant(self):
        x,y=sp.symbols("x y")
        for rank in (3,4):
            data=np.arange(1,2**rank+1,dtype=object).reshape((2,)*rank)
            action=[]
            for i in range(2):
                action.append(sum(data[(i,)+indices]*sp.prod([x,y][j] for j in indices)
                                  for indices in itertools.product(range(2),repeat=rank-1)))
            expected=sp.Poly(sp.resultant((L*x**(rank-1)-action[0]).subs(y,1),
                                         (L*y**(rank-1)-action[1]).subs(y,1),x),L)
            self.assertEqual(tensor_characteristic_polynomial(data),expected)

    def test_dense_rank_one_tensor_and_legacy_tensor_method(self):
        data=np.ones((3,3,3),dtype=int)
        expected=sp.Poly(L**8*(L-9)*(L-1)**3,L)
        self.assertEqual(Tensor(data).characteristic_polynomial(),expected)

    def test_rational_weights_are_not_rounded(self):
        h=Hypergraph([[0,1,2]])
        p=h.characteristic_polynomial(weights=["2/3"])
        self.assertEqual(p,sp.Poly(L**3*(L**3-sp.Rational(8,27))**3,L))
        self.assertEqual(exact_scalar(0.1),sp.Rational(1,10))
        with self.assertRaises(ValueError): exact_scalar("__import__('os')")

    def test_relabeling_and_scalar_shift_invariance(self):
        h=Hypergraph([["a","b","c"],["b","c","d"]])
        self.assertEqual(h.characteristic_polynomial(),h.Relabel().characteristic_polynomial())
        rows=[{(2,0):1,(1,1):2,(0,2):3},{(2,0):4,(1,1):5,(0,2):6}]
        p=action_characteristic_polynomial(rows,3)
        shifted=[dict(row) for row in rows]
        shifted[0][2,0]+=2; shifted[1][0,2]+=2
        self.assertEqual(action_characteristic_polynomial(shifted,3),sp.Poly(p.as_expr().subs(L,L-2),L))

    def test_invalid_domain_and_explicit_limits(self):
        h=Hypergraph([[0,1,2]])
        with self.assertRaises(EliminationLimitError): h.characteristic_polynomial(limits=EliminationLimits(max_macaulay_size=14))
        with self.assertRaises(EliminationLimitError): h.characteristic_polynomial(limits=EliminationLimits(max_block_size=2))
        with self.assertRaises(ValueError): h.characteristic_polynomial(rank=4)
        with self.assertRaises(ValueError): Hypergraph([[0,1],[1,2,3]]).characteristic_polynomial()
        with self.assertRaises(ValueError): action_characteristic_polynomial([{(1,0):1},{}],3)
        with self.assertRaises(ValueError): tensor_characteristic_polynomial(np.zeros((2,3)))

    def test_exact_division_metadata_and_no_sage_process_dependency(self):
        with patch("subprocess.run",side_effect=AssertionError("External runtime")):
            result=Hypergraph([[0,1,2]]).characteristic_polynomial(details=True)
        self.assertTrue(result.metadata["exact_division"])
        component=result.metadata["components"][0]
        self.assertEqual((component["numerator_degree"],component["denominator_degree"]),(15,3))

    def test_registered_isolated_tools_and_estimation(self):
        registry=ToolRegistry()
        result=registry.call("hypergraph_tensor_charpoly",{"edges":[[0,1,2]]})
        self.assertEqual(result["degree"],12)
        estimate=registry.call("hypergraph_tensor_charpoly",{"edges":[[0,1,2],[2,3,4]],"estimate_only":True})
        self.assertEqual(estimate["global"]["macaulay_size"],210)
        self.assertEqual(registry.call("tensor_charpoly",{"data":[[0,1],[1,0]]})["degree"],2)
        with self.assertRaises(RuntimeError): registry.call("hypergraph_tensor_charpoly",{"edges":[[0,1,2]],"rank":4,"estimate_only":True})

    def test_timeout_is_not_reported_as_a_partial_answer(self):
        import subprocess
        from graph_research.elimination_tools import run_elimination
        with patch("graph_research.runtime.runner.run_worker",side_effect=TimeoutError("Simulated protected-worker timeout")):
            with self.assertRaisesRegex(RuntimeError,"no partial polynomial"):
                run_elimination({"mode":"tensor","data":[[0,1],[1,0]]})


if __name__=="__main__": unittest.main()
