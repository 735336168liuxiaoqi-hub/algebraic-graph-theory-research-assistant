"""Public compatibility and dependency boundaries of functional packages."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest
import tomllib
from unittest.mock import patch

from graph_research import graphs,hypergraphs,tensors


ROOT=Path(__file__).resolve().parents[1]


class PackageStructureTests(unittest.TestCase):
    def test_v08_public_functions_and_method_parameters_remain_compatible(self):
        baseline=json.loads((ROOT/'graph_research/data/api_compat_v08.json').read_text(encoding='utf-8'))
        for module in [graphs,hypergraphs,tensors]:
            for name,signature in baseline['modules'][module.__name__].items():
                with self.subTest(api=module.__name__+'.'+name):
                    self.assertEqual(str(inspect.signature(getattr(module,name))),signature)
        for name,signature in baseline['hypergraph_methods'].items():
            obj=getattr(hypergraphs.Hypergraph,name)
            parameters=list(inspect.signature(obj).parameters.values())
            actual=str(inspect.Signature(parameters[1:] if parameters and parameters[0].name in ['self','h'] else parameters))
            with self.subTest(method=name):
                if name=='alpha_spectrum':
                    public=parameters[1:] if parameters[0].name=='self' else parameters
                    self.assertEqual(str(inspect.Signature(public[:4])),signature)
                    self.assertEqual([p.name for p in public[4:]],['initial_vector','method'])
                    self.assertTrue(all(p.default is not inspect.Parameter.empty for p in public[4:]))
                else:self.assertEqual(actual,signature)

    def test_legacy_modules_alias_one_canonical_implementation(self):
        from graph_research.registry import ToolRegistry as old_registry
        from graph_research.tools import ToolRegistry
        from graph_research.plotting import HyperGraphPlot as old_plot
        from graph_research.rendering import HyperGraphPlot
        from graph_research.elimination import tensor_characteristic_polynomial as old_elimination
        from graph_research.tensors.elimination import tensor_characteristic_polynomial
        from graph_research.extensions import ToolStore as old_store
        from graph_research.tools.extensions import ToolStore
        self.assertIs(old_registry,ToolRegistry)
        self.assertIs(old_plot,HyperGraphPlot)
        self.assertIs(old_elimination,tensor_characteristic_polynomial)
        self.assertIs(old_store,ToolStore)
        from graph_research.algebra.numeric import spectral_radius
        self.assertIs(graphs.spectral_radius,spectral_radius)

    def _isolated(self,body,blocked):
        code="""
import builtins,sys
sys.path.insert(0,ROOT)
original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name.split('.')[0] in BLOCKED:raise AssertionError('Unexpected optional import: '+name)
 return original(name,*args,**kwargs)
builtins.__import__=guarded
""".replace('ROOT',repr(str(ROOT))).replace('BLOCKED',repr(blocked))+body
        result=subprocess.run([sys.executable,'-I','-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)

    def test_core_math_does_not_import_optional_sdks(self):
        self._isolated("""
from graph_research import Hypergraph,HyperPath,Tensor,graphs
assert abs(graphs.graph_spectrum('path',3)['rho']-2**.5)<1e-10
assert abs(HyperPath(2,3).alpha_spectrum()['rho']-2**(1/3))<1e-8
assert Hypergraph([[0,1,2]]).characteristic_polynomial().degree()==12
assert Tensor([[0,1],[1,0]]).SpectralRadius()[0]>0
assert not any(n.startswith(('graph_research.assistant','graph_research.tools','graph_research.rendering')) for n in sys.modules)
""",{'matplotlib','langgraph','httpx','jsonschema','sage'})

    def test_json_tools_work_without_model_or_plot_dependencies(self):
        self._isolated("""
from graph_research.tools import ToolRegistry
r=ToolRegistry()
assert len(r.tools)==47
assert r.call('graph_invariants',{'kind':'path','n':3})['diameter']==2
assert 'lookup_legacy' not in r.tools
assert not any(n.startswith('graph_research.assistant') for n in sys.modules)
""",{'matplotlib','langgraph','httpx','sage'})

    def test_catalog_cli_uses_tools_runtime_without_model_sdk(self):
        self._isolated("""
from graph_research.cli import main
sys.argv=['graph-research','catalog','--detail','index']
assert main()==0
""",{'matplotlib','langgraph','httpx','sage'})

    def test_native_approval_state_is_shared_without_importing_gui_or_mcp(self):
        self._isolated("""
