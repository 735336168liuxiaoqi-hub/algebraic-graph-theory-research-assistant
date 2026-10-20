"""Scientific semantics and desktop/model routes for Python capability adapters."""
import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np

from graph_research.tools import ToolRegistry
from graph_research.rendering.layouts import graph_layout_positions

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class LibraryEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ToolRegistry()

    def test_repeated_edge_replacement_preserves_isolates_and_partial_product_structure(self):
        result = self.registry.call('graph_edit', {'operation':'replace_edges','kind':'edges','n':4,'edges':[[0,1],[1,2]],
                                                   'edit_edges':[[0,1],[1,2]],'replacement':{'kind':'path','n':3},'endpoints':[0,2]})
        graph = nx.Graph(); graph.add_nodes_from(result['vertices']); graph.add_edges_from(result['edges'])
        self.assertEqual(graph.degree(3), 0)
        self.assertEqual(sorted(len(c) for c in nx.connected_components(graph)), [1,5])
        self.assertEqual(result['order'], 6); self.assertEqual(result['size'], 4)
        result = self.registry.call('graph_edit', {'operation':'partial_product','kind':'path','n':3,'vertices':[1],
                                                   'replacement':{'kind':'path','n':2}})
        graph = nx.Graph(); graph.add_nodes_from(range(result['graph_spec']['n'])); graph.add_edges_from(result['graph_spec']['edges'])
        expected = nx.complete_graph(4); expected.remove_edge(0,1)
        self.assertTrue(nx.is_isomorphic(graph, expected))
        with self.assertRaises(ValueError):
            self.registry.call('graph_edit', {'operation':'partial_product','kind':'path','n':3,'vertices':[1,1],
                                               'replacement':{'kind':'path','n':2}})

    def test_rook_coefficients_against_independent_placement_enumeration(self):
        board = [[1,0,1],[1,1,0],[0,1,1]]
        cells = [(i,j) for i,row in enumerate(board) for j,value in enumerate(row) if value]
        expected = [sum(len({i for i,j in placement}) == k and len({j for i,j in placement}) == k
                        for placement in itertools.combinations(cells,k)) for k in range(4)]
        result = self.registry.call('combinatorial_calculation', {'operation':'rook_polynomial', 'board':board})
        self.assertEqual(result['coefficients_ascending'], expected)
        from graph_research.rendering.results import terminal_result
        shown = terminal_result({'ok':True,'tool':'combinatorial_calculation','result':result})
        self.assertIn('多项式：', shown); self.assertNotIn('特征多项式：', shown)
        self.assertEqual(self.registry.call('combinatorial_calculation', {'operation':'rook_polynomial','board':[[0,0]]})['coefficients_ascending'], [1])
        for invalid in ([[1],[1,0]], [[2]], [[True]]):
            with self.assertRaises(Exception):
                self.registry.call('combinatorial_calculation', {'operation':'rook_polynomial','board':invalid})

    def test_cayley_side_routes_keep_actual_noncommutative_arcs(self):
        from sympy.combinatorics import Permutation
        generators = [[1,0,2],[1,2,0]]
        results = {side:self.registry.call('combinatorial_calculation', {'operation':'cayley_graph', 'generators':generators, 'side':side})
                   for side in ('right','left','twosided')}
        groups = [Permutation(p) for p in results['right']['elements']]
        index = {g:i for i,g in enumerate(groups)}
        arcs = {side:{tuple(e) for e in result['arcs']} for side,result in results.items()}
        left = {(i,index[Permutation(s)*g]) for i,g in enumerate(groups) for s in generators if Permutation(s)*g != g}
        self.assertEqual(arcs['left'], left)
        self.assertNotEqual(arcs['left'], arcs['right'])
        self.assertEqual(arcs['twosided'], arcs['left'] | arcs['right'])
        for side,result in results.items():
            self.assertEqual(result['side'], side)
            self.assertEqual(result['elements'], results['right']['elements'])

    def test_coordinate_transform_metric_and_input_preservation(self):
        positions = [{'vertex':i,'xy':xy} for i,xy in enumerate([[0,0],[1,1],[2,0]])]
        original = copy.deepcopy(positions)
        records = graph_layout_positions(nx.path_graph(3), 'transform', positions, angle=90, scale=2, offset=[1,-1])
        actual = np.array([p['xy'] for p in records])
        np.testing.assert_allclose(actual, [[1,-1],[-1,1],[1,3]], atol=1e-12)
        self.assertEqual(positions, original)
        for i,j in itertools.combinations(range(3),2):
            self.assertAlmostEqual(np.linalg.norm(actual[i]-actual[j]), 2*np.linalg.norm(np.array(positions[i]['xy'])-positions[j]['xy']))

    def test_fixed_spring_alignment_and_rooted_tree(self):
        positions = [{'vertex':i,'xy':xy} for i,xy in enumerate([[0,0],[1,1],[2,0]])]
        records = graph_layout_positions(nx.path_graph(3), positions=positions, fixed_vertices=[0,2], iterations=20)
        self.assertEqual(records[0], positions[0]); self.assertEqual(records[2], positions[2])
        aligned = graph_layout_positions(nx.path_graph(3), 'align_horizontal', positions, vertices=[0,1])
        self.assertEqual(aligned[0]['xy'][1], .5); self.assertEqual(aligned[1]['xy'][1], .5)
        self.assertEqual(aligned[2], positions[2])
        rooted = graph_layout_positions(nx.path_graph(5), 'tree', root=2)
        self.assertEqual(rooted[2]['xy'], [0,0])
        self.assertEqual([record['xy'][1] for record in rooted], [-2,-1,0,-1,-2])
        for kwargs in ({'fixed_vertices':[0]}, {'operation':'tree','root':10}, {'operation':'transform'}, {'positions':positions[:2]}):
            with self.assertRaises(ValueError):graph_layout_positions(nx.path_graph(3), **kwargs)
        with self.assertRaises(ValueError):graph_layout_positions(nx.cycle_graph(4), 'tree')

    def test_plot_export_coordinate_roundtrip_and_dependent_tikz(self):
        with tempfile.TemporaryDirectory() as directory, patch('pathlib.Path.cwd', return_value=Path(directory)):
            result = self.registry.call('graph_layout', {'operation':'circular','kind':'path','n':4})
            self.assertEqual(result['graph_spec'], {'kind':'edges','n':4,'edges':[[0,1],[1,2],[2,3]]})
            saved = json.loads(Path(result['files']['coordinates']).read_text(encoding='utf-8'))
            self.assertEqual(saved['positions'], result['positions'])
            self.assertTrue(Path(result['files']['png']).read_bytes().startswith(b'\x89PNG'))
            exported = self.registry.call('graph_tikz', {'edges':result['edges'],'vertices':result['vertices'],'positions':result['positions']})
            self.assertTrue(Path(exported['files']['standalone']).is_file())
            coordinates = [{'vertex':0,'xy':[0,0]}, {'vertex':1,'xy':[0,1]}]
            overlapped = self.registry.call('graph_layout', {'operation':'align_horizontal','kind':'path','n':2,'positions':coordinates})
            self.assertEqual(overlapped['positions'][0]['xy'], overlapped['positions'][1]['xy'])
            self.assertEqual(overlapped['preview_status'], 'not_rendered')
            self.assertTrue(overlapped['warnings']); self.assertNotIn('png', overlapped['files'])
            self.assertTrue(Path(overlapped['files']['coordinates']).is_file())

    def test_lattice_equivalence_rectangular_board_and_literal_labels(self):
        with tempfile.TemporaryDirectory() as directory, patch('pathlib.Path.cwd', return_value=Path(directory)):
            direct = self.registry.call('combinatorial_plot', {'operation':'grid_path','steps':[1,0,1,0]})
            indexed = self.registry.call('combinatorial_plot', {'operation':'lattice_path','total_steps':4,'right_steps':[0,2]})
            self.assertEqual(direct['points'], indexed['points']); self.assertEqual(direct['endpoint'], [2,2])
            board = self.registry.call('combinatorial_plot', {'operation':'chessboard','matrix':[[1,0,1],[0,1,0]],'row_labels':['$not_latex$','上行']})
            self.assertEqual(board['shape'], [2,3]); self.assertEqual(board['row_labels'][0], '$not_latex$')
            for path in board['files'].values():self.assertTrue(Path(path).is_file())
            with self.assertRaises(ValueError):self.registry.call('combinatorial_plot', {'operation':'lattice_path','total_steps':2,'right_steps':[2]})
            with self.assertRaises(ValueError):self.registry.call('combinatorial_plot', {'operation':'chessboard','matrix':[[1,0]],'row_labels':['x','y']})

    def test_shared_desktop_catalog_and_model_contracts(self):
        from graph_research.assistant.offline import grouped_tools
        from graph_research.tools.contracts import function_definitions
        from graph_research.tools.input_guides import input_guide
        from graph_research.graph_input.document import document
        from graph_research.graph_input.adapters import graph_patch
        names = {'combinatorial_plot', 'graph_layout'}
        drawing = next(g for g in grouped_tools(self.registry) if g['name']=='绘图、布局与LaTeX')
        self.assertTrue(names <= {t['name'] for t in drawing['tools']})
        self.assertTrue(names <= {t['name'] for t in function_definitions(self.registry)})
        from graph_research.assistant.model_context import model_catalog
        catalog = self.registry.catalog(detail='model')
        for query, expected in [('画出棋盘和格路径','combinatorial_plot'),
                                 ('做谱布局并固定顶点重新排列','graph_layout'),
                                 ('批量替换边再做局部笛卡尔积','graph_edit')]:
            self.assertIn(expected, {tool['name'] for tool in model_catalog(catalog, query, [])[1]})
        for name in names:
            guide = input_guide(self.registry.describe(name))
            self.assertEqual(len(guide['fields']), len(self.registry.describe(name)['parameters']['properties']))
        graph = document(['甲','乙','孤立点'], [{'vertices':['甲','乙']}])
        patched = graph_patch(graph, self.registry.describe('graph_layout'))
        self.assertEqual({k:v for k,v in patched['patch'].items() if k!='graph_document'}, {'kind':'edges','n':3,'edges':[[0,1]]})
        self.assertEqual(patched['patch']['graph_document'],graph.to_dict())
        self.assertIn('positions', patched['remove'])
        from graph_research.graph_input.adapters import result_graph
        source = document(['甲','乙'], [{'vertices':['甲','乙']}], positions=[[0,0],[1,0]])
        patched = graph_patch(source, self.registry.describe('graph_layout'))
        self.assertEqual(patched['patch']['positions'], [{'vertex':0,'xy':[0,0]},{'vertex':1,'xy':[1,0]}])
        result = {'graph_spec':{'kind':'edges','n':2,'edges':[[0,1]]},
                  'positions':[{'vertex':0,'xy':[2,3]},{'vertex':1,'xy':[3,3]}]}
        reused = result_graph({'ok':True, 'tool':'graph_layout', 'result':result,
                               'graph_inputs':[{'document':source.to_dict(),'target':'graph'}]})
        self.assertEqual(reused.to_dict()['vertices'], ['甲','乙'])
        self.assertEqual(reused.to_dict()['positions'], [[2,3],[3,3]])

    def test_offline_protected_calls_preserve_all_artifacts_in_verified_bundle(self):
        from graph_research.assistant.offline import OfflineToolSession
        from graph_research.assistant.results import verify_bundle
        from graph_research.runtime.integrity import verify
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = OfflineToolSession(root/'session', root/'tools', results_directory=root/'results')
            fingerprint = verify()['manifest_sha256']
            with patch('graph_research.assistant.model.ConfiguredModel', side_effect=AssertionError('No model call')):
                layout = session.call_tool('graph_layout', {'operation':'circular','kind':'path','n':3})
                board = session.call_tool('combinatorial_plot', {'operation':'chessboard','matrix':[[1,0,1],[0,1,0]]})
            self.assertTrue(layout['ok'], layout); self.assertTrue(board['ok'], board)
            self.assertEqual(layout['result']['preview_status'], 'rendered')
            self.assertTrue(verify_bundle(session.result_bundle['archive'], session.result_bundle['sha256'])['ok'])
            self.assertEqual(session.result_bundle['summary']['verified_calls'], 2)
            self.assertEqual(verify()['manifest_sha256'], fingerprint)

    def test_mcp_example_executes_real_bound_layout_to_tikz_without_model(self):
        from graph_research.mcp.runtime import MCPResearchRuntime, HostConfiguration
        example = Path(__file__).resolve().parents[1]/'examples/library_entries/layout-to-tikz.mcp.json'
        task = json.loads(example.read_text(encoding='utf-8'))['task']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = MCPResearchRuntime(HostConfiguration(str(root), 'library-entry-test'))
            result = runtime.submit(task, wait_seconds=2)
            try:
                deadline = time.monotonic()+35
                while result.get('transport',{}).get('active') and time.monotonic()<deadline:
                    result = runtime.get(result['task_id'], wait_seconds=2, until='terminal')
                self.assertEqual(result['status'], 'completed', result)
                self.assertEqual(result['budget']['used'], {'tool_calls':2,'model_calls':0})
                self.assertTrue(any(root.rglob('*.tex')))
                self.assertTrue(any(root.rglob('positions.json')))
            finally:
                if result.get('transport',{}).get('active'):
                    runtime.cancel(result['task_id'])
                for process in runtime.children.values():
                    if process.poll() is None:process.wait(10)


if __name__ == '__main__':unittest.main()
