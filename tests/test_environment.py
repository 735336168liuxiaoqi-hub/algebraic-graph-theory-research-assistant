"""Source, installed metadata and entry points identify the same checkout."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tomllib

import graph_research
from graph_research.runtime.diagnostics import environment_report


class EnvironmentTests(unittest.TestCase):
    def test_current_interpreter_source_and_installed_metadata_agree(self):
        report=environment_report()
        self.assertTrue(report['ok'],report['issues'])
        self.assertEqual(report['installed_versions'],[graph_research.__version__])
        self.assertEqual(Path(report['package_file']).resolve(),Path(graph_research.__file__).resolve())

    def test_version_has_one_source_for_package_metadata(self):
        root=Path(__file__).resolve().parents[1]
        project=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))
        self.assertIn('version',project['project']['dynamic']);self.assertNotIn('version',project['project'])
        self.assertEqual(project['tool']['setuptools']['dynamic']['version']['attr'],'graph_research._version.__version__')
        from graph_research._version import __version__
        self.assertEqual(__version__,graph_research.__version__)

    def test_isolated_launch_from_another_directory_uses_this_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-I','-X','utf8','-m','graph_research','doctor'],cwd=directory,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(Path(report['package_file']).resolve(),Path(graph_research.__file__).resolve())
        self.assertEqual(report['installed_versions'],[graph_research.__version__])

    def test_diagnostic_detects_stale_metadata_and_never_reports_credentials(self):
        stale=SimpleNamespace(metadata={'Name':'graph-research-assistant'},version='0.4.0',locate_file=lambda _:Path.cwd())
        with patch('graph_research.runtime.diagnostics.metadata.distributions',return_value=[stale]),patch.dict('os.environ',{'RESEARCH_API_KEY':'PRIVATE_SENTINEL_765'}):
            report=environment_report()
        self.assertFalse(report['ok']);self.assertIn('0.4.0',report['installed_versions'])
        self.assertNotIn('PRIVATE_SENTINEL_765',json.dumps(report))

    def test_cli_version_does_not_initialize_tools_or_models(self):
        from graph_research.cli import main
        buffer=io.StringIO()
        with patch.object(sys,'argv',['graph-research','--version']),redirect_stdout(buffer),self.assertRaises(SystemExit) as result:
            main()
        self.assertEqual(result.exception.code,0);self.assertIn(graph_research.__version__,buffer.getvalue())

    def test_custom_venv_is_valid_even_when_the_source_has_a_project_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';(source/'.venv').mkdir(parents=True);(source/'pyproject.toml').touch()
            custom=root/'my-python';custom.mkdir();(custom/'pyvenv.cfg').write_text('include-system-site-packages = false\n',encoding='utf-8')
            installed=SimpleNamespace(metadata={'Name':'graph-research-assistant'},version=graph_research.__version__,locate_file=lambda _:custom)
            with patch.object(graph_research,'__file__',str(source/'graph_research/__init__.py')),patch.object(sys,'prefix',str(custom)),patch('graph_research.runtime.diagnostics.metadata.distributions',return_value=[installed]):
                report=environment_report()
            self.assertTrue(report['ok'],report['issues']);self.assertFalse(report['uses_project_environment'])
            self.assertEqual(report['environment_kind'],'venv')

    def test_conda_and_inherited_packages_are_supported_without_blocking_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory);(prefix/'conda-meta').mkdir();(prefix/'pyvenv.cfg').write_text('include-system-site-packages = true\n',encoding='utf-8')
            installed=SimpleNamespace(metadata={'Name':'graph-research-assistant'},version=graph_research.__version__,locate_file=lambda _:prefix)
            with patch.object(sys,'prefix',str(prefix)),patch('graph_research.runtime.diagnostics.metadata.distributions',return_value=[installed]):
                report=environment_report()
            self.assertTrue(report['ok']);self.assertEqual(report['environment_kind'],'conda')
            self.assertTrue(report['warnings']);self.assertEqual(report['issues'],[])

    def test_old_python_remains_an_actual_compatibility_error(self):
        with patch.object(sys,'version_info',(3,10,12)):report=environment_report()
        self.assertFalse(report['ok']);self.assertTrue(any('3.11' in issue for issue in report['issues']))

    def test_check_launcher_prefers_explicit_then_activated_python_and_validates_paths(self):
        from tools.launch_checks import select_python
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);relative=Path('Scripts/python.exe') if sys.platform=='win32' else Path('bin/python')
            local=root/'.venv'/relative;local.parent.mkdir(parents=True);local.touch()
            custom=root/'a custom environment'/relative;custom.parent.mkdir(parents=True);custom.touch()
            conda=root/'conda'/('python.exe' if sys.platform=='win32' else 'bin/python');conda.parent.mkdir(parents=True);conda.touch()
            self.assertEqual(select_python(root,{}),local.resolve())
            self.assertEqual(select_python(root,{'VIRTUAL_ENV':str(custom.parent.parent),'CONDA_PREFIX':str(root/'conda')}),custom.resolve())
            self.assertEqual(select_python(root,{'CONDA_PREFIX':str(root/'conda')}),conda.resolve())
            self.assertEqual(select_python(root,{'RESEARCH_PYTHON':str(custom),'CONDA_PREFIX':str(root/'conda')}),custom.resolve())
            with self.assertRaises(ValueError):select_python(root,{'RESEARCH_PYTHON':str(root/'missing.exe')})

    def test_custom_checks_allow_compatible_dependency_versions_but_ci_can_enforce_pins(self):
        from tools.checks import main
        for strict in (False,True):
            with patch.object(sys,'argv',['checks.py']+(['--strict-lock'] if strict else [])),patch('tools.checks.subprocess.run') as run,redirect_stdout(io.StringIO()):
                run.return_value.returncode=0
                main()
            commands=[call.args[0] for call in run.call_args_list]
            self.assertEqual(any('tools/check_dependency_lock.py' in command for command in commands),strict)


if __name__=='__main__':unittest.main()
