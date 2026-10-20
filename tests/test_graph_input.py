"""Lossless inputs, native editing and execution-bound original-label provenance."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import networkx as nx
import numpy as np
from graph_research.graph_input import GraphDocument,GraphInputError,GraphLibrary,parse_graph,graph_family
from graph_research.graph_input.document import document,strict_json
from graph_research.graph_input.adapters import graph_patch,graph_targets,bound_inputs,validate_bindings,validate_sources,result_graph,model_graph_text
from graph_research.tools import ToolRegistry


def binding(graph,definition,target='graph',arguments=None):
    prepared=graph_patch(graph,definition,target,arguments)
    result={k:prepared[k] for k in ('target','patch','vertex_mapping')};result['document']=graph.to_dict()
    if 'case_index' in prepared:result['case_index']=prepared['case_index']
    return result


class InputParsingTests(unittest.TestCase):
    def test_quick_input_typed_labels_isolates_and_immutable_snapshot(self):
        graph=parse_graph('1 a\n"1" a',vertices_text='1 "1" a isolated')
        self.assertEqual(graph.vertices,(1,'1','a','isolated'));self.assertEqual(graph.size,2)
        data=graph.to_dict();data['vertices'].append('unwanted');self.assertEqual(graph.order,4)
        source=graph.to_dict();frozen=GraphDocument(source);source['edges'][0]['vertices'][0]='changed'
        self.assertEqual(frozen,graph)

    def test_nonuniform_hypergraph_weights_and_incidence_zero_rows(self):
        hyper=parse_graph('{a b c} | 2\n{c d} | 3',graph_type='hypergraph',weighted=True)
        self.assertFalse(hyper.uniform);self.assertEqual([e['weight'] for e in hyper.edges],[2,3])
        matrix=parse_graph('1 0\n1 0\n1 1\n0 1\n0 0','incidence','hypergraph')
        self.assertEqual(matrix.order,5);self.assertEqual([e['vertices'] for e in matrix.edges],[[0,1,2],[2,3]])

    def test_adjacency_weight_direction_and_complex_conjugation(self):
        real=parse_graph('0,2,0\n2,0,0\n0,0,0','adjacency',weighted=True)
        self.assertEqual((real.order,real.size),(3,1))
        directed=parse_graph('0 1\n0 0','adjacency',directed=True)
        self.assertTrue(directed.directed);self.assertEqual(directed.edges[0]['vertices'],[0,1])
        complex_graph=parse_graph('[[0,{"real":0,"imag":2}],[{"real":0,"imag":-2},0]]','adjacency',weighted=True)
        self.assertEqual(complex_graph.edges[0]['weight'],{'real':0,'imag':2})
        for text in ('0 1\n0 0','1 0\n0 0','0 2\n2 0'):
            with self.assertRaises(GraphInputError):parse_graph(text,'adjacency')

    def test_graph6_roundtrip_preserves_isolates_and_bounds_before_decode(self):
        graph=nx.path_graph(4);graph.add_node(4);encoded=nx.to_graph6_bytes(graph,header=True).decode().strip()
        parsed=parse_graph(encoded,'graph6',vertices_text='a b c d isolated')
        self.assertEqual(parsed.order,5);self.assertEqual(parsed.edges[-1]['vertices'],['c','d'])
        with patch('networkx.from_graph6_bytes',side_effect=AssertionError('large allocation must not be reached')):
            with self.assertRaises(GraphInputError):parse_graph('~???'+'?'*4,'graph6')
        with self.assertRaises(GraphInputError):parse_graph('Bg\nBg','graph6')
        with self.assertRaises(GraphInputError):parse_graph('中文','graph6')

    def test_structured_json_flags_positions_and_legacy_specs(self):
        source=parse_graph('a b | {"real":0,"imag":1}',weighted=True,directed=True).with_updates(positions=[[0,0],[2,1]])
        restored=parse_graph(source._serialized,'json','hypergraph',directed=False,weighted=False)
        self.assertEqual(source,restored)
        self.assertEqual(parse_graph('{"kind":"path","n":4}','json').order,4)
        self.assertEqual(parse_graph('{"edges":[[1,2]],"vertices":[1,2,3]}','json').order,3)
        with self.assertRaises(GraphInputError):parse_graph('{"edges":[true]}','json')
        with self.assertRaises(GraphInputError):strict_json('{"edges":[],"edges":[]}')

    def test_existing_layout_json_import_keeps_typed_labels_and_coordinates(self):
        layout={'format':'graph-research-layout','version':1,'vertices':[1,'1','isolated'],'edges':[[0,1]],'weights':[2],
                'positions':[[10000000,0],[10000002,1],[10000004,2]]}
        graph=parse_graph(json.dumps(layout),'json')
        self.assertEqual(graph.vertices,(1,'1','isolated'));self.assertTrue(graph.weighted)
        self.assertEqual(graph.to_dict()['positions'],layout['positions']);self.assertEqual(graph.edges[0]['weight'],2)

    def test_line_errors_duplicate_edges_unknown_labels_and_no_execution(self):
        for text,number in [('a b\n\nb a',3),('a a',1),('a b c',1),('a "unclosed',1),('a b | 2',1)]:
            with self.subTest(text=text):
                with self.assertRaises(GraphInputError) as raised:parse_graph(text)
                self.assertEqual(raised.exception.line,number)
        with self.assertRaisesRegex(GraphInputError,'完整顶点'):parse_graph('a b',vertices_text='a isolated')
        with self.assertRaises(GraphInputError):parse_graph('a b | "__import__(1)"',weighted=True)
        with patch('subprocess.run',side_effect=AssertionError('must not execute')):
            graph=parse_graph('__import__(os) node')
            self.assertEqual(graph.vertices[0],'__import__(os)')

    def test_document_rejects_invalid_flags_weights_and_coordinates(self):
        base=parse_graph('a b').to_dict()
        for update in ({'directed':1},{'vertices':[True,'b']},{'vertices':['a','a']},{'positions':[[0,0],[0,0]]},{'unknown':'instruction'},{'weighted':True,'edges':[{'vertices':['a','b'],'weight':float('nan')}]}):
            with self.subTest(update=update),self.assertRaises(GraphInputError):GraphDocument({**base,**update})
        with self.assertRaises(GraphInputError):parse_graph('a b | -1',graph_type='hypergraph',weighted=True)
        with self.assertRaises(GraphInputError):parse_graph('a b',graph_type='hypergraph',directed=True)

    def test_families_match_independent_order_size_and_hypergraph_rank(self):
        self.assertEqual((graph_family('graph','complete',n=5).order,graph_family('graph','complete',n=5).size),(5,10))
        h=graph_family('hypergraph','path',m=3,k=4)
        self.assertEqual((h.order,h.size),(10,3));self.assertTrue(all(len(e['vertices'])==4 for e in h.edges))


class InputAdapterTests(unittest.TestCase):
    def setUp(self):self.registry=ToolRegistry()
    def definition(self,name):return self.registry.describe(name)

    def test_null_graph_is_rejected_before_networkx_pointless_concept(self):
        from graph_research.tools.registry import graph_invariants
        with self.assertRaisesRegex(ValueError,'at least one vertex'):
            graph_invariants('empty',0)

    def test_unknown_tool_raises_tool_not_found_not_keyerror(self):
        from graph_research.assistant.task_contract import TaskProtocolError
        with self.assertRaises(TaskProtocolError) as caught:
            self.registry.call('bogus_tool_name',{})
        self.assertEqual(caught.exception.code,'tool_not_found')

    def test_simple_graph_mapping_and_spectrum_keep_full_order(self):
        graph=parse_graph('b a\na c',vertices_text='c b a isolated')
        prepared=graph_patch(graph,self.definition('graph_spectrum'))
        self.assertEqual(prepared['patch'],{'kind':'edges','n':4,'edges':[[1,2],[2,0]]})
        result=self.registry.call('graph_spectrum',prepared['patch']);self.assertAlmostEqual(result['rho'],2**.5)
        self.assertEqual(prepared['vertex_mapping'][0],{'index':0,'label':'c'})

    def test_repeated_and_reversed_edges_are_rejected_not_merged(self):
        for edges in ([[0,1],[0,1]],[[0,1],[1,0]],[[0,1],[1,2],[0,1]]):
            with self.subTest(edges=edges),self.assertRaisesRegex(ValueError,'Duplicate edge'):
                self.registry.call('graph_spectrum',{'kind':'edges','n':3,'edges':edges})
            with self.subTest(edges=edges),self.assertRaisesRegex(ValueError,'Duplicate edge'):
                self.registry.call('graph_invariants',{'kind':'edges','n':3,'edges':edges})
        self.assertEqual(self.registry.call('graph_invariants',{'kind':'edges','n':3,'edges':[[0,1],[1,2]]})['size'],2)

    def test_rho_is_taken_from_the_same_decomposition_as_the_spectrum(self):
        for arguments in ({'kind':'path','n':5},{'kind':'complete','n':128},{'kind':'cycle','n':7,'matrix':'L'},
                          {'kind':'path','n':5,'matrix':'D'},{'kind':'star','n':6,'alpha':0.5,'matrix':'alpha'}):
            with self.subTest(arguments=arguments):
                result=self.registry.call('graph_spectrum',arguments)
                self.assertEqual(result['rho'],result['spectrum'][0])
        seidel=self.registry.call('graph_spectrum',{'kind':'path','n':5,'matrix':'S'})
        self.assertAlmostEqual(seidel['rho'],max(abs(v) for v in seidel['spectrum']),places=12)

    def test_reject_direction_weights_and_hypergraph_isolate_loss(self):
        for graph in (parse_graph('a b',directed=True),parse_graph('a b | 2',weighted=True),parse_graph('a b c',graph_type='hypergraph')):
            with self.assertRaises(GraphInputError):graph_patch(graph,self.definition('graph_spectrum'))
        h=parse_graph('a b c',graph_type='hypergraph',vertices_text='a b c isolated')
        for tool in ('hypergraph_transform','hypergraph_spectrum','hypergraph_structure'):
            with self.assertRaisesRegex(GraphInputError,'孤立点'):graph_patch(h,self.definition(tool))
        self.assertEqual(graph_patch(h,self.definition('hypergraph_tensor_charpoly'))['patch']['n'],4)

    def test_drawing_preserves_labels_positions_and_weighted_route(self):
        graph=parse_graph('1 "1"',vertices_text='1 "1" isolated').with_updates(positions=[[0,0],[1,1],[2,0]])
        prepared=graph_patch(graph,self.definition('graph_tikz'))
        self.assertEqual(prepared['patch']['vertices'],[1,'1','isolated']);self.assertEqual(prepared['vertex_mapping'],[])
        weighted=parse_graph('a b | {"real":0,"imag":2}',weighted=True)
        result=self.registry.call('weighted_graph_spectrum',graph_patch(weighted,self.definition('weighted_graph_spectrum'))['patch'])
        self.assertEqual(result['rho'],2)
        self.assertEqual(graph_patch(weighted,self.definition('hypergraph_plot'))['patch']['graph_document'],weighted.to_dict())

    def test_comparison_recipe_and_batch_roles_and_source_validation(self):
        graph=parse_graph('a b')
        self.assertEqual(graph_targets(self.definition('compare_graphs')),['left','right'])
        self.assertEqual(graph_patch(graph,self.definition('compare_graphs'),'right')['patch']['right']['n'],2)
        base=graph_patch(graph,self.definition('graph_recipe'),'base')['patch'];self.assertEqual(base['graph_type'],'graph')
        definition=self.definition('graph_batch_study');first=binding(graph,definition,'case')
        second_graph=parse_graph('c d\nd e');second=binding(second_graph,definition,'case',first['patch']);args=second['patch']
        sources=bound_inputs({'case0':first,'case1':second},args)
        self.assertEqual(len(sources),2);normalized=validate_bindings(definition,args,sources)
        self.assertEqual(validate_sources(definition,args,normalized),normalized)

    def test_manual_graph_change_excludes_stale_mapping_and_worker_rejects_forgery(self):
        graph=parse_graph('a b');definition=self.definition('graph_invariants');source=binding(graph,definition);args=source['patch']
        self.assertEqual(len(bound_inputs({'graph':source},args)),1)
        self.assertEqual(bound_inputs({'graph':source},{**args,'n':3}),[])
        corrupted=copy.deepcopy(source);corrupted['vertex_mapping'][0]['label']='wrong'
        with self.assertRaises(GraphInputError):validate_bindings(definition,args,[corrupted])
        normalized=validate_bindings(definition,args,[source]);normalized[0]['vertex_mapping'][0]['label']='wrong'
        with self.assertRaises(GraphInputError):validate_sources(definition,args,normalized)

    def test_result_reuse_restores_labels_and_avoids_line_graph_identity_confusion(self):
        graph=parse_graph('a b\nb c');definition=self.definition('graph_edit');source=binding(graph,definition);args={**source['patch'],'operation':'subdivide_edges','edit_edges':[[0,1]],'subdivisions':1}
        observation={'ok':True,'tool':'graph_edit','arguments':args,'result':self.registry.call('graph_edit',args),'graph_inputs':validate_bindings(definition,args,[source])}
        result=result_graph(observation);self.assertEqual(result.order,4);self.assertTrue({'a','b','c'}<=set(result.vertices))
        args={**source['patch'],'operation':'line_graph'};observation.update(arguments=args,result=self.registry.call('graph_edit',args))
        self.assertEqual(set(result_graph(observation).vertices),{0,1})
        with self.assertRaises(GraphInputError):result_graph({'ok':True,'tool':'matrix_analysis','result':{}})

    def test_saved_recipe_is_data_and_survives_layout_but_not_structural_edits(self):
        args={'graph_type':'graph','base':{'kind':'path','n':'t+2'},'parameters':{'t':2},'steps':[{'operation':'attach_star','roots':[0],'count':1}]}
        graph=result_graph({'ok':True,'tool':'graph_recipe','arguments':args,'result':self.registry.call('graph_recipe',args)})
        self.assertEqual(graph.to_dict()['recipe'],args)
        moved=graph.with_updates(positions=[[i,i*i] for i in range(graph.order)])
        self.assertEqual(moved.to_dict()['recipe'],args);self.assertIn('graph_recipe',model_graph_text(moved))
        self.assertNotIn('recipe',moved.with_updates(weighted=True).to_dict())
        self.assertEqual(parse_graph(graph._serialized,'json').to_dict()['recipe'],args)

    def test_drawing_result_keeps_numeric_labels_and_layout_without_remapping_twice(self):
        graph=parse_graph('1 2\n2 3',vertices_text='1 2 3 isolated').with_updates(positions=[[0,0],[1,1],[2,0],[3,2]])
        definition=self.definition('graph_tikz');source=binding(graph,definition);normalized=validate_bindings(definition,source['patch'],[source])
        restored=result_graph({'ok':True,'tool':'graph_tikz','arguments':source['patch'],'result':{},'graph_inputs':normalized})
        self.assertEqual(restored.vertices,graph.vertices);self.assertEqual(restored.to_dict()['positions'],graph.to_dict()['positions'])

    def test_png_svg_plot_uses_exact_saved_positions_instead_of_relayout(self):
        graph=parse_graph('a b c\nc d',graph_type='hypergraph',vertices_text='a b c d isolated').with_updates(positions=[[0,0],[2,0],[1,2],[3,2],[4,4]])
        args=graph_patch(graph,self.definition('hypergraph_plot'))['patch']
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            result=self.registry.call('hypergraph_plot',args)
        self.assertEqual(result['positions'],[{'vertex':v,'xy':xy} for v,xy in zip(graph.vertices,graph.to_dict()['positions'])])


class GraphLibraryAndEvidenceTests(unittest.TestCase):
    def test_library_snapshots_names_paths_and_corrupt_files(self):
        graph=parse_graph('a b').with_updates(positions=[[0,0],[2,1]])
        with tempfile.TemporaryDirectory() as directory:
            library=GraphLibrary(Path(directory)/'library');identifier=library.save(graph,'../../图名')
            loaded=library.load(identifier);self.assertEqual(loaded.name,'../../图名');self.assertEqual(loaded.to_dict()['positions'],[[0,0],[2,1]])
            library.set_current(graph);self.assertEqual(library.current(),graph)
            with self.assertRaises(GraphInputError):library.load('../../escape')
            (library.directory/'objects'/(identifier+'.json')).write_text('broken',encoding='utf-8')
            self.assertFalse(library.entries()[0]['valid']);self.assertTrue((library.directory/'objects'/(identifier+'.json')).exists())
            exported=library.export(graph,Path(directory)/'copy.json');self.assertEqual(parse_graph(exported.read_text(encoding='utf-8'),'json'),graph)

    def test_original_input_is_bound_to_receipt_and_exported_with_result(self):
        from graph_research.assistant import OfflineToolSession,verify_bundle
        from graph_research.runtime.runner import run_tool
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session=OfflineToolSession(root/'session',root/'tools');definition=ToolRegistry().describe('graph_invariants')
            graph=parse_graph('a b',vertices_text='a b isolated');source=binding(graph,definition)
            observation=session.call_tool('graph_invariants',source['patch'],graph_inputs=[source])
            self.assertTrue(observation['ok']);self.assertEqual(observation['graph_inputs'][0]['document']['vertices'],['a','b','isolated'])
            self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])
            with zipfile.ZipFile(session.result_bundle['archive']) as bundle:
                self.assertTrue(any(name.endswith('/graph-inputs.json') for name in bundle.namelist()))
                self.assertIn('输入图与顶点编号对照',bundle.read('report.html').decode('utf-8'))
                name=next(n for n in bundle.namelist() if n.endswith('/input-graph-1.json'))
                self.assertEqual(parse_graph(bundle.read(name).decode(),'json'),graph)
            session.state['observations'][0]['graph_inputs'][0]['vertex_mapping'][0]['label']='tampered'
            with self.assertRaisesRegex(ValueError,'Graph input source'):session.export_results()
            invalid=copy.deepcopy(observation['graph_inputs']);invalid[0]['vertex_mapping'][0]['label']='tampered'
            with self.assertRaises(RuntimeError):run_tool('graph_invariants',source['patch'],root/'tools',directory=root/'bad',graph_inputs=invalid)


os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt,QPointF
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from graph_research.desktop.graph_input import GraphInputDialog
    from graph_research.desktop.graph_canvas import GraphCanvas
    from graph_research.desktop.app import DesktopWindow
    from graph_research.desktop.service import DesktopWorkspace
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False


@unittest.skipUnless(QT_AVAILABLE,'Optional native desktop unavailable')
class NativeGraphInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.widgets=[]
    def tearDown(self):
        for widget in self.widgets:widget.close();widget.deleteLater()
        self.app.processEvents();self.temp.cleanup()
    def dialog(self,graph=None):
        result=GraphInputDialog(GraphLibrary(self.root/'library'),graph);self.widgets.append(result);return result

    def test_quick_text_preview_line_highlight_and_invalid_input_cannot_apply(self):
        dialog=self.dialog();dialog.text.setPlainText('a b\nb c');dialog.parse_input()
        self.assertEqual(dialog.canvas.current_graph().order,3);self.assertTrue(dialog.use.isEnabled())
        dialog.text.setPlainText('a b\nb a');dialog.parse_input()
        self.assertFalse(dialog.use.isEnabled());self.assertEqual(len(dialog.text.extraSelections()),1);self.assertIn('第2行',dialog.status.text())
        dialog.canvas.vertices[0].setPos(QPointF(240,240));dialog._canvas_changed(dialog.canvas.current_graph())
        self.assertFalse(dialog.use.isEnabled());self.assertEqual(dialog.summary.textFormat(),Qt.TextFormat.PlainText)

    def test_format_zero_index_triggers_revalidation_and_undo_restores_flags(self):
        dialog=self.dialog();dialog.format.setCurrentIndex(dialog.format.findData('json'));dialog.text.setPlainText(parse_graph('a b')._serialized);dialog.parse_input()
        self.assertTrue(dialog.use.isEnabled());dialog.format.setCurrentIndex(0);self.assertFalse(dialog.use.isEnabled());dialog.parse_input();self.assertFalse(dialog.use.isEnabled())
        dialog=self.dialog(parse_graph('a b'));dialog.tabs.setCurrentIndex(3);dialog.directed.setChecked(True);self.assertTrue(dialog.prepared_graph().directed)
        dialog.canvas.undo();self.assertFalse(dialog.prepared_graph().directed);self.assertFalse(dialog.directed.isChecked())
        for combo in (dialog.format,dialog.family,dialog.graph_type,dialog.canvas.mode):
            for i in range(combo.count()):
                self.assertTrue(combo.itemData(i,Qt.ItemDataRole.ToolTipRole));combo.setCurrentIndex(i)
                self.assertEqual(combo.toolTip(),combo.itemData(i,Qt.ItemDataRole.ToolTipRole))

    def test_graph_canvas_add_connect_hyperedge_delete_undo_and_live_curves(self):
        dialog=self.dialog();dialog.tabs.setCurrentIndex(3);canvas=dialog.canvas
        canvas.add_vertex('a',[0,0]);canvas.add_vertex('b',[1,0]);canvas.add_vertex('c',[.5,1]);canvas.add_edge(['a','b'])
        self.assertEqual(canvas.current_graph().size,1);canvas.remove_vertex('a');self.assertEqual(canvas.current_graph().size,0);canvas.undo();self.assertEqual(canvas.current_graph().size,1)
        h=parse_graph('a b c',graph_type='hypergraph');canvas.set_graph(h);before=canvas.paths[0].path().boundingRect()
        canvas.vertices[0].setPos(canvas.vertices[0].pos()+QPointF(70,20));self.app.processEvents()
        self.assertNotEqual(canvas.paths[0].path().boundingRect(),before)
        self.assertEqual(canvas.current_graph().edges,h.edges)

    def test_real_mouse_vertex_and_edge_creation(self):
        dialog=self.dialog();dialog.tabs.setCurrentIndex(3);dialog.show();self.app.processEvents();canvas=dialog.canvas
        canvas.mode.setCurrentIndex(canvas.mode.findData('vertex'))
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(QPointF(-70,0)))
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(QPointF(70,0)))
        self.assertEqual(canvas.current_graph().order,2)
        canvas.mode.setCurrentIndex(canvas.mode.findData('edge'))
        for item in list(canvas.vertices):QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(item.pos()))
        self.assertEqual(canvas.current_graph().size,1)

    def delete_canvas(self,graph):
        dialog=self.dialog(graph);dialog.tabs.setCurrentIndex(3);dialog.show();self.app.processEvents()
        canvas=dialog.canvas;canvas.mode.setCurrentIndex(canvas.mode.findData('delete'));return canvas

    def click_vertex(self,canvas,index):
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(canvas.vertices[index].pos()))

    def edge_point(self,canvas,index):
        for percent in (.5,.3,.7,.2,.8,.4,.6):
            point=canvas.view.mapFromScene(canvas.paths[index].path().pointAtPercent(percent));item=canvas.view.itemAt(point)
            while item is not None and item.data(0) is None:item=item.parentItem()
            if item is not None and item.data(0)==('edge',index):return point
        self.fail('No unobscured edge point in the test drawing')

    def test_delete_vertex_first_click_previews_all_incident_edges_second_click_commits_and_undo_restores(self):
        graph=parse_graph('a b\nb c\nc d').with_updates(positions=[[0,0],[2,0],[2,2],[4,2]],recipe={'base':{'kind':'path','n':4}})
        canvas=self.delete_canvas(graph);before=canvas.current_graph();changed=[];canvas.changed.connect(changed.append)
        self.click_vertex(canvas,1)
        self.assertEqual(canvas.current_graph(),before);self.assertFalse(changed);self.assertFalse(canvas.undo_stack)
        self.assertEqual(canvas.vertices[1].brush().color().name(),'#c33d35')
        self.assertEqual([p.pen().style() for p in canvas.paths],[Qt.PenStyle.DashLine,Qt.PenStyle.DashLine,Qt.PenStyle.SolidLine])
        self.assertIn('2 条关联边',canvas.selection_text.text());self.assertIn('再次点击',canvas.mode.toolTip())
        self.click_vertex(canvas,1)
        self.assertEqual(canvas.current_graph().vertices,('a','c','d'));self.assertEqual(canvas.current_graph().size,1)
        self.assertEqual(len(changed),1);self.assertEqual(len(canvas.undo_stack),1);self.assertIsNone(canvas._delete_target)
        self.assertNotIn('recipe',canvas.current_graph().to_dict());canvas.undo();self.assertEqual(canvas.current_graph(),before)

    def test_delete_hyperedge_previews_only_that_edge_and_keeps_all_vertices(self):
        graph=parse_graph('a b c\nc d e',graph_type='hypergraph').with_updates(positions=[[0,0],[1,1],[2,0],[3,1],[4,0]])
        canvas=self.delete_canvas(graph);before=canvas.current_graph();point=self.edge_point(canvas,0)
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(canvas.current_graph(),before);self.assertEqual(canvas._delete_target,('edge',0))
        self.assertEqual(canvas.paths[0].pen().style(),Qt.PenStyle.DashLine);self.assertEqual(canvas.paths[1].pen().style(),Qt.PenStyle.SolidLine)
        self.assertTrue(all(v.brush().color().name()=='#173d3b' for v in canvas.vertices))
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(canvas.current_graph().vertices,before.vertices);self.assertEqual(canvas.current_graph().edges,[before.edges[1]])
        canvas.undo();self.assertEqual(canvas.current_graph(),before)

    def test_switching_delete_target_blank_escape_mode_and_clear_button_cancel_without_changes(self):
        graph=parse_graph('a b\nb c').with_updates(positions=[[0,0],[2,0],[2,2]])
        canvas=self.delete_canvas(graph);before=canvas.current_graph()
        self.click_vertex(canvas,0);self.click_vertex(canvas,1)
        self.assertEqual(canvas._delete_target,('vertex','b'));self.assertEqual(canvas.current_graph(),before)
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(QPointF(-40,-40)))
        self.assertIsNone(canvas._delete_target)
        self.click_vertex(canvas,0);QTest.keyClick(canvas.view,Qt.Key.Key_Escape);self.assertIsNone(canvas._delete_target)
        self.assertTrue(all(p.pen().style()==Qt.PenStyle.SolidLine for p in canvas.paths))
        self.click_vertex(canvas,0);canvas.clear_selection.click();self.assertIsNone(canvas._delete_target)
        self.click_vertex(canvas,0);canvas.mode.setCurrentIndex(0);self.assertIsNone(canvas._delete_target)
        self.assertEqual(canvas.current_graph(),before);self.assertFalse(canvas.undo_stack)

    def test_directed_weighted_delete_highlight_restores_arrow_and_caption_colors_on_cancel(self):
        graph=parse_graph('a b | 2\nb a | -1',directed=True,weighted=True).with_updates(positions=[[0,0],[2,0]])
        canvas=self.delete_canvas(graph);before=canvas.current_graph();point=self.edge_point(canvas,0)
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(canvas._delete_target,('edge',0));self.assertEqual(canvas.paths[1].pen().style(),Qt.PenStyle.SolidLine)
        self.assertTrue(all(child.brush().color().name()=='#c33d35' for child in canvas.paths[0].childItems()))
        canvas.unselect();self.assertTrue(all(child.brush().color().name()==canvas.paths[0].pen().color().name() for child in canvas.paths[0].childItems()))
        self.assertEqual(canvas.current_graph(),before)
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point);QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(canvas.current_graph().edges,[before.edges[1]]);canvas.undo();self.assertEqual(canvas.current_graph(),before)

    def test_loading_graph_and_undo_cancel_pending_delete_without_consuming_old_history(self):
        canvas=self.delete_canvas(parse_graph('a b').with_updates(positions=[[0,0],[2,0]]))
        canvas.add_vertex('c',[1,2]);before=canvas.current_graph();history=len(canvas.undo_stack)
        self.click_vertex(canvas,0);canvas.undo();self.assertEqual(canvas.current_graph(),before);self.assertEqual(len(canvas.undo_stack),history)
        self.click_vertex(canvas,0);canvas.set_graph(before);self.assertIsNone(canvas._delete_target)
        self.click_vertex(canvas,0);self.assertEqual(canvas.current_graph(),before)

    def test_second_click_delivered_as_double_click_still_confirms_same_target(self):
        canvas=self.delete_canvas(parse_graph('a b').with_updates(positions=[[0,0],[2,0]]))
        self.click_vertex(canvas,0);self.assertEqual(canvas.current_graph().order,2)
        QTest.mouseDClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(canvas.vertices[0].pos()))
        self.assertEqual(canvas.current_graph().vertices,('b',));self.assertEqual(len(canvas.undo_stack),1)

    def test_overlapping_drag_can_recover_and_keeps_new_structure_when_switching_inputs(self):
        dialog=self.dialog(parse_graph('a b').with_updates(positions=[[0,0],[1,0]]));dialog.tabs.setCurrentIndex(3);canvas=dialog.canvas
        canvas._drag_start=canvas.current_graph();canvas.vertices[1].setPos(canvas.vertices[0].pos());canvas._released()
        self.assertFalse(dialog.use.isEnabled())
        canvas.vertices[1].setPos(QPointF(200,0));canvas._released();self.assertTrue(dialog.use.isEnabled())
        canvas.add_vertex('new',[2,2]);canvas._drag_start=canvas.current_graph();canvas.vertices[1].setPos(canvas.vertices[0].pos());canvas._released()
        self.assertFalse(dialog.use.isEnabled());dialog.tabs.setCurrentIndex(0)
        self.assertTrue(dialog.use.isEnabled());self.assertIn('new',dialog.prepared_graph().vertices)

    def test_weighted_directed_canvas_keeps_arrows_and_weights_across_redraws(self):
        graph=parse_graph('a b | 2\nb a | -1',directed=True,weighted=True);dialog=self.dialog(graph);canvas=dialog.canvas
        self.assertEqual(len(canvas.paths[0].childItems()),2)
        for i in range(15):canvas.vertices[0].setPos(canvas.vertices[0].pos()+QPointF(1,1))
        self.assertEqual(len(canvas.paths[0].childItems()),2);self.assertTrue(canvas.current_graph().directed)
        self.assertEqual([edge['weight'] for edge in canvas.current_graph().edges],[2,-1])

    def test_file_formats_and_save_load_preserve_coordinates(self):
        dialog=self.dialog();path=self.root/'edges.csv';path.write_text('a,b\nb,c',encoding='utf-8-sig');dialog.load_file(path,'edge_list')
        self.assertEqual(dialog.prepared_graph().size,2);dialog.tabs.setCurrentIndex(3);dialog.canvas.vertices[0].setPos(QPointF(210,50))
        before=dialog.prepared_graph();dialog.save_graph();identifier=dialog.library.entries()[0]['id'];loaded=dialog.library.load(identifier)
        self.assertEqual(loaded,before)
        dialog.tabs.setCurrentIndex(0);self.assertEqual(dialog.prepared_graph().to_dict()['positions'],before.to_dict()['positions'])
        path.write_text('0 1\n1 0',encoding='utf-8');dialog.vertices.clear();dialog.load_file(path,'adjacency');self.assertEqual(dialog.prepared_graph().vertices,(0,1))

    def test_native_tool_application_partial_comparison_mapping_and_stale_binding(self):
        window=DesktopWindow(DesktopWorkspace(self.root/'work'));self.widgets.append(window);graph=parse_graph('a b\nb c',vertices_text='a b c isolated')
        window.apply_graph(graph);self.assertEqual(window.collect_arguments()['n'],4);self.assertTrue(window.mapping_toggle.isVisibleTo(window))
        window.fields['n'].set_value(5);self.assertEqual(bound_inputs(window.graph_bindings,window.collect_arguments()),[])
        window.select_tool('compare_graphs');window.apply_graph(graph,'left');window.apply_graph(parse_graph('x y'),'right')
        self.assertEqual(window.collect_arguments()['right']['n'],2);self.assertEqual(len(window.graph_bindings),2)

    def test_dialogue_inserts_data_draft_only_and_modes_share_library(self):
        from graph_research.desktop.shell import IntegratedWindow
        shell=IntegratedWindow(DesktopWorkspace(self.root/'both'));self.widgets.append(shell);graph=parse_graph('a b')
        shell.workspace.graph_library.set_current(graph);identifier=shell.workspace.graph_library.save(graph)
        with patch('httpx.Client',side_effect=AssertionError('no network')):
            shell.modes.setCurrentIndex(1);self.assertEqual(shell.chat.workspace.graph_library.load(identifier),graph)
            shell.chat.insert_graph(graph)
        self.assertIn('graph_document',shell.chat.composer.toPlainText());self.assertIn('不是指令',shell.chat.composer.toPlainText())
        self.assertFalse(shell.chat.workspace.session.state);self.assertIsNone(shell.chat.model)

    def test_recipe_preparation_does_not_calculate_and_canvas_edit_invalidates_old_recipe(self):
        recipe={'graph_type':'graph','base':{'kind':'path','n':2}}
        graph=parse_graph('a b').with_updates(recipe=recipe);dialog=self.dialog(graph)
        self.assertTrue(dialog.recipe_button.isVisibleTo(dialog));dialog.prepare_recipe();self.assertTrue(dialog.use_recipe)
        dialog=self.dialog(graph);dialog.tabs.setCurrentIndex(3);dialog.canvas.add_vertex('c',[3,2])
        self.assertNotIn('recipe',dialog.prepared_graph().to_dict());self.assertFalse(dialog.recipe_button.isVisibleTo(dialog))
        invalid=self.dialog(parse_graph('a b').with_updates(recipe={'base':{'kind':'path','n':2}}));invalid.prepare_recipe()
        self.assertFalse(invalid.use_recipe);self.assertIn('配方参数无效',invalid.status.text())


if __name__=='__main__':unittest.main()
