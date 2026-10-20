"""Native result management, background workers and shared desktop preferences."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
    from graph_research.desktop.results_center import ResultsCenter,CleanupPreview,collect_sources
    from graph_research.desktop.service import DesktopWorkspace
    from graph_research.desktop.model_service import ModelWorkspace
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False

from graph_research.assistant.result_catalog import ResultCatalog
from graph_research.assistant.result_cleanup import ResultCleanup
from tests.test_feature_workflow import ScriptedModel


@unittest.skipUnless(QT_AVAILABLE,'Optional Qt desktop dependency unavailable')
class ResultsCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.workspace=ModelWorkspace(self.root/'workspace')
        # Analysis-only session avoids a native worker for UI bookkeeping tests.
        self.workspace.session.ask('路径图研究',ScriptedModel([{'action':'final','answer':'结构分析'}]))
        self.center=ResultsCenter(self.workspace);self.wait();self.addCleanup(self.cleanup)

    def cleanup(self):
        self.wait();self.center.close();self.center.deleteLater();self.app.processEvents();self.temp.cleanup()

    def wait(self):
        end=time.monotonic()+15
        while self.center.thread is not None and time.monotonic()<end:self.app.processEvents();time.sleep(.005)
        self.app.processEvents();self.assertIsNone(self.center.thread,'Result manager worker did not finish')

    def test_filters_selection_pin_and_verified_open(self):
        self.assertEqual(self.center.table.rowCount(),1);self.center.table.selectRow(0)
        self.assertTrue(self.center.open_button.isEnabled());self.assertIn('.zip',self.center.detail.text())
        self.center.toggle_pin();self.wait();self.center.only_pinned.setChecked(True)
        self.assertEqual(self.center.table.rowCount(),1);self.assertEqual(self.center.pin_button.text(),'取消保留')
        self.center.search.setText('不存在的课题');self.assertEqual(self.center.table.rowCount(),0)
        self.center.search.clear();self.center.table.selectRow(0)
        with patch('graph_research.desktop.results_center.QDesktopServices.openUrl',return_value=True) as opened:
            self.center.open_result();self.wait();self.assertEqual(opened.call_count,1)
            self.assertTrue(Path(opened.call_args.args[0].toLocalFile()).is_file())

    def test_snapshot_uses_selected_session_and_new_location_only_applies_to_new_sessions(self):
        original=self.workspace.session;self.workspace.new_session()
        self.center.table.selectRow(0);self.center.snapshot();self.wait()
        catalog=ResultCatalog(original.results_directory)
        self.assertEqual(len(catalog.list_versions(original.session_id)),2)
        selected=self.root/'new-results'
        with patch('graph_research.desktop.results_center.QFileDialog.getExistingDirectory',return_value=str(selected)):
            self.center.choose_directory();self.wait()
        model=ModelWorkspace(self.root/'model',results_preferences=self.workspace.results_preferences)
        self.assertEqual(model.session.results_directory,selected)
        self.workspace.open_session(original.directory);self.assertEqual(self.workspace.session.results_directory,original.results_directory)
        self.workspace.new_session();self.assertEqual(self.workspace.session.results_directory,selected)
        self.assertEqual(len(collect_sources(self.workspace.results_preferences)),1)

    def test_cleanup_preview_cancel_keeps_files_then_recycle_and_restore(self):
        session=self.workspace.session;catalog=ResultCatalog(session.results_directory);cleaner=ResultCleanup(catalog)
        preview=cleaner.preview([session.session_id],'task');result=[{'root':str(catalog.root),'preview':preview}]
        dialog=CleanupPreview(result,'task',self.center)
        self.assertIn('清理',dialog.windowTitle());dialog.close();dialog.deleteLater()
        with patch.object(CleanupPreview,'exec',return_value=QDialog.DialogCode.Rejected):self.center.review_cleanup(result,'task')
        self.assertTrue(Path(session.result_bundle['archive']).is_file())
        preview=cleaner.preview([session.session_id],'task');result=[{'root':str(catalog.root),'preview':preview}]
        with patch.object(CleanupPreview,'exec',return_value=QDialog.DialogCode.Accepted),patch.object(QMessageBox,'information'):
            self.center.review_cleanup(result,'task');self.wait()
        self.assertEqual(self.center.table.rowCount(),0)
        operation=cleaner.list_operations()[0];cleaner.restore(operation['id']);self.center.refresh();self.wait()
        self.assertEqual(self.center.table.rowCount(),1)

    def test_background_failure_leaves_dialog_usable_and_close_waits_for_worker(self):
        def fail():raise ValueError('测试失败说明')
        self.center.start(fail);self.center.reject();self.assertIsNotNone(self.center.thread);self.wait()
        self.assertIn('测试失败说明',self.center.feedback.text());self.assertTrue(self.center.close_button.isEnabled())

    def test_import_remembers_an_existing_managed_root_without_copying_it_again(self):
        from graph_research.assistant import ResearchSession
        other=ResearchSession(self.root/'other-session',results_directory=self.root/'other-results')
        other.ask('外部成果',ScriptedModel([{'action':'final','answer':'分析'}]));archive=Path(other.result_bundle['archive'])
        with patch('graph_research.desktop.results_center.QFileDialog.getExistingDirectory',return_value=str(other.directory)),patch.object(QMessageBox,'information'):
            self.center.import_legacy();self.wait()
        self.assertEqual(self.center.table.rowCount(),2);self.assertTrue(archive.is_file());self.assertEqual(len(list((self.root/'other-results').rglob('*.zip'))),1)


if __name__=='__main__':unittest.main()
