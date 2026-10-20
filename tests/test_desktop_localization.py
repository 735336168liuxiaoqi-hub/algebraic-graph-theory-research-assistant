"""Complete vocabulary coverage and native tooltip/input behavior without APIs."""
import os
import re
import unittest

from graph_research.desktop.localization import parameter_title,option_presentation
from graph_research.tools import ToolRegistry
from graph_research.tools.input_guides import input_guide
from graph_research.rendering.results import TITLES

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt,QEvent
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QApplication,QToolTip,QComboBox
    from graph_research.desktop.app import ParameterField
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False


class VocabularyTests(unittest.TestCase):
    def test_every_builtin_tool_parameter_and_enum_has_chinese_presentation(self):
        chinese=re.compile(r'[\u4e00-\u9fff]');total=0
        for definition in ToolRegistry().catalog():
            self.assertRegex(TITLES[definition['name']],chinese)
            for parameter,schema in definition['parameters']['properties'].items():
                with self.subTest(tool=definition['name'],parameter=parameter):
                    self.assertRegex(parameter_title(definition,parameter),chinese)
                    for value in schema.get('enum',[]):
                        title,hint=option_presentation(definition,parameter,value)
                        self.assertRegex(title,chinese);self.assertRegex(hint,chinese)
                        self.assertLessEqual(len(hint),220);total+=1
        self.assertGreater(total,100)

    def test_operation_help_reuses_actual_contract_and_power_explains_distance(self):
        definition=ToolRegistry().describe('graph_edit')
        for value,hint in definition['documentation']['operations'].items():
            self.assertEqual(option_presentation(definition,'operation',value)[1],hint)
        title,hint=option_presentation(definition,'operation','power')
        self.assertEqual(title,'图的幂');self.assertIn('最短路距离',hint);self.assertIn('power=2',hint)
        result=ToolRegistry().call('graph_edit',{'operation':'power','kind':'path','n':4,'power':2})
        self.assertEqual({frozenset(edge) for edge in result['edges']},{frozenset(edge) for edge in [(0,1),(1,2),(2,3),(0,2),(1,3)]})

    def test_same_raw_values_have_context_specific_meanings(self):
        registry=ToolRegistry()
        self.assertEqual(option_presentation(registry.describe('graph_spectrum'),'matrix','L')[0],'拉普拉斯矩阵')
        self.assertEqual(option_presentation(registry.describe('hypergraph_tensor_charpoly'),'matrix','L')[0],'拉普拉斯张量')
        self.assertEqual(option_presentation(registry.describe('directed_graph_spectrum'),'matrix','L')[0],'出度拉普拉斯矩阵')
        self.assertEqual(option_presentation(registry.describe('graph_invariants'),'kind','path')[0],'路径图')
        self.assertEqual(option_presentation(registry.describe('generate_hypergraph'),'family','path')[0],'松路')
        self.assertEqual(parameter_title(registry.describe('linear_recurrence'),'start'),'起始下标')
        self.assertEqual(parameter_title(registry.describe('graph_enumeration'),'start'),'起点')

    def test_extension_values_do_not_inherit_unrelated_native_translations(self):
        definition={'name':'custom','documentation':{'coverage':'extension_unreviewed'},
                    'parameters':{'properties':{'operation':{'description':'扩展自定义操作'}}}}
        self.assertEqual(option_presentation(definition,'operation','power'),('power','扩展自定义操作'))
        self.assertEqual(parameter_title(definition,'rank'),'rank')


