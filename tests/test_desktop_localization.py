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


if __name__=='__main__':unittest.main()
