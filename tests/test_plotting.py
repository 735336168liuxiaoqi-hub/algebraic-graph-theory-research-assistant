"""Geometric membership checks for the scientific hypergraph renderer."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import networkx as nx
from matplotlib.path import Path as MplPath

from graph_research import Hypergraph, HyperGraphPlot
from graph_research.plotting import hyperedge_path
from graph_research.registry import ToolRegistry


class HypergraphPlotTests(unittest.TestCase):
    def test_simple_graph_families_use_solid_black_segments_and_keep_every_vertex(self):
        samples=[nx.path_graph(5),nx.cycle_graph(6),nx.complete_graph(5),nx.empty_graph(4),nx.Graph()]
        disconnected=nx.Graph();disconnected.add_nodes_from([1,'1','孤立点','other']);disconnected.add_edge(1,'1');samples.append(disconnected)
        for graph in samples:
            with self.subTest(vertices=list(graph),edges=list(graph.edges())):
                h=Hypergraph(graph);figure=h.plot()
                self.assertEqual(set(figure.hypergraph_positions),set(graph))
                self.assertEqual(len(figure.hypergraph_paths),graph.number_of_edges())
                for edge,path,patch in zip(h.Edges,figure.hypergraph_paths,figure.axes[0].patches):
                    np.testing.assert_array_equal(path.codes,[MplPath.MOVETO,MplPath.LINETO])
                    np.testing.assert_array_equal(path.vertices,[figure.hypergraph_positions[v] for v in edge])
                    np.testing.assert_allclose(patch.get_edgecolor(),[0,0,0,1]);self.assertEqual(patch.get_linestyle(),'solid')
                code=h.to_tikz()
                self.assertEqual(code.count(r'\fill[black]'),graph.number_of_nodes())
                self.assertEqual(code.count('{HTML}{000000}'),graph.number_of_edges())
                self.assertNotIn('dashed',code);self.assertNotIn('dotted',code);self.assertNotIn('.. controls',code)

    def test_spline_interpolates_all_members_and_is_unfilled(self):
        h = Hypergraph([[0,1,2], [1,2], [2,3,4,5]], vertices=list(range(7)))
        pos = {0:(0,0),1:(1,1),2:(2,0),3:(3,1),4:(4,0),5:(3,-1),6:(1,-1)}
        figure = h.plot(pos=pos)
        self.assertEqual(len(figure.axes[0].patches),3)
        for edge,path,patch in zip(h.Edges, figure.hypergraph_paths,figure.axes[0].patches):
            self.assertFalse(patch.get_fill())
            endpoints = path.vertices[[0,1]] if len(edge)==2 else path.vertices[[0]+list(range(3,len(path.vertices)-1,3))]
            for v in edge:
                self.assertTrue(np.any(np.all(np.isclose(endpoints,pos[v]),axis=1)))
            if len(edge)>2:
                self.assertEqual(path.codes[-1],MplPath.CLOSEPOLY)
                np.testing.assert_array_equal(path.vertices[0],path.vertices[-1])
        self.assertEqual(set(figure.hypergraph_positions),set(range(7)))

    def test_tcb_controls_match_original_sage_tangents(self):
        p=np.array([[0,0],[2,0],[0,2]],dtype=float)
        path=hyperedge_path(p)
        # Original t=.5,c=.5,b=0: outgoing=.375*before+.125*after.
        expected=p[0]+(.375*(p[0]-p[2])+.125*(p[1]-p[0]))/3
        np.testing.assert_allclose(path.vertices[1],expected)

    def test_collinear_curve_still_passes_members_without_collapsing(self):
        path=hyperedge_path([[0,0],[1,0],[2,0]])
        self.assertGreater(np.ptp(path.vertices[:,1]),0)
        for x in (0,1,2):
            self.assertTrue(any(np.array_equal(p,[x,0]) for p in path.vertices))

    def test_inside_vertex_is_not_added_to_curve(self):
        pos={0:(0,0),1:(2,0),2:(1,2),3:(1,.5)}
        fig=Hypergraph([[0,1,2]],vertices=list(pos)).plot(pos=pos)
        endpoints=fig.hypergraph_paths[0].vertices[[0,3,6,9]]
        self.assertFalse(any(np.array_equal(p,pos[3]) for p in endpoints))

    def test_disconnected_layout_preserves_component_scale(self):
        h=Hypergraph([[0,1,2],[2,3],[3,4,5,6]],vertices=list(range(8)))
        first=h.plot(seed=42).hypergraph_positions
        second=h.plot(seed=42).hypergraph_positions
        for v in first:
            np.testing.assert_array_equal(first[v],second[v])
        body=np.array([first[v] for v in range(7)])
        all_points=np.array(list(first.values()))
        self.assertGreater(np.ptp(body,axis=0).max()/np.ptp(all_points,axis=0).max(),.5)
        self.assertEqual(len({tuple(p) for p in first.values()}),8)

    def test_manual_positions_defaults_and_validation(self):
        h=Hypergraph([["a","b","c"]])
        pos={"a":(0,0),"b":(1,0),"c":(0,1)}
        h.set_pos(pos)
        self.assertEqual(h.get_pos(),pos)
        np.testing.assert_array_equal(h.plot().hypergraph_positions['b'],[1,0])
        a=h.graphplot(edge_labels=True).plot(edge_labels=False)
        self.assertFalse(any(text.get_text()=='e0' for text in a.axes[0].texts))
        for invalid in ({"a":(0,0)}, {**pos,"c":(float('nan'),1)}, {**pos,"c":(0,0)}):
            with self.assertRaises(ValueError): h.plot(pos=invalid)

    def test_headless_exports_empty_graph_and_tool(self):
        h=Hypergraph([[0,1],[1,2,3]])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for extension in ('png','svg','pdf'):
                path=h.save_plot(root/f'graph.{extension}',edge_labels=True)
                self.assertGreater(path.stat().st_size,100)
            Hypergraph(vertices=[0,1]).save_plot(root/'isolates.svg')
            Hypergraph().save_plot(root/'empty.svg')
            with patch('graph_research.plotting.Path.cwd',return_value=root):
                result=ToolRegistry().call('hypergraph_plot',{'edges':[[0,1],[1,2,3]],'vertices':[0,1,2,3,4]})
            self.assertFalse(result['uniform'])
            self.assertEqual(result['edge_members'],[[0,1],[1,2,3]])
            self.assertTrue(all(Path(p).exists() for p in result['files'].values()))


if __name__ == '__main__':
    unittest.main()
