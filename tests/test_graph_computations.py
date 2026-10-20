"""Tests compare functional graph properties and exact identities, not names."""
import itertools
import math
import unittest
import networkx as nx
import numpy as np
import sympy as sp
from graph_research import graphs as gg
from graph_research import hypergraphs as hg
from graph_research.tensors import Tensor,HyperMatrix
from graph_research.registry import ToolRegistry


class OrdinaryGraphTests(unittest.TestCase):
    def test_hermitian_directed_spectrum(self):
        g=nx.DiGraph([(0,1),(1,2),(2,0)])
        h=gg.hermitian_adjacency_matrix(g)
        np.testing.assert_allclose(h,h.conj().T)
        np.testing.assert_allclose(gg.eigenpairs(g,type="H",spe=True),[math.sqrt(3),0,-math.sqrt(3)],atol=1e-12)
        self.assertEqual(gg.exact_characteristic_polynomial(g,"H").as_expr(),sp.Symbol("x")**3-3*sp.Symbol("x"))

    def test_exact_symbolic_alpha_characteristic_polynomial(self):
        x,a=sp.symbols("x alpha")
        polynomial=gg.exact_characteristic_polynomial(nx.path_graph(3),"alpha",a).as_expr()
        self.assertEqual(sp.expand(polynomial.subs(a,0)),x**3-2*x)
        self.assertEqual(sp.expand(polynomial.subs(a,1)),sp.expand((x-1)**2*(x-2)))

    def test_spectral_projectors_and_angles(self):
        g=nx.cycle_graph(5); a=gg.alpha_matrix(g)
        projectors=gg.spectral_projectors(g)
        np.testing.assert_allclose(sum(p["projector"] for p in projectors),np.eye(5),atol=1e-12)
        np.testing.assert_allclose(sum(p["eigenvalue"]*p["projector"] for p in projectors),a,atol=1e-12)
        for p in projectors: np.testing.assert_allclose(p["projector"]@p["projector"],p["projector"],atol=1e-12)
        _,angles=gg.angle(g)
        np.testing.assert_allclose((angles**2).sum(axis=0),1,atol=1e-12)

    def test_orbits_and_equitable_quotient(self):
        expected={frozenset([0,4]),frozenset([1,3]),frozenset([2])}
        self.assertEqual(set(map(frozenset,gg.orbit_subdivision(nx.path_graph(5)))),expected)
        result=gg.equitable_quotient(nx.star_graph(4))
        self.assertTrue(result["equitable"])
        np.testing.assert_allclose(sorted(np.linalg.eigvals(result["quotient"])),[-2,2],atol=1e-12)
        self.assertFalse(gg.equitable_quotient(nx.path_graph(3),[[0,1],[2]])["equitable"])
        self.assertEqual(gg.automorphism_group(nx.cycle_graph(4)).order(),8)

    def test_h_join_and_symbolic_average_quotient(self):
        base=nx.path_graph(2)
        replacement=[nx.empty_graph(2),nx.empty_graph(3)]
        g=gg.H_join(base,replacement)
        self.assertTrue(nx.is_isomorphic(g,nx.complete_bipartite_graph(2,3)))
        a=sp.Symbol("alpha"); q=gg.HJQM(base,{0:(2,0),1:(3,0)},a)
        self.assertEqual(q,sp.Matrix([[3*a,3*(1-a)],[2*(1-a),2*a]]))

    def test_structure_transformations(self):
        g=gg.K_subdivide_graph(nx.path_graph(3),2)
        self.assertTrue(nx.is_isomorphic(g,nx.path_graph(7)))
        self.assertTrue(nx.is_isomorphic(gg.theta_graph([2,2,2]),nx.complete_bipartite_graph(2,3)))
        self.assertTrue(nx.is_tree(gg.caterpillar(3,{0:2,2:1})))
        rooted=gg.rooted_product(nx.path_graph(2),{0:(0,nx.path_graph(3)),1:(0,nx.path_graph(3))})
        self.assertTrue(nx.is_isomorphic(rooted,nx.path_graph(6)))
        self.assertEqual(len(gg.corona_graphs(nx.path_graph(3),nx.empty_graph(2))),9)
        self.assertTrue(nx.is_isomorphic(gg.Blowup(nx.path_graph(2),[0,1],2),nx.cycle_graph(4)))
        with self.assertRaises(ValueError): ToolRegistry().call("graph_construction",{"family":"caterpillar","n":3,"attachments":[[0,1000000000]]})

    def test_paths_cycles_and_hamiltonian_enumeration(self):
        g=nx.complete_graph(4)
        self.assertEqual(len(gg.findCycles(g,3)),4)
        self.assertEqual(len(gg.Find_all_hamiltonian_cycles(g)),3)
        self.assertEqual(len(gg.All_Paths(nx.cycle_graph(4),0,2,2)),2)
        self.assertIsNone(gg.Find_hamiltonian_cycle(nx.path_graph(5)))
        self.assertEqual(len(gg.Find_hamiltonian_cycle(nx.complete_graph(10))),10)
        tree=gg.path_tree(nx.cycle_graph(3),0)
        self.assertEqual(len(tree),5); self.assertTrue(nx.is_tree(tree))
        self.assertEqual(gg.get_appand_paths(nx.path_graph(4)),[[0,1,2,3]])
        with self.assertRaises(RuntimeError): gg.Count_Subgraph(nx.complete_graph(5),nx.path_graph(3),max_embeddings=5)

    def test_degree_realizations_against_graph_atlas(self):
        for degrees in ([2]*6,[3]*6,[2,2,1,1]):
            actual=gg.Graphs_WithDegreeSequence(degrees)
            reference=[g for g in nx.graph_atlas_g() if len(g)==len(degrees) and sorted(dict(g.degree()).values())==sorted(degrees)]
            self.assertEqual(len(actual),len(reference))
            self.assertTrue(all(any(nx.is_isomorphic(g,h) for h in reference) for g in actual))
        self.assertEqual(gg.Graphs_WithDegreeSequence([1,1,1]),[])

    def test_cospectral_grouping_and_matching_recurrence(self):
        self.assertEqual(len(gg.findCospe([nx.path_graph(3),nx.star_graph(2),nx.complete_graph(3)])[0]),2)
        for n in range(1,8): self.assertEqual(gg.abscharpoly_path(n),gg.abscharpoly(nx.path_graph(n)))
        x=sp.Symbol("x")
        self.assertEqual(gg.gen_poly(4,sp.Poly(1,x),sp.Poly(x,x)),sp.Poly(x**4+3*x**2+1,x))

    def test_random_generation_invariants(self):
        for k in (0,1,3):
            graph=gg.RandomKCyclicGraph(8,k,seed=3)
            self.assertTrue(nx.is_connected(graph)); self.assertEqual(graph.number_of_edges()-len(graph)+1,k)
        cactus=gg.RandomCactusGraph([3,4,5],seed=1)
        self.assertEqual(sorted(map(len,nx.cycle_basis(cactus))),[3,4,5])
        unicycle=gg.Random_Unicyclic_Graph([3,2],4,seed=2)
        self.assertEqual(len(unicycle),7); self.assertEqual(unicycle.number_of_edges(),7)

    def test_block_tensor_products(self):
        a=np.arange(4).reshape(2,2); b=np.array([[1,2],[3,4]])
        np.testing.assert_array_equal(gg.Khatri_Rao_Product(a,b),np.kron(a,b))
        blocks=([1,1],[1,1])
        np.testing.assert_array_equal(gg.Khatri_Rao_Product(a,b,blocks,blocks),a*b)
        np.testing.assert_array_equal(gg.Tracy_Singh_Product(a,b,blocks,blocks),np.kron(a,b))