@unittest.skipUnless(QT_AVAILABLE,'Optional PySide6 dependency unavailable')
class NativeTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_all_enum_and_boolean_values_survive_display_selection_and_draft_restore(self):
        for definition in ToolRegistry().catalog():
            guides={item['name']:item for item in input_guide(definition)['fields']}
            for parameter,schema in definition['parameters']['properties'].items():
                if 'enum' not in schema and schema.get('type')!='boolean':continue
                field=ParameterField(parameter,schema,guides[parameter],False,definition)
                try:
                    values=schema.get('enum',[False,True])
                    for value in values:
                        with self.subTest(tool=definition['name'],parameter=parameter,value=value):
                            field.set_value(value);self.assertEqual(field.read(),value)
                            self.assertIs(type(field.read()),type(value))
                            index=field.editor.currentIndex()
                            hint=field.editor.itemData(index,Qt.ItemDataRole.ToolTipRole)
                            self.assertTrue(hint);self.assertEqual(field.editor.toolTip(),hint)
                            snapshot=field.snapshot();field.set_value(values[0]);field.restore(snapshot)
                            self.assertEqual(field.read(),value)
                finally:field.close();field.deleteLater();self.app.processEvents()

    def test_real_popup_help_event_uses_hovered_item_without_changing_selection(self):
        definition=ToolRegistry().describe('graph_edit');schema=definition['parameters']['properties']['operation']
        guide=next(item for item in input_guide(definition)['fields'] if item['name']=='operation')
        field=ParameterField('operation',schema,guide,True,definition);field.resize(640,260);field.show()
        try:
            field.set_value('complement');field.editor.showPopup();self.app.processEvents()
            view=field.editor.view();index=field.editor.model().index(schema['enum'].index('power'),0)
            view.scrollTo(index);self.app.processEvents();point=view.visualRect(index).center()
            event=QHelpEvent(QEvent.Type.ToolTip,point,view.viewport().mapToGlobal(point))
            QApplication.sendEvent(view.viewport(),event);self.app.processEvents()
            self.assertIn('最短路距离',QToolTip.text());self.assertEqual(field.read(),'complement')
            field.editor.hidePopup();QToolTip.hideText();field.set_value('power')
            self.assertIn('图的幂',field.editor.currentText());self.assertIn('最短路距离',field.editor.toolTip())
        finally:QToolTip.hideText();field.editor.hidePopup();field.close();field.deleteLater();self.app.processEvents()

    def test_model_settings_translate_choices_but_preserve_protocol_values(self):
        import tempfile
        from pathlib import Path
        from graph_research.desktop.configuration import ModelDialog
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.json';dialog=ModelDialog(config_path=path)
            try:
                dialog.address.setText('https://example.invalid/v1');dialog.model_id.setText('offline-test')
                for mode in ('responses','chat_completions'):
                    dialog.protocol.setCurrentIndex(dialog.protocol.findData(mode))
                    for key in ('max_tokens','max_completion_tokens'):
                        dialog.token_field.setCurrentIndex(dialog.token_field.findData(key))
                        settings=dialog.read_settings()
                        self.assertEqual(settings.mode,mode);self.assertEqual(settings.chat_token_field,key)
                        for combo in (dialog.protocol,dialog.token_field):
                            self.assertRegex(combo.currentText(),r'[\u4e00-\u9fff]');self.assertTrue(combo.toolTip())
                self.assertFalse(path.exists())
            finally:dialog.close();dialog.deleteLater();self.app.processEvents()


class LanguagePreferencesTests(unittest.TestCase):
    def test_language_preferences_are_atomic_validated_and_read_only_on_load(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from graph_research.desktop.i18n import load_language,save_language
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'language.json'
            self.assertEqual(load_language(path),'zh');self.assertFalse(path.exists())
            save_language('en',path);self.assertEqual(load_language(path),'en')
            before=path.read_bytes()
            with patch('graph_research.desktop.i18n.os.replace',side_effect=OSError('simulated write failure')):
                with self.assertRaises(OSError):save_language('zh',path)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])
            for invalid in ([],None,{'version':1,'language':'fr'},{'version':2,'language':'en'}):
                path.write_text(json.dumps(invalid),encoding='utf-8')
                self.assertEqual(load_language(path),'zh')
            with self.assertRaises(ValueError):save_language('unknown',path)


