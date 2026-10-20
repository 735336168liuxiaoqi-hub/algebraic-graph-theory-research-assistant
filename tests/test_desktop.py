"""Native desktop forms, worker lifecycle, durable results and layout geometry."""
import json
import os
from pathlib import Path
import tempfile
from threading import Event
import time
import subprocess
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import QPointF,Qt
    from PySide6.QtWidgets import QApplication,QMessageBox
    from graph_research.desktop.app import DesktopWindow,STYLE
    from graph_research.desktop.layout import LayoutDialog
    from graph_research.desktop.service import DesktopWorkspace
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False

from graph_research.assistant import verify_bundle
from graph_research.assistant.offline import OfflineToolSession
from graph_research.runtime.integrity import CORE,verify


@unittest.skipUnless(QT_AVAILABLE,'Optional PySide6 desktop dependency is unavailable')
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=QApplication.instance() or QApplication([])
        cls.application.setQuitOnLastWindowClosed(False);cls.application.setStyleSheet(STYLE)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.workspace=DesktopWorkspace(self.root/'workspace');self.window=DesktopWindow(self.workspace)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.window.thread is not None:
            self.window.cancel_calculation();self.wait()
        self.window.close();self.application.processEvents();self.window.deleteLater();self.application.processEvents();self.temp.cleanup()

    def wait(self,timeout=25):
        deadline=time.monotonic()+timeout
        while self.window.thread is not None and time.monotonic()<deadline:
            self.application.processEvents();time.sleep(.01)
        self.assertIsNone(self.window.thread,'Desktop worker did not finish/cancel within the bounded wait')
        self.application.processEvents()

    def test_all_visible_native_tool_examples_fit_the_native_forms(self):
        for name in self.window.items:
            with self.subTest(tool=name):
                self.window.select_tool(name);self.window.apply_example();arguments=self.window.collect_arguments()
                import jsonschema
                jsonschema.validate(arguments,self.workspace.registry.tools[name].parameters)
                self.application.processEvents()
        self.assertEqual(len(self.window.items),37)

    def test_drawing_menu_integrates_layout_and_legacy_selection_routes_to_structure_plot(self):
        self.assertNotIn('hypergraph_editor',self.window.items)
        from graph_research.desktop.graph_actions import INTEGRATED
        self.assertFalse(INTEGRATED & self.window.items.keys())
        self.assertEqual(self.window.items['combinatorial_plot'].parent().text(0),'组合与多项式')
        self.assertTrue(INTEGRATED <= self.workspace.registry.tools.keys())
        self.window.select_tool('hypergraph_editor');self.assertEqual(self.window.current_tool,'hypergraph_plot')

    def test_simple_graph_layout_keeps_given_positions_updates_segments_and_resets_exactly(self):
        vertices=[1,'1','a','isolated'];positions=[{'vertex':v,'xy':[i*2.,i*i*1.5]} for i,v in enumerate(vertices)]
        dialog=LayoutDialog({'edges':[[1,'1'],['1','a']],'vertices':vertices,'positions':positions})
        try:
            self.assertTrue(dialog.simple);initial=dialog.current_document()
            self.assertEqual(initial['positions'],[p['xy'] for p in positions])
            before=dialog.paths[0].path().elementAt(0);dialog.vertices[0].setPos(dialog.vertices[0].pos()+QPointF(30,40))
            after=dialog.paths[0].path().elementAt(0);self.assertNotEqual((before.x,before.y),(after.x,after.y))
            self.assertTrue(all(path.path().elementCount()==2 for path in dialog.paths))
            self.assertTrue(all(path.pen().color().name()=='#000000' for path in dialog.paths))
            exported=[];dialog.positions_ready.connect(exported.append);dialog.use_positions()
            with patch.object(self.window,'_dispatch_graph_call') as dispatch:self.window.use_layout(exported[0])
            name,arguments,_=dispatch.call_args.args[0]
            self.assertEqual(name,'graph_tikz');self.assertEqual(arguments['vertices'],vertices)
            self.assertEqual(len(arguments['positions']),4);self.assertEqual(self.window.current_tool,'graph_invariants')
            dialog.reset();self.assertEqual(dialog.current_document(),initial)
        finally:dialog.close();dialog.deleteLater();self.application.processEvents()

    def test_open_layout_uses_positions_returned_by_plot_instead_of_regenerating_them(self):
        original={'edges':[['a','b']],'vertices':['a','b','isolated']}
        positions=[{'vertex':'a','xy':[-3,4]},{'vertex':'b','xy':[1,2]},{'vertex':'isolated','xy':[7,8]}]
        self.window.observation={'tool':'hypergraph_plot','arguments':original,'result':{'positions':positions}}
        with patch('graph_research.desktop.layout.LayoutDialog') as dialog:
            self.window.open_layout()
            arguments=dialog.call_args.args[0]
        self.assertEqual(arguments['positions'],positions);self.assertNotIn('positions',original)

    def test_async_calculation_and_history_work_without_browser_or_model(self):
        self.window.select_tool('graph_invariants');self.window.apply_example();self.window.fields['n'].set_value(4)
        with patch('webbrowser.open',side_effect=AssertionError('No browser')):
            self.window.start_calculation();self.assertIsNotNone(self.window.thread)
            self.assertFalse(self.window.compute.isEnabled());self.wait()
        self.assertTrue(self.window.observation['ok']);self.assertEqual(self.window.observation['result']['diameter'],3)
        self.assertEqual(self.window.recent.count(),1);self.assertTrue(self.window.compute.isEnabled())
        self.assertTrue(verify_bundle(self.workspace.session.result_bundle['archive'],self.workspace.session.result_bundle['sha256'])['ok'])

    def test_cancel_before_worker_starts_is_not_lost_and_preserves_results(self):
        self.workspace.session.call_tool('graph_invariants',{'n':3})
        self.window.apply_example()
        with patch('graph_research.assistant.offline.run_tool',side_effect=AssertionError('Early cancellation must not start a worker')):
            self.window.start_calculation();self.window.cancel_calculation();self.wait()
        records=self.workspace.history();self.assertEqual(len(records),2)
        self.assertTrue(records[0]['ok'],str(records)[:800]);self.assertFalse(records[1]['ok'])
        self.assertEqual(self.workspace.session.state['status'],'cancelled')

    def test_close_during_calculation_cancels_and_cleans_up_thread(self):
        self.window.show();self.window.apply_example();self.window.start_calculation();self.window.close();self.wait()
        self.assertTrue(self.window.close_after);self.assertFalse(self.window.isVisible())

    def test_invalid_parameters_do_not_start_calculation(self):
        self.window.fields['n'].set_value(0)
        with patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Ok):self.window.start_calculation()
        self.assertIsNone(self.window.thread);self.assertFalse(self.workspace.history())

    def test_parameter_drafts_survive_switching_tools_and_json_input_is_validated(self):
        self.window.fields['n'].set_value(7);self.window.select_tool('matrix_analysis');self.window.select_tool('graph_invariants')
        self.assertEqual(self.window.collect_arguments()['n'],7)
        self.window.input_tabs.setCurrentIndex(1);self.window.json_editor.setPlainText('{"kind":"path","n":4}')
        self.assertEqual(self.window.collect_arguments(),{'kind':'path','n':4})
        self.window.json_editor.setPlainText('{"n":2,"n":4}')
        with self.assertRaises(ValueError):self.window.collect_arguments()

    def test_new_session_clears_old_visible_results_and_previous_session_can_reopen(self):
        result=self.workspace.session.call_tool('graph_invariants',{'n':3});self.window.show_observation(result)
        previous=self.workspace.session.directory;self.window.new_session()
        self.assertIsNone(self.window.observation);self.assertEqual(self.window.raw.toPlainText(),'')
        self.assertEqual(self.window.recent.count(),0)
        self.workspace.open_session(previous);self.assertEqual(self.workspace.history()[0]['result']['diameter'],2)

    def test_workspace_restart_and_export_preserve_verified_results(self):
        record=self.workspace.session.call_tool('graph_invariants',{'n':3});directory=self.workspace.session.directory
        reloaded=DesktopWorkspace(self.workspace.directory)
        self.assertEqual(reloaded.session.directory,directory);self.assertEqual(len(reloaded.history()),1)
        output=reloaded.export_bundle(self.root/'delivered.zip');self.assertTrue(verify_bundle(output)['ok'])
        saved=reloaded.save_record(record,self.root/'result.json');self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['result']['diameter'],2)
        with self.assertRaises(PermissionError):reloaded.save_record(record,CORE/'desktop-must-not-write.json')
        self.assertTrue(verify()['ok'])

    def test_native_matrix_view_and_attached_image_validate_before_display(self):
        record=self.workspace.session.call_tool('matrix_analysis',{'matrix':[[1,2],[2,1]]});self.window.show_observation(record)
        # Matrix-analysis returns its eigenvalue vector; exact matrix tool returns a matrix.
        matrix=self.workspace.session.call_tool('exact_matrix_operation',{'matrix':[[1,2],[3,4]]})
        self.window.show_observation(matrix);self.assertEqual(self.window.table.rowCount(),2)
        self.assertEqual(self.window.table.columnCount(),2)
        drawn=self.workspace.session.call_tool('hypergraph_plot',{'edges':[[0,1],[1,2,3]]});self.window.show_observation(drawn)
        self.assertFalse(self.window.image.original.isNull());self.assertEqual(self.window.result_tabs.currentIndex(),2)
        file=self.window._files[self.window.file_selector.currentIndex()-1];file.write_bytes(file.read_bytes()+b'changed')
        self.window.show_file(self.window.file_selector.currentIndex());self.assertIsNone(self.window.image.original)

    def test_native_layout_drag_updates_curves_and_preserves_saved_vertex_identity(self):
        dialog=LayoutDialog({'edges':[[0,1,2],[2,3]],'vertices':[0,1,2,3,4]})
        try:
            old=dialog.current_document();before=dialog.paths[0].path().elementAt(0)
            vertex=dialog.vertices[0];vertex.setPos(vertex.pos()+QPointF(40,-25));self.application.processEvents()
            updated=dialog.current_document();after=dialog.paths[0].path().elementAt(0)
            self.assertNotEqual(old['positions'][0],updated['positions'][0]);self.assertNotEqual((before.x,before.y),(after.x,after.y))
            self.assertEqual(updated['vertices'],[0,1,2,3,4]);self.assertEqual(updated['edges'],old['edges'])
            data=[];dialog.positions_ready.connect(data.append);dialog.use_positions()
            self.assertEqual(len(data),1);self.assertEqual(len(data[0]['positions']),5)
            with patch.object(self.window,'_dispatch_graph_call') as dispatch:self.window.use_layout(data[0])
            name,arguments,_=dispatch.call_args.args[0]
            self.assertEqual(name,'hypergraph_tikz');self.assertEqual(len(arguments['positions']),5)
            self.assertEqual(self.window.current_tool,'graph_invariants')
        finally:dialog.close();dialog.deleteLater();self.application.processEvents()

    def test_matrix_preview_keeps_original_values_in_raw_json(self):
        value=1.23456789012345
        fake={'tool':'matrix_analysis','ok':True,'arguments':{},'result':{'matrix':[[value]],'rank':1}}
        self.window.show_observation(fake)
        self.assertIn(repr(value),self.window.raw.toPlainText())
        self.assertIn(repr(value),self.window.table.item(0,0).toolTip())

    def test_native_application_imports_no_browser_engine_model_sdk_or_configuration(self):
        root=Path(__file__).resolve().parents[1]
        code="""
import builtins,sys,os
sys.path.insert(0,ROOT)
os.environ['QT_QPA_PLATFORM']='offscreen'
real=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in ('httpx','langgraph','sage') or name.startswith(('PySide6.QtWebEngine','graph_research.assistant.model')):
        raise AssertionError('Unexpected desktop dependency '+name)
    return real(name,*args,**kwargs)
builtins.__import__=guarded
from PySide6.QtWidgets import QApplication
from graph_research.desktop.app import DesktopWindow
from graph_research.desktop.service import DesktopWorkspace
app=QApplication([])
window=DesktopWindow(DesktopWorkspace(WORKSPACE))
window.apply_example()
assert window.collect_arguments()['n']==3
assert len(window.items)==37
window.close()
app.processEvents()
print('native_desktop_without_browser_or_api_ok')
""".replace('ROOT',repr(str(root))).replace('WORKSPACE',repr(str(self.root/'isolated')))
        result=subprocess.run([sys.executable,'-I','-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('native_desktop_without_browser_or_api_ok',result.stdout)


if __name__=='__main__':unittest.main()