class HypergraphComputationTests(unittest.TestCase):
    def test_weighted_and_diagonal_quotients(self):
        for graph in (hg.HyperStar(3,3),hg.HyperCycle(3,3),hg.HyperPath(3,3)):
            quotient=hg.Quotient_Graph(graph)
            for a in (0,0.3,0.8):
                self.assertAlmostEqual(graph.alpha_spectrum(a)["rho"],quotient.alpha_spectrum(a)["rho"],places=8)
        with self.assertRaises(ValueError): hg.OrbitQuotient(hg.HyperPath(3,3),[list(range(7))])
        # Legacy representative-edge construction is not a spectral quotient.
        path=hg.HyperPath(3,3)
        self.assertGreater(abs(path.alpha_spectrum(0)["rho"]-hg.edge_representative_quotient(path).alpha_spectrum(0)["rho"]),0.1)

    def test_weights_flags_and_legacy_metadata(self):
        graph=hg.Hypergraph([[0,1,2]],weights=[2])
        self.assertAlmostEqual(graph.alpha_spectrum(.4)["rho"],2,places=9)
        self.assertAlmostEqual(graph.Alpha_Spectral_Radius(.4,edge_weighted=False)[0],1,places=9)
        graph.Edges[0].weight=3
        self.assertAlmostEqual(graph.alpha_spectrum(0)["rho"],3,places=9)
        clone=graph.copy(); clone.Edge_Weigth[0]=4
        self.assertEqual(graph.weights[0],3)
        self.assertEqual(graph.Index([0,1,2]),[0])

    def test_hypergraph_symbolic_equations_and_orbits(self):
        graph=hg.HyperStar(3,3)
        self.assertEqual(sorted(map(len,graph.orbit_subdivision())),[1,6])
        self.assertEqual(len(graph.reduced_eigenequs()),2)
        single=hg.Hypergraph([[0,1,2]],weights=[2])
        x0,x1,x2,l=sp.symbols("x0 x1 x2 lambda")
        self.assertEqual(single.eigen_equation()[0],l*x0**2-2*x1*x2)

    def test_attach_expand_clone_and_cartesian(self):
        star=hg.VStarLike(1,1,1,rank=3)
        self.assertTrue(hg.IsIsomorphic(star,hg.HyperStar(3,3)))
        edge_star=hg.EStarLike(1,2,rank=3)
        self.assertEqual((edge_star.size(),edge_star.order()),(4,9))
        original=hg.HyperPath(2,2)
        expanded=hg.blowup_edge(original,1)
        self.assertTrue(hg.IsIsomorphic(expanded,hg.HyperPath(2,3)))
        single=hg.Hypergraph([[0,1,2]])
        all_clones=hg.blowup_vertex(single,{0:2})
        cartesian=hg.Blow_Up(single,{0:2})
        self.assertEqual((all_clones.rank,all_clones.size()),(4,1))
        self.assertEqual((cartesian.rank,cartesian.size()),(3,2))
        product=hg.cartesian_product_H(hg.HyperPath(1,2),hg.HyperPath(1,2))
        self.assertTrue(nx.is_isomorphic(nx.from_numpy_array(product.adjacency_matrix()),nx.cycle_graph(4)))

    def test_inner_paths_coalescence_and_subdivision(self):
        graph=hg.Add_innerPath(hg.Hypergraph(vertices=[0,1]),[0,1],3,k=3)
        self.assertTrue(hg.IsIsomorphic(graph,hg.HyperPath(3,3)))
        base=hg.HyperPath(2,3)
        sub=hg.subdivide_edge(base,base.Edges[0],3)
        self.assertTrue(hg.IsIsomorphic(sub,hg.HyperPath(4,3)))
        merged=hg.Coalescence_Hypergraphs(hg.HyperPath(1,3),hg.HyperPath(1,3),[[0],[0]],True)
        self.assertTrue(hg.IsIsomorphic(merged,hg.HyperPath(2,3)))
        self.assertEqual(len(hg.HyperPath(3,3).all_paths(0,3)),1)

    def test_bicyclic_families_have_cycle_rank_two(self):
        for graph in (hg.Bicyclic_C1([1,2,2]),hg.Bicyclic_C2([2,1,1]),hg.Bicyclic_C3([1,2])):
            self.assertTrue(graph.is_uniform()); self.assertTrue(graph.is_connected())
            self.assertEqual(hg.CyclomaticNumber(graph),2)

    def test_matching_polynomial_is_not_tensor_charpoly(self):
        x=sp.Symbol("x")
        self.assertEqual(hg.Matching_Polynomial(hg.Hypergraph([[0,1,2]])).as_expr(),x**3-1)
        self.assertEqual(hg.Matching_Polynomial(hg.HyperStar(3,3)).as_expr(),x**7-3*x**4)
        for n in range(2,6):
            graph=nx.path_graph(n)
            self.assertEqual(hg.Matching_Polynomial(hg.Hypergraph(graph)),gg.exact_characteristic_polynomial(graph))

    def test_associated_incidence_graph_and_reduced_matrix(self):
        graph=hg.HyperStar(3,3); matrix=graph.WeightIncidenceMatrix(.2)
        np.testing.assert_allclose(matrix.sum(axis=1),1,atol=1e-9)
        self.assertEqual(graph.WeightIncidenceMatrix(.2,reduced=True).shape,(1,3))
        associated=graph.Associated_Weight_Bipartite_Graph(.2)
        self.assertEqual(associated.number_of_edges(),9)
        self.assertTrue(all(data["weight"]>0 for _,_,data in associated.edges(data=True)))

    def test_tensor_compatibility_repairs(self):
        a=np.array([[1,2],[3,4]]); b=np.array([[5,6],[7,8]])
        np.testing.assert_array_equal(Tensor(a).tensordot(b),a@b)
        self.assertEqual(Tensor(a).contract(b,axes=2).array.item(),70)
        with self.assertRaises(ValueError): HyperMatrix(a)+HyperMatrix([10,20])
        self.assertIsInstance(HyperMatrix(a)+HyperMatrix(b),HyperMatrix)


if __name__=="__main__": unittest.main()
