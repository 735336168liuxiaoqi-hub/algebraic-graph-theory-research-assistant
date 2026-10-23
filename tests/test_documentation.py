"""Check that reviewed contracts match schemas, signatures and actual results."""
import copy
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jsonschema

from graph_research.registry import ToolRegistry,Tool
from graph_research.documentation import conventions,export_documentation,function_definitions,_source
from graph_research.agent import build_agent
from graph_research.extensions import ToolStore


class DocumentationTests(unittest.TestCase):
    def test_all_native_tools_have_contracts_and_valid_actual_defaults(self):
        registry=ToolRegistry()
        self.assertEqual(len(registry.tools),47)
        for tool in registry.tools.values():
            with self.subTest(tool=tool.name):
                doc=tool.documentation
                self.assertEqual(doc['coverage'],'reviewed_native')
                self.assertTrue(all(key in doc for key in ('summary','preconditions','returns','limits','effects','examples')))
                self.assertTrue(set(doc['related_tools'])<=set(registry.tools))
                signature=inspect.signature(tool.function)
                for name,schema in tool.parameters['properties'].items():
                    self.assertTrue(schema['description'])
                    if name in signature.parameters and signature.parameters[name].default is not inspect.Parameter.empty:
                        self.assertEqual(doc['defaults'][name],signature.parameters[name].default)
                    if 'default' in schema:
                        jsonschema.validate(schema['default'],schema)
                        self.assertIsNotNone(schema['default'])
                for example in doc['examples']:
                    jsonschema.validate(example['arguments'],tool.parameters)

    def test_documented_examples_return_the_fields_they_promise(self):
        registry=ToolRegistry()
        with tempfile.TemporaryDirectory() as temporary,patch('pathlib.Path.cwd',return_value=Path(temporary)):
            for name,tool in registry.tools.items():
                for example in tool.documentation['examples']:
                    with self.subTest(tool=name,arguments=example['arguments']):
                        result=registry.call(name,example['arguments'])
                        self.assertTrue(set(example['expected_keys'])<=set(result))

    def test_catalog_views_do_not_leak_mutable_schema_or_documentation(self):
        registry=ToolRegistry()
        record=registry.describe('graph_spectrum')
        record['parameters']['properties']['n']['description']='changed outside'
        record['documentation']['limits'].clear()
        self.assertNotEqual(registry.describe('graph_spectrum')['parameters']['properties']['n']['description'],'changed outside')
        self.assertTrue(registry.describe('graph_spectrum')['documentation']['limits'])
        self.assertTrue(all('parameters' not in t for t in registry.catalog(detail='index')))
        model={t['name']:t for t in registry.catalog(detail='model')}
        self.assertIn('example_arguments',model['hypergraph_spectrum']['documentation'])
        self.assertIn('preconditions',model['hypergraph_spectrum']['documentation'])
        self.assertIn('全部',model['hypergraph_spectrum']['description'])

    def test_reused_schema_fragments_get_distinct_parameter_meanings(self):
        registry=ToolRegistry()
        properties=registry.tools['hypergraph_spectrum'].parameters['properties']
        self.assertIsNot(properties['weights'],properties['vertex_degrees'])
        self.assertIn('边权',properties['weights']['description'])
        self.assertIn('D的对角',properties['vertex_degrees']['description'])
        self.assertNotEqual(properties['weights']['description'],properties['vertex_degrees']['description'])
        edit=registry.tools['graph_edit'].parameters['properties']
        self.assertIsNot(edit['edges'],edit['edit_edges'])
        self.assertIn('delete_edges',edit['edit_edges']['description'])
        self.assertNotIn('delete_edges',edit['edges']['description'])
        compare=registry.tools['compare_graphs'].parameters['properties']
        self.assertIsNot(compare['left'],compare['right'])
        self.assertIn('左侧',compare['left']['description'])
        self.assertIn('右侧',compare['right']['description'])

    def test_stale_operation_contract_is_detected_at_registration(self):
        data=copy.deepcopy(_source())
        del data['tools']['graph_edit']['operations']['complement']
        with patch('graph_research.documentation._source',return_value=data):
            with self.assertRaisesRegex(ValueError,'Operation documentation differs'):
                ToolRegistry()

    def test_generated_files_are_portable_and_do_not_execute_calculations(self):
        registry=ToolRegistry()
        with tempfile.TemporaryDirectory() as temporary,patch.object(registry,'call',side_effect=AssertionError('Docs must not calculate')):
            paths=export_documentation(registry,temporary)
            catalog=json.loads(Path(paths['tool-catalog.json']).read_text(encoding='utf-8'))
            self.assertEqual(len(catalog['tools']),47)
            self.assertTrue(catalog['conventions'])
            api=json.loads(Path(paths['library-api-index.json']).read_text(encoding='utf-8'))
            self.assertGreater(len(api),100)
            self.assertIn('graph_research.algebra.recurrences.solve_linear_recurrence',{entry['python_api'] for entry in api})
            self.assertIn('graph_research.algebra.integer_systems.solve_integer_linear_system',{entry['python_api'] for entry in api})
            self.assertTrue(all(entry['model_callable'] is False for entry in api))
            self.assertTrue(any(entry['documentation_status']=='needs_detail' for entry in api))
            self.assertIn('hypergraph_tensor_charpoly',Path(paths['TOOL_REFERENCE.md']).read_text(encoding='utf-8'))
        for definition in function_definitions(registry):
            self.assertEqual(set(definition),{'name','description','parameters'})
            self.assertIn('返回',definition['description'])

    def test_experimental_tools_keep_their_validation_boundary(self):
        registry=ToolRegistry()
        registry.register(Tool('example_extension','扩展样例',{'type':'object','properties':{}},lambda: {},'fixture_tested_experimental'))
        doc=registry.describe('example_extension')
        self.assertEqual(doc['status'],'fixture_tested_experimental')
        self.assertEqual(doc['documentation']['coverage'],'extension_unreviewed')
        self.assertIn('fixture_tested_experimental',function_definitions(registry)[-1]['description'])

    def test_agent_receives_routing_contracts_without_model_network_access(self):
        captured=[]
        class ScriptedModel:
            def complete(self,messages):
                captured.append(json.loads(messages[1]['content']))
                if len(captured)==1:return {'action':'inspect','query':{'tools':['hypergraph_spectrum','hypergraph_tensor_charpoly','hypergraph_tikz']}}
                return {'action':'final','answer':'仅检查接口说明，不声称完成数学计算。'}
        with tempfile.TemporaryDirectory() as temporary:
            result=build_agent(ScriptedModel(),ToolRegistry(),ToolStore(temporary)).invoke({'question':'说明工具选择边界'})
        self.assertEqual(result['status'],'model_analysis_only')
        context=captured[0]
        self.assertEqual(context['tool_conventions'],conventions())
        self.assertEqual({t['name'] for t in context['tool_inventory']},set(ToolRegistry().tools))
        self.assertLessEqual(len(context['tools']),6)
        tools={t['name']:t for t in captured[1]['inspection']['tools']}
        self.assertEqual(len(tools),3)
        self.assertIn('不是全部',tools['hypergraph_spectrum']['description'])
        self.assertIn('estimate_only',tools['hypergraph_tensor_charpoly']['parameters']['properties'])
        self.assertIn('returns',tools['hypergraph_tikz']['documentation'])


if __name__=='__main__':unittest.main()
