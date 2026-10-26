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
    @unittest.skipUnless(sys.platform=='win32','Windows desktop batch launcher')
    def test_desktop_batch_dispatches_from_unicode_space_path_without_changing_codepage(self):
        import os
        import time
        import venv
        root=Path(__file__).resolve().parents[1]
        raw=(root/'start-desktop.cmd').read_bytes()
        raw.decode('ascii')
        self.assertNotIn(b'\n',raw.replace(b'\r\n',b''))
        self.assertNotIn(b'chcp',raw.lower())
        with tempfile.TemporaryDirectory() as folder:
            workspace=Path(folder)/'中文目录 desktop launch';workspace.mkdir()
            (workspace/'start-desktop.cmd').write_bytes(raw)
            venv.EnvBuilder(with_pip=False).create(workspace/'.venv')
            entry=workspace/'tools/desktop_entry.py';entry.parent.mkdir()
            marker=workspace/'launched.json'
            entry.write_text('import json,os,sys\nfrom pathlib import Path\n'
                'Path(__file__).resolve().parents[1].joinpath("launched.json").write_text('
                'json.dumps({"cwd":os.getcwd(),"args":sys.argv},ensure_ascii=False),encoding="utf-8")\n',encoding='utf-8')
            command=[os.environ.get('COMSPEC','cmd.exe'),'/d','/c','call',str(workspace/'start-desktop.cmd')]
            result=subprocess.run(command,cwd=folder,input='',capture_output=True,text=True,errors='replace',timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            deadline=time.monotonic()+10
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(marker.exists(),result.stdout+result.stderr)
            found=json.loads(marker.read_text(encoding='utf-8'))
            self.assertEqual(Path(found['cwd']).resolve(),workspace.resolve())
            self.assertEqual(Path(found['args'][0]).resolve(),entry.resolve())

    def test_host_customization_diagnostic_is_read_only_and_never_echoes_env_values(self):
        with patch.dict('os.environ',{'PYTHONPATH':'PRIVATE_HOST_PATH'}),patch.dict(sys.modules,{'sitecustomize':SimpleNamespace()}):
            report=environment_report()
            self.assertEqual(__import__('os').environ['PYTHONPATH'],'PRIVATE_HOST_PATH')
            self.assertIn('sitecustomize',sys.modules)
        integration=report['host_integration']
        self.assertTrue(integration['pythonpath_present']);self.assertTrue(integration['sitecustomize_loaded'])
        self.assertEqual(integration['protected_execution'],'not_probed')
        self.assertNotIn('PRIVATE_HOST_PATH',json.dumps(report));self.assertTrue(report['warnings'])

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

    def test_preflight_blockage_keeps_workspace_logs_and_structured_evidence(self):
        from tools.checks import preflight
        from graph_research.runtime.runner import WorkerFailure
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def blocked(*args,**kwargs):
                runs=kwargs['directory'];runs.mkdir()
                (runs/'bootstrap-stderr.log').write_bytes(b'configuration unreadable')
                error=WorkerFailure('fixture blocked',exit_code=107,phase='before_worker_entry')
                error.diagnostic_id='a'*32
                error.startup_diagnostics={'phase':'before_worker_entry','logs':{'bootstrap-stderr.log':{'tail':'configuration unreadable'}}}
                raise error
            with patch('graph_research.runtime.runner.run_tool',side_effect=blocked),redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:preflight(root,root)
            self.assertEqual(caught.exception.code,2)
            evidence=json.loads((root/'preflight.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['status'],'environment_blocked')
            self.assertEqual(evidence['diagnostic_id'],'a'*32)
            self.assertTrue((Path(evidence['workspace'])/'runs/bootstrap-stderr.log').is_file())


@unittest.skipUnless(sys.platform=='win32','Windows startup diagnostic')
class StartupDiagnosticTests(unittest.TestCase):
    def run_diagnostic(self,overrides=None,exit_codes=None):
        from tools.diagnose_protected_startup import main
        import hashlib
        overrides=overrides or {};exit_codes=exit_codes or {}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prefix=root/'venv';prefix.mkdir()
            config=prefix/'pyvenv.cfg';config.write_text('home = test-runtime\n',encoding='utf-8')
            defaults={
                'selected_interpreter':{'selected_python_reached':True,'executable':sys.executable,'prefix':str(prefix)},
                'restricted_base_config_read':{'path':str(config),'exists':True,'readable':True,
                    'sha256':hashlib.sha256(config.read_bytes()).hexdigest(),'has_home':True},
            }
            class FixedProbe:
                process=SimpleNamespace(pid=1);final_usage={'available':False}
                def __init__(self,argv,workspace,env,**kwargs):
                    self.name=workspace.name
                    payload=overrides.get(self.name,defaults[self.name])
                    if isinstance(payload,dict):payload={**defaults[self.name],**payload}
                    if payload is not None:
                        (workspace/'probe.json').write_bytes(payload if isinstance(payload,bytes) else json.dumps(payload).encode('utf-8'))
                def wait(self,*args):return exit_codes.get(self.name,0)
                def close(self):pass
            output=root/'report'
            with patch('graph_research.runtime.windows.WindowsTask',FixedProbe),patch.object(sys,'prefix',str(prefix)),\
                    patch.object(sys,'argv',['diagnose_protected_startup.py','--output',str(output)]),redirect_stdout(io.StringIO()):
                code=main()
            report=json.loads((output/'report.json').read_text(encoding='utf-8'))
        return code,report

    def test_matching_probe_evidence_passes(self):
        code,report=self.run_diagnostic()
        self.assertEqual(code,0)
        self.assertEqual([row['status'] for row in report['probes']],['passed','passed'])

    def test_zero_exit_without_valid_probe_evidence_fails_and_retains_report(self):
        for name in ('selected_interpreter','restricted_base_config_read'):
            for payload,reason in ((None,'probe_result_missing'),(b'{','probe_result_unreadable_or_invalid'),
                                   (b'{}',None),([], 'probe_result_not_object')):
                with self.subTest(probe=name,payload=payload):
                    code,report=self.run_diagnostic({name:payload})
                    self.assertEqual(code,1)
                    row=next(row for row in report['probes'] if row['probe']==name)
                    self.assertEqual(row['worker_exit_code'],0);self.assertEqual(row['status'],'failed')
                    self.assertTrue(row['result_error'])
                    if reason:self.assertEqual(row['result_error'],reason)
                    self.assertNotEqual(row['startup']['phase'],'fixed_probe_completed')

    def test_probe_identity_and_configuration_evidence_must_match(self):
        cases=(
            ('selected_interpreter',{'selected_python_reached':False},'selected_interpreter_not_reached'),
            ('selected_interpreter',{'executable':'wrong-python.exe'},'selected_interpreter_mismatch'),
            ('selected_interpreter',{'prefix':'wrong-environment'},'selected_environment_mismatch'),
            ('restricted_base_config_read',{'readable':False},'configuration_not_readable'),
            ('restricted_base_config_read',{'path':'wrong-pyvenv.cfg'},'configuration_path_mismatch'),
            ('restricted_base_config_read',{'sha256':'0'*64},'configuration_hash_unverified'),
        )
        for name,payload,reason in cases:
            with self.subTest(probe=name,payload=payload):
                code,report=self.run_diagnostic({name:payload})
                self.assertEqual(code,1)
                row=next(row for row in report['probes'] if row['probe']==name)
                self.assertEqual(row['status'],'failed');self.assertEqual(row['result_error'],reason)

    def test_nonzero_exit_fails_even_with_matching_probe_evidence(self):
        for name in ('selected_interpreter','restricted_base_config_read'):
            with self.subTest(probe=name):
                code,report=self.run_diagnostic(exit_codes={name:107})
                self.assertEqual(code,1)
                row=next(row for row in report['probes'] if row['probe']==name)
                self.assertEqual(row['status'],'failed');self.assertEqual(row['worker_exit_code'],107)


if __name__=='__main__':unittest.main()