@unittest.skipUnless(QT_AVAILABLE,'Optional PySide6 dependency unavailable')
class BilingualDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from graph_research.desktop.i18n import set_language
        set_language('zh');self.addCleanup(set_language,'zh')

    def test_all_native_titles_parameters_options_and_current_help_have_english(self):
        from graph_research.desktop.english import register_registry
        from graph_research.desktop.i18n import set_language,tr
        registry=ToolRegistry();register_registry(registry);set_language('en')
        chinese=re.compile(r'[\u4e00-\u9fff]')
        for definition in registry.catalog():
            self.assertNotRegex(tr(TITLES[definition['name']]),chinese)
            for note in input_guide(definition)['notes']:self.assertNotRegex(tr(note),chinese)
            guides={field['name']:field for field in input_guide(definition)['fields']}
            for name,schema in definition['parameters']['properties'].items():
                self.assertNotRegex(tr(parameter_title(definition,name)),chinese)
                if 'enum' not in schema and schema.get('type')!='boolean':continue
                field=ParameterField(name,schema,guides[name],False,definition)
                try:
                    for value in schema.get('enum',[False,True]):
                        field.set_value(value)
                        with self.subTest(tool=definition['name'],parameter=name,value=value):
                            self.assertEqual(field.read(),value);self.assertIs(type(field.read()),type(value))
                            self.assertNotRegex(field.editor.currentText(),chinese)
                            self.assertTrue(field.editor.toolTip());self.assertNotRegex(field.editor.toolTip(),chinese)
                finally:field.deleteLater();self.app.processEvents()

    def test_live_switch_preserves_form_json_history_model_input_and_task_state(self):
        import copy
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from graph_research.desktop.i18n import set_language,load_language
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.shell import IntegratedWindow
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);workspace=DesktopWorkspace(root/'work');window=IntegratedWindow(workspace)
            try:
                offline=window.offline;offline.select_tool('graph_edit');offline.apply_example()
                offline.fields['operation'].set_value('power');offline.fields['power'].set_value(2)
                before=offline.collect_arguments();schema=copy.deepcopy(offline.definition)
                draft='{"labels":["完全图","中文用户标签"],"alpha":0.99}'
                offline.input_tabs.setCurrentIndex(1);offline.json_editor.setPlainText(draft)
                self.assertEqual(offline.json_editor.toPlainText(),draft)
                with patch('graph_research.desktop.i18n._preference_path',root/'language.json'):
                    window._language_actions['en'].trigger()
                    self.assertEqual(load_language(root/'language.json'),'en')
                self.assertEqual(offline.compute.text(),'Start computation')
                self.assertEqual(window.modes.tabText(0),'Local tools')
                self.assertEqual(offline.json_editor.toPlainText(),draft)
                self.assertEqual(offline.definition,schema);self.assertIsNone(window.chat)
                self.assertIsNone(offline.thread);self.assertEqual(workspace.history(),[])
                offline.input_tabs.setCurrentIndex(0);self.assertEqual(offline.collect_arguments(),before)
                self.assertIn('Graph power',offline.fields['operation'].editor.currentText())
                set_language('zh');self.assertEqual(offline.compute.text(),'开始计算')
                self.assertEqual(offline.collect_arguments(),before)
                self.assertEqual(offline.json_editor.toPlainText(),draft)
            finally:window.close();window.deleteLater();self.app.processEvents()

    def test_bindings_support_unhashable_qt_items_and_do_not_emit_selection_signals(self):
        from graph_research.desktop.i18n import set_language
        from graph_research.desktop.widgets import QComboBox,QListWidgetItem,QTableWidgetItem
        combo=QComboBox();combo.addItem('补图','complement');combo.addItem('图的幂','power');combo.setCurrentIndex(1)
        combo.setItemData(1,'最短路距离',Qt.ItemDataRole.ToolTipRole)
        events=[];combo.currentTextChanged.connect(events.append)
        item=QListWidgetItem('计算结果');raw=QTableWidgetItem('完全图');ui=QTableWidgetItem('是',ui=True)
        try:
            set_language('en')
            self.assertEqual(item.text(),'Computation result');self.assertEqual(raw.text(),'完全图')
            self.assertEqual(ui.text(),'Yes');self.assertEqual(combo.currentData(),'power');self.assertEqual(events,[])
            set_language('zh');self.assertEqual(item.text(),'计算结果');self.assertEqual(ui.text(),'是')
            self.assertEqual(combo.currentData(),'power');self.assertEqual(events,[])
        finally:combo.deleteLater();self.app.processEvents()

    def test_parameter_form_retains_natural_height_for_long_english_help(self):
        from PySide6.QtWidgets import QWidget,QVBoxLayout,QScrollArea,QLabel
        from graph_research.desktop.english import register_registry
        from graph_research.desktop.i18n import set_language
        register_registry(ToolRegistry())
        definition=ToolRegistry().describe('graph_edit');name='kind';schema=definition['parameters']['properties'][name]
        guide=next(field for field in input_guide(definition)['fields'] if field['name']==name)
        field=ParameterField(name,schema,guide,False,definition)
        content=QWidget();layout=QVBoxLayout(content);layout.addWidget(field);layout.addStretch()
        area=QScrollArea();area.setWidgetResizable(True);area.setWidget(content);area.resize(400,180);area.show()
        try:
            for code in ('en','zh','en'):
                set_language(code);self.app.processEvents();self.app.processEvents()
                for label in field.findChildren(QLabel):
                    if not label.isHidden() and label.wordWrap():
                        self.assertGreaterEqual(label.height()+1,label.heightForWidth(label.width()))
        finally:area.close();area.deleteLater();self.app.processEvents()

    def test_model_settings_language_switch_does_not_change_ids_keys_or_protocol(self):
        import tempfile
        from pathlib import Path
        from graph_research.desktop.configuration import ModelDialog
        from graph_research.desktop.i18n import set_language
        with tempfile.TemporaryDirectory() as folder:
            dialog=ModelDialog(config_path=Path(folder)/'model.json')
            try:
                dialog.address.setText('https://example.invalid/v1');dialog.model_id.setText('完全图')
                dialog.protocol.setCurrentIndex(dialog.protocol.findData('chat_completions'))
                set_language('en')
                self.assertEqual(dialog.windowTitle(),'Model settings')
                self.assertEqual(dialog.model_id.text(),'完全图')
                self.assertEqual(dialog.model_id.lineEdit().placeholderText(),"Select or enter the provider's model ID")
                self.assertEqual(dialog.protocol.currentData(),'chat_completions')
                self.assertEqual(dialog.address.text(),'https://example.invalid/v1')
                self.assertFalse((Path(folder)/'model.json').exists())
                set_language('zh');self.assertEqual(dialog.model_id.text(),'完全图')
            finally:dialog.deleteLater();self.app.processEvents()

    def test_conversation_content_and_argument_tooltips_are_not_translated(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtWidgets import QLabel,QPushButton
        from graph_research.desktop.chat import ChatWindow
        from graph_research.desktop.model_service import ModelWorkspace
        from graph_research.desktop.research_view import AnswerView
        from graph_research.desktop.i18n import set_language
        request='完全图 开始计算 科研对话';answer='计算结果：完全图';arguments={'labels':['完全图','科研对话']}
        with tempfile.TemporaryDirectory() as folder,patch('httpx.Client',side_effect=AssertionError('No model request')):
            window=ChatWindow(ModelWorkspace(Path(folder)/'model'))
            try:
                window.view_state={'observations':[{'tool':'graph_invariants','arguments':arguments,'ok':True}]}
                window.view_turns=[{'number':1,'user_request':request,'answer':answer,'status':'completed','observation_start':0,'observation_end':1}]
                for code in ('en','zh','en'):
                    set_language(code);window.render_conversation();self.app.processEvents()
                    self.assertIn(request,[item.text() for item in window.messages.findChildren(QLabel)])
                    self.assertIn(answer,[item.plain_answer for item in window.messages.findChildren(AnswerView)])
                    self.assertIn(json.dumps(arguments,ensure_ascii=False),[item.toolTip() for item in window.messages.findChildren(QPushButton)])
                window.preview_text.setText(request);self.assertEqual(window.preview_text.text(),request)
            finally:window.close();window.deleteLater();self.app.processEvents()

    def test_deleted_widgets_are_not_revived_by_language_change(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        from graph_research.desktop.i18n import set_language
        from graph_research.desktop.widgets import QPlainTextEdit
        text=QPlainTextEdit();text.setLocalizedRenderer(lambda:'raw user text')
        text.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        set_language('en');set_language('zh')
        definition=ToolRegistry().describe('graph_invariants')
        guide=next(item for item in input_guide(definition)['fields'] if item['name']=='n')
        field=ParameterField('n',definition['parameters']['properties']['n'],guide,False,definition)
        field.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()  # A pending singleShot must not call a deleted C++ widget.
        field._reflow();set_language('en');set_language('zh')

    def test_graph_and_result_data_stay_original_while_english_labels_update(self):
        import tempfile
        from pathlib import Path
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.graph_input import GraphInputDialog
        from graph_research.graph_input.document import document
        from graph_research.desktop.i18n import set_language
        from graph_research.desktop.result_text import result_text
        graph=document(['完全图','叶点','孤立点'],[{'vertices':['完全图','叶点']}],
                       graph_type='hypergraph',name='中文研究对象')
        with tempfile.TemporaryDirectory() as folder:
            workspace=DesktopWorkspace(Path(folder)/'work');dialog=GraphInputDialog(workspace.graph_library,graph=graph)
            try:
                before=dialog.graph.to_dict();name=dialog.name.text();set_language('en')
                self.assertEqual(dialog.windowTitle(),'Graph input');self.assertEqual(dialog.name.text(),name)
                self.assertEqual(dialog.graph.to_dict(),before)
                result={'tool':'graph_invariants','ok':True,'result':{'order':3,'connected':False,'vertices':['完全图','叶点']}}
                text=result_text(result);self.assertIn('Vertex count',text);self.assertIn('完全图',text)
                self.assertEqual(result['result']['vertices'],['完全图','叶点'])
                set_language('zh');self.assertEqual(dialog.graph.to_dict(),before)
            finally:dialog.deleteLater();self.app.processEvents()

    def test_language_switch_during_computation_does_not_cancel_or_repeat_it(self):
        import tempfile
        import time
        from pathlib import Path
        from graph_research.desktop.app import DesktopWindow
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.i18n import set_language
        with tempfile.TemporaryDirectory() as folder:
            workspace=DesktopWorkspace(Path(folder)/'work');window=DesktopWindow(workspace)
            try:
                window.select_tool('graph_invariants');window.apply_example();window.start_calculation()
                set_language('en');set_language('zh');set_language('en')
                deadline=time.monotonic()+30
                while window.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
                self.assertIsNone(window.thread);self.assertEqual(len(workspace.history()),1)
                self.assertTrue(workspace.history()[0]['ok']);self.assertEqual(window.recent.count(),1)
            finally:
                if window.thread is not None:
                    window.cancel_calculation()
                    while window.thread is not None:self.app.processEvents();time.sleep(.01)
                window.close();window.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
