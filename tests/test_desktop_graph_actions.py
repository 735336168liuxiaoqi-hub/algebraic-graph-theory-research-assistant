"""Graph-local desktop workflows, with real protected exports and no model calls."""
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    from graph_research.desktop.app import DesktopWindow
    from graph_research.desktop.service import DesktopWorkspace
    from graph_research.desktop.graph_actions import (GraphActionsDialog,input_graphs,observation_graphs,
        presentation_call,desktop_groups,INTEGRATED)
    AVAILABLE=True
except ImportError:AVAILABLE=False

from graph_research.graph_input.document import document
from graph_research.graph_input.adapters import validate_bindings
from graph_research.tools.registry import ToolRegistry


@unittest.skipUnless(AVAILABLE,'Optional desktop dependencies unavailable')
class GraphContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
        cls.registry=ToolRegistry()

    def graph(self,hyper=False):
        return document([1,'1','a','孤立点'],[{'vertices':[1,'1','a'] if hyper else [1,'1']}],
            graph_type='hypergraph' if hyper else 'graph',positions=[[0,0],[1,1],[2,0],[3,1]])

    def test_navigation_changes_only_desktop_and_retains_backend_tools(self):
        from graph_research.assistant.offline import grouped_tools
        groups=grouped_tools(self.registry);before=copy.deepcopy(groups);shown=desktop_groups(groups)
        names={d['name'] for g in shown for d in g['tools']}
        self.assertEqual(len(names),37);self.assertFalse(names & INTEGRATED);self.assertEqual(groups,before)
        self.assertEqual(len(self.registry.tools),43);self.assertTrue(INTEGRATED<=self.registry.tools.keys())
        self.assertIn('绘图、布局与LaTeX',[g['name'] for g in groups]);self.assertNotIn('绘图、布局与LaTeX',[g['name'] for g in shown])

    def test_numeric_simple_graph_recovery_defaults_and_isolated_vertices(self):
        for args in ({},{'kind':'edges','n':5,'edges':[[0,1]]}):
            graphs=input_graphs(self.registry.describe('graph_invariants'),args)
            graph=graphs[0][1];self.assertEqual(graph.order,5)
            self.assertEqual(graph.size,1 if args else 4)
        self.assertFalse(input_graphs(self.registry.describe('graph_enumeration'),{'operation':'degree_realizations','degrees':[1,1]}))

    def test_verified_sources_keep_labels_positions_and_reject_stale_sources(self):
        from graph_research.graph_input.adapters import graph_patch
        source=self.graph();definition=self.registry.describe('graph_invariants');prepared=graph_patch(source,definition)
        binding={k:prepared[k] for k in ('target','patch','vertex_mapping')};binding['document']=source.to_dict()
        args=prepared['patch'];sources=validate_bindings(definition,args,[binding])
        graph=input_graphs(definition,args,sources)[0][1];self.assertEqual(graph.to_dict(),source.to_dict())
        with self.assertRaises(ValueError):input_graphs(definition,{**args,'edges':[[1,2]]},sources)

    def test_transformed_graph_and_constructed_graph_are_actual_results(self):
        args={'kind':'path','n':4,'operation':'complement'}
        data=self.registry.call('graph_edit',args)
        graph=observation_graphs({'ok':True,'tool':'graph_edit','arguments':args,'result':data},self.registry)[0][1]
        self.assertEqual({frozenset(e['vertices']) for e in graph.edges},{frozenset(e) for e in data['edges']})
        self.assertNotIn(frozenset([0,1]),{frozenset(e['vertices']) for e in graph.edges})
        args={'family':'theta','lengths':[2,2,2]};data=self.registry.call('graph_construction',args)
        graph=observation_graphs({'ok':True,'tool':'graph_construction','arguments':args,'result':data},self.registry)[0][1]
        self.assertEqual((graph.order,graph.size),(data['order'],data['size']))
        with self.assertRaises((ValueError,KeyError)):
            observation_graphs({'ok':True,'tool':'graph_edit','arguments':{'n':5},'result':{}},self.registry)

    def test_paired_inputs_are_explicit_and_failures_symbolic_scenes_are_not_graphs(self):
        args={'left':{'kind':'path','n':4},'right':{'kind':'cycle','n':3}}
        graphs=input_graphs(self.registry.describe('compare_graphs'),args)
        self.assertEqual([g.order for _,g in graphs],[4,3]);self.assertEqual([t for t,_ in graphs],['左侧图','右侧图'])
        self.assertFalse(observation_graphs({'ok':False,'tool':'graph_invariants','arguments':{}},self.registry))
        with self.assertRaises(ValueError):observation_graphs({'ok':True,'tool':'hypergraph_schematic','arguments':{'operation':'export'},'result':{}},self.registry)

    def test_nonuniform_hypergraph_and_numeric_input_keep_type(self):
        args={'edges':[[0,1],[1,2,3]],'operation':'incidence'}
        graph=input_graphs(self.registry.describe('hypergraph_structure'),args)[0][1]
        self.assertEqual(graph.graph_type,'hypergraph');self.assertEqual([len(e['vertices']) for e in graph.edges],[2,3])

    def test_dialog_drag_export_and_switch_preserve_typed_vertices_without_mutating_input(self):
        source=self.graph();before=source.to_dict();dialog=GraphActionsDialog([('甲',source),('乙',self.graph(True))],self.registry)
        try:
            dialog.canvas.vertices[0].setPos(dialog.canvas.vertices[0].pos()+QPointF(32,16))
            position=dialog.canvas.current_graph().to_dict()['positions'][0]
            dialog.choice.setCurrentIndex(1);dialog.choice.setCurrentIndex(0)
            self.assertEqual(dialog.canvas.current_graph().to_dict()['positions'][0],position)
            dialog.prepare('tex');name,args,bindings=dialog.request
            self.assertEqual(name,'graph_tikz');self.assertEqual(args['vertices'],[1,'1','a','孤立点'])
            self.assertEqual(args['positions'][0]['xy'],position)
            self.assertEqual(source.to_dict(),before);validate_bindings(self.registry.describe(name),args,bindings)
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_direction_and_weights_are_visible_and_exports_are_enabled(self):
        source=document(['a','b','c'],[{'vertices':['a','b'],'weight':2}],directed=True,weighted=True)
        dialog=GraphActionsDialog([('有向带权图',source)],self.registry)
        try:
            self.assertTrue(dialog.canvas.current_graph().directed);self.assertEqual(dialog.canvas.current_graph().edges[0]['weight'],2)
            self.assertTrue(dialog.draw_button.isEnabled());self.assertTrue(dialog.tex_button.isEnabled());self.assertTrue(dialog.auto_button.isEnabled())
            dialog.prepare('tex');name,args,_=dialog.request
            self.assertEqual(name,'graph_tikz');self.assertTrue(args['graph_document']['directed']);self.assertEqual(args['graph_document']['edges'][0]['weight'],2)
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_automatic_layout_reuses_all_operations_and_rejects_structure_overrides(self):
        dialog=GraphActionsDialog([('图',self.graph())],self.registry)
        try:
            field=dialog.option_fields['layout']['operation'];field.set_value('transform')
            dialog.option_fields['layout']['angle'].set_value(90);dialog.prepare('layout')
            name,args,bindings=dialog.request;self.assertEqual(name,'graph_layout');self.assertEqual(args['angle'],90)
            self.assertEqual(args['n'],4);self.assertEqual(len(args['positions']),4);validate_bindings(self.registry.describe(name),args,bindings)
            self.assertEqual(field.editor.count(),7)
            with self.assertRaises(ValueError):presentation_call(self.graph(),self.registry.describe('hypergraph_plot'),{'edges':[[0,1]]})
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_coordinate_save_roundtrip_contains_structure_and_current_positions(self):
        from graph_research.graph_input import parse_graph
        dialog=GraphActionsDialog([('图',self.graph())],self.registry)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'coords.json'
                with patch('graph_research.desktop.graph_actions.QFileDialog.getSaveFileName',return_value=(str(path),'')):dialog.save_graph()
                restored=parse_graph(path.read_text(encoding='utf-8'),'json')
                self.assertEqual(restored.to_dict(),dialog.canvas.current_graph().to_dict())
        finally:dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_protected_png_and_tex_exports_keep_original_math_form_and_record_in_same_session(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace=DesktopWorkspace(Path(directory)/'workspace');window=DesktopWindow(workspace)
            try:
                window.fields['n'].set_value(6);original=window.collect_arguments()
                # Viewing numerical results is immediate and does not execute an extra tool.
                record={'ok':True,'tool':'graph_invariants','arguments':{'kind':'path','n':4},'result':{'order':4,'size':3}}
                window.show_observation(record);self.assertTrue(window.result_drawing_button.isEnabled());window.preview_result_graph()
                self.assertEqual(window.result_canvas.graph.order,4);self.assertFalse(workspace.history())
                for v in window.result_canvas.vertices:self.assertFalse(v.flags() & v.GraphicsItemFlag.ItemIsMovable)
                source=self.graph()
                for name in ('hypergraph_plot','graph_tikz'):
                    window._dispatch_graph_call(presentation_call(source,workspace.registry.describe(name)))
                    self.assertFalse(window.input_drawing_button.isEnabled());deadline=time.monotonic()+30
                    while window.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
                    self.assertIsNone(window.thread);self.assertTrue(window.observation['ok'],window.observation)
                    self.assertEqual(window.current_tool,'graph_invariants');self.assertEqual(window.collect_arguments(),original)
                    self.assertEqual(window._result_graphs()[0][1].vertices,source.vertices)
                    self.assertTrue(workspace.artifacts(window.observation));self.assertTrue(window.result_drawing_button.isEnabled())
                    if name=='hypergraph_plot':self.assertEqual(window.result_title.text(),'普通图结构图')
                self.assertEqual(len(workspace.history()),2);self.assertEqual(workspace.session.task_context['model_calls'],0)
            finally:
                if window.thread is not None:window.cancel_calculation();window.thread.quit();window.thread.wait(30000)
                window.close();window.deleteLater();self.app.processEvents()

    def test_current_input_entry_uses_form_and_not_unrelated_library_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace=DesktopWorkspace(Path(directory)/'workspace');window=DesktopWindow(workspace)
            try:
                workspace.graph_library.set_current(self.graph(True));window.fields['n'].set_value(6)
                with patch.object(window,'open_graph_actions') as opened:window.open_input_drawing()
                graph=opened.call_args.args[0][0][1];self.assertEqual(graph.graph_type,'graph');self.assertEqual(graph.order,6)
            finally:window.close();window.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
