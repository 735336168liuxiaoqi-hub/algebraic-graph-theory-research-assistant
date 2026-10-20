"""Independent mathematical oracles for the second Sage replacement batch."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np
import sympy as sp
from sympy.combinatorics.named_groups import SymmetricGroup

from graph_research import graphs as gg,hypergraphs as hg
from graph_research.algebra import elementary as el
from graph_research.algebra.groups import getCycleIndex,getCycleIndex1,cayley_graph,permutation_group,group_calculation
from graph_research.assistant import OfflineToolSession,verify_bundle
from graph_research.tools import ToolRegistry


class NetworkXReplacementTests(unittest.TestCase):
    def test_weights_grouped_edges_defaults_and_invalid_updates_are_atomic(self):
        graph=nx.path_graph(4);graph.add_node('isolate');graph[1][2]['weight']=7
        before=copy.deepcopy(graph)
        result=gg.set_edge_weight(graph,{(0,1):2,3:[(2,3)]},default_weight=5)
        self.assertEqual([result[u][v]['weight'] for u,v in [(0,1),(1,2),(2,3)]],[2,7,3])
        self.assertTrue(nx.utils.graphs_equal(graph,before))
        with self.assertRaises(ValueError):gg.set_edge_weight(graph,{(0,1):2,(8,9):1},copy=False)
        self.assertTrue(nx.utils.graphs_equal(graph,before))
        matrix=gg.weight_edges(graph,{(0,1):2})
        np.testing.assert_array_equal(matrix,[[0,2,0,0,0],[2,0,7,0,0],[0,7,0,1,0],[0,0,1,0,0],[0,0,0,0,0]])
        self.assertIs(gg.set_edge_weight(graph,{(0,1):4},copy=False),graph)
        with self.assertRaises(ValueError):gg.weight_edges(graph,{(0,1):float('nan')})

    def test_complex_orientations_and_degree_reciprocal_matrix(self):
        graph=nx.cycle_graph(3);matrix=gg.complex_weight(graph,[(0,1)])
        np.testing.assert_array_equal(matrix,[[0,1j,1],[-1j,0,1],[1,1,0]])
        self.assertFalse(any('weight' in data for _,_,data in graph.edges(data=True)))
        with self.assertRaises(ValueError):gg.complex_weight(graph,[(0,1),(1,0)])
        graph=nx.path_graph(3);graph.add_node('isolated')
        np.testing.assert_array_equal(gg.AMdb(graph),[[0,1.5,0,0],[1.5,0,1.5,0],[0,1.5,0,0],[0,0,0,0]])

    def test_edge_substitution_preserves_isolates_attributes_and_root_identification(self):
        graph=nx.path_graph(3);graph.add_node('isolated');graph.nodes[0]['color']='red'
        replacement=nx.path_graph(['u','middle','v']);replacement.add_node('new-isolate');replacement['u']['middle']['weight']=2
        before=copy.deepcopy((graph,replacement));result=gg.edge2graph(graph,(0,1),'u','v',replacement)
        self.assertEqual(len(result),6);self.assertEqual(result.number_of_edges(),3)
        self.assertEqual(sum(d==0 for _,d in result.degree()),2);self.assertEqual(result.nodes[0]['color'],'red')
        self.assertEqual(sorted(d for _,d in result.degree()),[0,0,1,1,2,2])
        self.assertTrue(nx.utils.graphs_equal(graph,before[0]));self.assertTrue(nx.utils.graphs_equal(replacement,before[1]))
        with self.assertRaises(ValueError):gg.replace_edges_by_graph(graph,[replacement]*2,[(0,1),(1,0)],[('u','v')]*2)

    def test_partial_product_has_expected_explicit_edges_and_prevents_label_collision(self):
        graph=nx.path_graph(4);result=gg.PartProduct(graph,[1,2],nx.path_graph(2))
        expected=[((1,0),(1,1)),((2,0),(2,1)),((1,0),(2,0)),((1,1),(2,1)),
                  (0,(1,0)),(0,(1,1)),(3,(2,0)),(3,(2,1))]
        self.assertEqual({frozenset(edge) for edge in result.edges()},{frozenset(edge) for edge in expected})
        graph.add_node((1,0))
        with self.assertRaises(ValueError):gg.PartProduct(graph,[1,2],nx.path_graph(2))

    def test_degree_groups_cycles_copies_subtraction_and_random_symmetry(self):
        graph=nx.star_graph(3);graph.add_node('iso')
        self.assertEqual(gg.pick_vertices(graph),{0:['iso'],1:[1,2,3],3:[0]})
        self.assertEqual(gg.pick_vertices(graph,-1),(3,[0]))
        self.assertEqual(gg.list2dict([('a',1),('b',2),('a',3)]),{'a':[1,3],'b':[2]})
        self.assertTrue(nx.is_isomorphic(gg.Cycle(['a','b','c','d']),nx.cycle_graph(4)))
        self.assertEqual(nx.number_connected_components(gg.mygraphmul(nx.path_graph(2),3)),3)
        self.assertTrue(nx.is_isomorphic(gg.mygraphmul(nx.path_graph(2),nx.path_graph(2)),nx.cycle_graph(4)))
        self.assertEqual(len(gg.mygraphsub(graph,nx.path_graph(3))),5)
        for seed in range(4):
            matrix=gg.random_symmetric_matrix(5,-2,3,seed=seed)
            np.testing.assert_array_equal(matrix,matrix.T);self.assertTrue(np.all((-2<=matrix)&(matrix<=3)))

    def test_old_edge_container_mapping_and_coefficient_signs(self):
        edges=[hg.edge([0,1,2]),hg.edge([2,3])]
        for i,edge in enumerate(edges):edge.index=i
        self.assertEqual(gg.Index(edges),[0,1]);self.assertEqual(tuple(edges[0]-[1]),(0,2))
        self.assertTrue(edges[0].issuperset([0,2]));self.assertEqual(tuple(edges[0]&[1,2]),(1,2))
        self.assertEqual(set(edges[0]+edges[1]),{0,1,2,3});self.assertEqual(edges[0][1],1)
        x=sp.Symbol('x');self.assertEqual(gg.checksign1(sp.Poly(x**3-2*x,x)),{-1,1})

    def test_leaf_schur_expression_matches_independently_constructed_graphs(self):
        x=sp.Symbol('x')
        for kind in ('L','Q'):
            for graph,counts in [(nx.path_graph(3),{0:2,1:1}),(nx.cycle_graph(3),{1:2}),(nx.empty_graph(2),{0:1})]:
                expanded=graph.copy();node=len(graph)
                for root,count in counts.items():
                    for _ in range(count):expanded.add_edge(root,node);node+=1
                exact=gg.exact_graph_matrix(expanded,kind).charpoly(x).as_expr()
                self.assertEqual(sp.expand(gg.polynomials_for_addstarsgraph(graph,counts,type=kind)-exact),0)
        k=sp.Symbol('k',integer=True,nonnegative=True)
        symbolic=gg.polynomials_for_addstarsgraph(nx.path_graph(2),{0:k})
        for value in (0,1,3):
            self.assertEqual(sp.simplify(symbolic.subs(k,value)-gg.polynomials_for_addstarsgraph(nx.path_graph(2),{0:value})),0)
        with self.assertRaises(ValueError):gg.polynomials_for_addstarsgraph(nx.path_graph(2),{0:1},type='A')


class SymPyReplacementTests(unittest.TestCase):
    def test_elementary_operations_symbolic_fractions_and_atomic_in_place(self):
        original=sp.Matrix([[1,2],[3,4]])
        np.testing.assert_array_equal(np.array(el.do_Actions(original,[('r3',1,0,-3)]),dtype=int),[[1,2],[0,-2]])
        self.assertEqual(el.el_rop2(original,(0,'1/2')),sp.Matrix([[sp.Rational(1,2),1],[3,4]]))
        self.assertEqual(el.el_rop3(original,(1,0,-3)),sp.Matrix([[1,2],[0,-2]]))
        self.assertEqual(el.el_cop2(original,(0,2)),sp.Matrix([[2,2],[6,4]]))
        self.assertEqual(el.el_cop3(original,(1,0,-2)),sp.Matrix([[1,0],[3,-2]]))
        self.assertEqual(el.do_Actions(original,[('r1',0,1),('c1',0,1)]),sp.Matrix([[4,3],[2,1]]))
        with self.assertRaises(ValueError):el.do_Actions(original,[('r2',0,2),('r1',0,9)],True)
        self.assertEqual(original,sp.Matrix([[1,2],[3,4]]))
        self.assertIs(el.do_Actions(original,[('r2',0,2)],True),original)
        self.assertEqual(original,sp.Matrix([[2,4],[3,4]]))

    def test_determinant_row_linearity_and_vector_decomposition(self):
        a=sp.Matrix([[1,2,3],[4,0,6],[7,8,10]])
        pieces=el.split_row(a,1,[[1,0,2],[2,0,1]],False)
        self.assertEqual(sum((m[1,:] for m in pieces[1:]),sp.zeros(1,3)),a[1,:])
        self.assertEqual(sum(m.det() for m in pieces[1:]),a.det())
        self.assertEqual(sum(el.split_vector([0,2,3]),sp.zeros(3,1)),sp.Matrix([0,2,3]))
        self.assertEqual(el.split_vector([0,0]),[])
        with self.assertRaises(ValueError):el.split_row([[1,2,3]],0,[])

    def test_latex_is_explicit_and_does_not_change_global_printer_or_mutate(self):
        a=sp.Matrix([[1,2],[3,4]]);before=sp.latex(a)
        self.assertIn(r'\begin{vmatrix}',el.lst2ltx([a],Det=True))
        self.assertIn('+',el.sum_hold([a,a]));self.assertIn(r'\xrightarrow',el.Op_links([('r3',1,0,-2)]))
        self.assertIn(r'\leftarrow',el.do_show_ops(a,[('c2',0,2)]))
        self.assertIn(r'\begin{vmatrix}',el.split_row(a,0,[[1,0]]));self.assertEqual(sp.latex(a),before)
        self.assertEqual(a,sp.Matrix([[1,2],[3,4]]))
        x=sp.Symbol('x');self.assertIn('&=',el.show_equtions([sp.Eq(2*x,3)]))
        normalized=el.stdequs([sp.Eq(x+1,3*x-2)])[0]
        self.assertEqual(sp.expand(normalized.lhs-normalized.rhs-((x+1)-(3*x-2))),0)
        with self.assertRaises(ValueError):el.stdequs([sp.Eq(x*x,2)])

    def test_exact_polynomial_domain_and_tolerance_aware_rounding(self):
        x=sp.Symbol('x');a=sp.Matrix([[x*x,1],[x,sp.Rational(1,2)]])
        domain=el.Mat2PR(a);self.assertEqual(domain.to_Matrix(),a);self.assertEqual(str(domain.domain),'QQ[x]')
        exact=sp.Rational(1,3);large=10**40+1
        values=el.map_round([exact,large,1.000000000001],ndigits=2,eps=1e-10)
        self.assertEqual(values,[exact,large,1]);self.assertEqual(el.matrix_round([[exact]],2,1e-10)[0],exact)
        self.assertEqual(el.map_round(np.array([.3333]),2,1e-10)[0],.3333)
        with self.assertRaises(ValueError):el.map_round([float('inf')])


class FiniteGroupReplacementTests(unittest.TestCase):
    def test_standard_cycle_index_matches_s3_and_independent_burnside_orbits(self):
        group=SymmetricGroup(3);x1,x2,x3=sp.symbols('x1 x2 x3')
        z=getCycleIndex(group);self.assertEqual(sp.expand(z-(x1**3+3*x1*x2+2*x3)/6),0)
        members=list(group.generate_schreier_sims())
        for colors in (2,3):
            representatives={min(tuple(assignment[p(i)] for i in range(3)) for p in members) for assignment in itertools.product(range(colors),repeat=3)}
            self.assertEqual(z.subs({x1:colors,x2:colors,x3:colors}),len(representatives))

    def test_old_partition_encoding_is_preserved_and_not_mistaken_for_standard_index(self):
        x0,x1,x2=sp.symbols('x0 x1 x2')
        old=getCycleIndex1(SymmetricGroup(3))
        self.assertEqual(sp.expand(old-(x0*x1*x2+3*x0*x0*x1+2*x0**3)/6),0)
        self.assertNotEqual(old,getCycleIndex(SymmetricGroup(3)))
        with self.assertRaises(ValueError):permutation_group([[1,2,3,4,0],[1,0,2,3,4]],max_order=20)
        with self.assertRaises(ValueError):permutation_group([[0,1],[0,0]])

    def test_cayley_directions_labels_loops_and_finite_semigroup_support(self):
        group=SymmetricGroup(3)
        for side in ('left','right','twosided'):
            graph=cayley_graph(group,side=side)
            self.assertEqual(len(graph),6)
            for source,target,data in graph.edges(data=True):
                generator=group.generators[data['generator']]
                self.assertEqual(target,generator*source if data['side']=='left' else source*generator)
        graph=cayley_graph([0,1],generators={'zero':0,'one':1})
        self.assertEqual(graph.number_of_edges(),4);self.assertEqual(nx.number_of_selfloops(graph),3)
        simple=cayley_graph([0,1],generators=[0,1],simple=True)
        self.assertEqual(set(simple.edges()),{(1,0)})
        self.assertTrue(nx.is_strongly_connected(cayley_graph(group,simple=True)))
        self.assertEqual(group_calculation('cayley_graph',[[1,0,2],[1,2,0]])['n'],6)


class HypergraphReplacementTests(unittest.TestCase):
    def test_shared_root_star_is_not_a_chain_and_preserves_weights_and_isolates(self):
        graph=hg.Hypergraph([[0,1,2]],vertices=[0,1,2,'isolated'],weights=[2])
        result=graph.add_star([0,1],2)
        self.assertEqual(result.hyperedges(),[(0,1,2),(0,1,3),(0,1,4)])
        self.assertEqual(list(result.weights),[2,1,1]);self.assertIn('isolated',result.Vertices)
        self.assertEqual(graph.order(),4);self.assertEqual(result.degree(0),3)
        second=hg.add_stars(graph,{(0,1):2,2:1});self.assertEqual(second.size(),4)
        unweighted=hg.add_star(hg.Hypergraph([[0,1,2]]),[0,1],2)
        self.assertAlmostEqual(unweighted.alpha_spectrum(0)['rho'],3**(2/3),places=8)
        with self.assertRaises(ValueError):hg.add_star(graph,[0,1,2],1)

    def test_laplacian_equations_match_tensor_contraction_with_custom_variables(self):
        graph=hg.Hypergraph([['a','b','c']]);variables=sp.symbols('u v w');lam=sp.Symbol('ell')
        equations=graph.eigenVfun(lam,variables);point=np.array([1,2,3])
        contraction=np.einsum('ijk,j,k->i',graph.laplacian_tensor().array,point,point)
        substitutions={**dict(zip(variables,point)),lam:7}
        np.testing.assert_allclose([float(eq.subs(substitutions)) for eq in equations],7*point**2-contraction)
        with self.assertRaises(ValueError):hg.Hypergraph([[0,1],[1,2,3]]).eigenVfun()


@unittest.skipUnless(importlib.util.find_spec('matplotlib'),'Optional Matplotlib unavailable')
class CombinatorialDrawingReplacementTests(unittest.TestCase):
    def test_lattice_coordinates_shapes_and_rendering(self):
        from graph_research import combinatorics as c
        figure,points=c.gridPath([1,0,1],withPoints=True)
        self.assertEqual(points,[(0,0),(1,0),(1,1),(2,1)])
        self.assertEqual(c.lattice_path(3,[0,2],withPoints=True)[1],points)
        self.assertEqual(len(c.getGridPath([0,1]).axes[0].lines),1)
        self.assertEqual(len(c.rectangle(0,0,2,3).axes[0].patches),1)
        board=c.chess_board([[1,0,1],[0,1,0]],lambda i,j:'black' if (i+j)%2 else 'white',row_label=['r0','r1'],col_label=['c0','c1','c2'])
        self.assertEqual(len(board.axes[0].patches),6);self.assertEqual([t.get_text() for t in board.axes[0].get_yticklabels()],['r0','r1'])
        image=io.BytesIO();figure.savefig(image,format='png');self.assertTrue(image.getvalue().startswith(b'\x89PNG'))


class ReplacementIntegrationTests(unittest.TestCase):
    def test_every_available_catalog_entry_resolves_to_an_actual_callable(self):
        import importlib
        root=Path(__file__).resolve().parents[1]
        records=json.loads((root/'docs/provenance/migration_catalog.json').read_text(encoding='utf-8'))['definitions']
        for record in records:
            if record['status']!='native_implementation_available':continue
            with self.subTest(source=record['source_file'],symbol=record['symbol']):
                target=importlib.import_module(record['native_module'])
                for part in record['native_symbol'].split('.'):target=getattr(target,part)
                self.assertTrue(callable(target))

    def test_new_branches_run_protected_and_cayley_composes_with_existing_spectrum(self):
        with tempfile.TemporaryDirectory() as directory:
            session=OfflineToolSession(Path(directory)/'session',Path(directory)/'packages')
            cayley=session.call_tool('combinatorial_calculation',{'operation':'cayley_graph','generators':[[1,0,2],[1,2,0]]})
            self.assertTrue(cayley['ok']);structure=cayley['result']
            spectrum=session.call_tool('directed_graph_spectrum',{'n':structure['n'],'arcs':structure['arcs'],'matrix':'A'})
            self.assertTrue(spectrum['ok']);self.assertAlmostEqual(spectrum['result']['rho'],2)
            calls=[('exact_matrix_operation',{'operation':'split_row','matrix':[[1,2],[3,4]],'row_terms':[[1,0]]}),
                   ('hypergraph_transform',{'edges':[[0,1,2]],'operation':'attach_star','roots':[0,1],'count':2}),
                   ('hypergraph_structure',{'edges':[[0,1,2]],'operation':'laplacian_equations'})]
            for name,args in calls:self.assertTrue(session.call_tool(name,args)['ok'])
            self.assertTrue(verify_bundle(session.result_bundle['archive'])['ok'])
            self.assertFalse((Path(directory)/'packages').exists())

    def test_catalog_extraction_keeps_string_defaults_and_complete_multiline_tex(self):
        from tools import build_migration_catalog as builder
        source='def gridPath(seq, co="blue"):\n    return seq\n\ndef Graph2TeX(graph):\n    tex = r\'\'\'\n\\begin{document}\ntext\n\\end{document}\n\'\'\'\n    return tex\n\nnext_value = 1\n\nclass MissingWidget:\n    def __init__(self):\n        pass\n'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'source').mkdir();(root/'graph_research/data').mkdir(parents=True)
            (root/'source/fixture.sage').write_text(source,encoding='utf-8')
            with patch.multiple(builder,ROOT=root,SOURCE=root/'source',NAMES=['fixture'],MODULES={'fixture':'combinatorics'}),redirect_stdout(io.StringIO()):builder.main()
            rows=json.loads((root/'docs/provenance/migration_catalog.json').read_text(encoding='utf-8'))['definitions']
            self.assertEqual([row['symbol'] for row in rows],['gridPath','Graph2TeX','MissingWidget','MissingWidget.__init__'])
            self.assertEqual(rows[-1]['status'],'pending')
            self.assertIn('return tex',rows[1]['source']);self.assertNotIn('next_value',rows[1]['source'])


if __name__=='__main__':unittest.main()