from graph_research.assistant.approval_state import heartbeat_fresh,compatible_core
assert heartbeat_fresh({'heartbeat':99},now=100)
assert compatible_core({},'c'*64)
assert not any(n.startswith(('PySide6','mcp','graph_research.mcp','graph_research.desktop')) for n in sys.modules)
""",{'PySide6','mcp','matplotlib','langgraph','httpx'})
        for name in ('desktop/approval_bridge.py','desktop/task_approvals.py'):
            tree=ast.parse((ROOT/'graph_research'/name).read_text(encoding='utf-8'))
            self.assertFalse(any(isinstance(node,ast.ImportFrom) and
                (node.module or '').startswith('graph_research.mcp') for node in ast.walk(tree)),name)

    def test_shared_json_identities_preserve_existing_compact_and_spaced_formats(self):
        from graph_research.runtime.serialization import canonical_json,json_fingerprint,legacy_json_fingerprint
        value={'b':'图','a':[1,-0.0,True,None]}
        compact='{"a":[1,-0.0,true,null],"b":"图"}'
        spaced='{"a": [1, -0.0, true, null], "b": "图"}'
        self.assertEqual(canonical_json(value),compact)
        self.assertEqual(json_fingerprint(value),hashlib.sha256(compact.encode('utf-8')).hexdigest())
        self.assertEqual(legacy_json_fingerprint(value),hashlib.sha256(spaced.encode('utf-8')).hexdigest())
        self.assertNotEqual(json_fingerprint(value),legacy_json_fingerprint(value))
        from graph_research.assistant import experience,research_objects,task_contract,results,result_cleanup
        from graph_research.experiments import execution_contract,preparation
        from graph_research.tools import change_control
        for function in (experience.canonical,research_objects.canonical,task_contract.canonical,results._canonical,preparation._json):
            self.assertIs(function,canonical_json)
        for function in (experience.fingerprint,research_objects.fingerprint,task_contract.digest,execution_contract.digest):
            self.assertIs(function,json_fingerprint)
        self.assertIs(change_control.digest,legacy_json_fingerprint)
        self.assertIs(result_cleanup._json_hash,legacy_json_fingerprint)
        for number in (float('nan'),float('inf'),-float('inf')):
            for function in (canonical_json,json_fingerprint,legacy_json_fingerprint):
                with self.assertRaises(ValueError):function({'number':number})

    def test_shared_json_serialization_requires_only_the_standard_library(self):
        self._isolated("""
from graph_research.runtime.serialization import canonical_json,json_fingerprint
assert canonical_json({'b':2,'a':1})=='{"a":1,"b":2}'
assert len(json_fingerprint({'a':1}))==64
""",{'numpy','networkx','sympy','jsonschema','PySide6','mcp','torch','matplotlib','langgraph','httpx'})

    def test_functional_sources_have_no_wildcard_exports_or_runtime_method_install(self):
        for directory in ['graphs','hypergraphs','algebra','core','tensors','tools','assistant','rendering','experiments']:
            for path in (ROOT/'graph_research'/directory).glob('*.py'):
                tree=ast.parse(path.read_text(encoding='utf-8'))
                self.assertFalse(any(isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names) for n in ast.walk(tree)),str(path))
        model=ast.parse((ROOT/'graph_research/hypergraphs/model.py').read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='setattr' for n in ast.walk(model)))

    def test_installation_separates_core_visual_tools_and_assistant(self):
        metadata=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']
        self.assertEqual(len(metadata['dependencies']),3)
        self.assertTrue(all(not any(optional in name for optional in ('matplotlib','langgraph','httpx','jsonschema')) for name in metadata['dependencies']))
        self.assertEqual(set(metadata['optional-dependencies']),{'visual','tools','assistant','desktop','mcp','all','search'})
        self.assertTrue(any(value.startswith('mcp>=') for value in metadata['optional-dependencies']['mcp']))
        self.assertFalse(any(value.startswith('mcp') for value in metadata['dependencies']))

    def test_catalog_marks_uninstalled_optional_visual_tools(self):
        from graph_research.tools import ToolRegistry
        with patch('graph_research.tools.capabilities.find_spec',return_value=None):
            registry=ToolRegistry()
            self.assertFalse(registry.describe('graph_tikz')['availability']['available'])
            self.assertEqual(registry.describe('graph_tikz')['availability']['install_extra'],'visual')
            self.assertTrue(registry.describe('hypergraph_editor')['availability']['available'])
            self.assertTrue(registry.describe('hypergraph_spectrum')['availability']['available'])


if __name__=='__main__':unittest.main()
