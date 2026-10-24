"""Fault injection and real Windows OS enforcement; never mutate the live core."""
from contextlib import closing
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from threading import Event,Thread
import time
import unittest
from unittest.mock import patch
import zipfile

from graph_research import Hypergraph
from graph_research.runtime.integrity import CORE,MANIFEST,backup,restore,verify,sha256
from graph_research.runtime.storage import atomic_text,write_json,read_json,safe_path,exclusive_lock,staged_file
from graph_research.runtime.runner import run_tool,run_worker,TaskLimits
from graph_research.assistant import ResearchSession,UserMemoryStore
from graph_research.tools import ToolRegistry
from graph_research.tools.extensions import ToolStore
from tests.test_feature_workflow import ScriptedModel


class StorageProtectionTests(unittest.TestCase):
    def test_consumed_atomic_temps_do_not_count_as_host_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            with patch.object(Path,'unlink',side_effect=SystemExit('Host deletion policy')) as deletion:
                for i in range(80):atomic_text(path,json.dumps({'step':i}),overwrite=True)
            self.assertEqual(json.loads(path.read_text()),{'step':79})
            deletion.assert_not_called()
            self.assertEqual(list(Path(tmp).glob('.gr-*')),[])

    def test_real_leftover_cleanup_respects_host_deletion_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'export.json'
            with patch.object(Path,'unlink',side_effect=SystemExit('Host deletion policy')):
                with self.assertRaises(SystemExit):
                    with staged_file(path) as temporary:
                        temporary.write_text('incomplete')
                        raise ValueError('Producer failed before publication')
            self.assertFalse(path.exists())
            self.assertEqual(len(list(Path(tmp).glob('.gr-*'))),1)

    @unittest.skipUnless(os.name=='nt','Windows atomic no-clobber rename')
    def test_new_exports_need_no_cleanup_deletions_and_keep_complete_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Path,'unlink',side_effect=SystemExit('Host deletion policy')) as deletion:
                for i in range(80):atomic_text(Path(tmp)/(str(i)+'.json'),json.dumps({'step':i}))
            deletion.assert_not_called();self.assertEqual(list(Path(tmp).glob('.gr-*')),[])
            for i in range(80):self.assertEqual(json.loads((Path(tmp)/(str(i)+'.json')).read_text()),{'step':i})

    def test_atomic_publication_cannot_clobber_a_concurrently_created_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'export.json'
            with self.assertRaises(FileExistsError):
                with staged_file(path) as temporary:
                    temporary.write_text('new calculation')
                    path.write_text('other complete research')
            self.assertEqual(path.read_text(),'other complete research')
            self.assertEqual(list(Path(tmp).glob('.gr-*')),[])

    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_state_publication_retries_only_io_while_a_reader_holds_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';write_json(path,{'revision':1});blocked=Event();errors=[];produced=[];replace=os.replace
            def publish(source,target):
                try:return replace(source,target)
                except OSError as error:
                    if getattr(error,'winerror',None) in (5,32,33):blocked.set()
                    raise
            def writer():
                produced.append(1)
                try:write_json(path,{'revision':2})
                except Exception as error:errors.append(error)
            with patch('graph_research.runtime.storage.os.replace',side_effect=publish) as attempts:
                with path.open('rb'):
                    thread=Thread(target=writer);thread.start();self.assertTrue(blocked.wait(2));self.assertEqual(read_json(path)[0],{'revision':1})
                thread.join(2);self.assertFalse(thread.is_alive());self.assertFalse(errors);self.assertGreaterEqual(attempts.call_count,2)
            self.assertEqual(produced,[1]);self.assertEqual(read_json(path)[0],{'revision':2})

    def test_documentation_and_batch_output_cannot_pollute_the_package(self):
        from graph_research.tools.contracts import export_documentation
        with self.assertRaises(PermissionError):export_documentation(ToolRegistry(),CORE/'accidental-docs')
        result=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','demo','--output',str(CORE/'accidental-experiment')],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((CORE/'accidental-docs').exists());self.assertFalse((CORE/'accidental-experiment').exists())
        self.assertTrue(verify()['ok'])

    def test_exports_cannot_write_core_or_clobber_existing_research(self):
        before=sha256(CORE/'data/tool_docs.json')
        h=Hypergraph([[0,1,2]])
        with self.assertRaises(PermissionError):h.save_pos(CORE/'data/tool_docs.json',overwrite=True)
        self.assertEqual(sha256(CORE/'data/tool_docs.json'),before)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plot.tex'
            h.save_tikz(path);first=path.read_bytes()
            with self.assertRaises(FileExistsError):h.save_tikz(path,vertex_labels=False)
            self.assertEqual(path.read_bytes(),first)
            h.save_tikz(path,vertex_labels=False,overwrite=True)
            self.assertNotEqual(path.read_bytes(),first)
            with self.assertRaises(PermissionError):safe_path(Path(tmp)/'../escape',root=tmp)

    def test_atomic_failure_preserves_complete_state_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';write_json(path,{'step':1},backup=True)
            with patch('graph_research.runtime.storage.os.replace',side_effect=OSError('Simulated disk interruption')):
                with self.assertRaises(OSError):write_json(path,{'step':2},backup=True)
            self.assertEqual(read_json(path)[0],{'step':1})
            write_json(path,{'step':2},backup=True);path.write_text('{incomplete',encoding='utf-8')
            self.assertEqual(read_json(path,recover=True),({'step':1},True))
            with self.assertRaises(ValueError):read_json(path,recover=False)

    def test_link_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/'outside';outside.mkdir();link=root/'link'
            try:link.symlink_to(outside,target_is_directory=True)
            except OSError:
                if os.name!='nt':raise
                command="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(outside).replace("'","''")+"' | Out-Null"
                created=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',command],capture_output=True)
                self.assertEqual(created.returncode,0,created.stderr)
            with self.assertRaises(PermissionError):atomic_text(link/'bad.json','x')
            self.assertFalse((outside/'bad.json').exists())

    def test_integrity_detects_modified_missing_and_extra_files_then_recovers_new_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);copy=root/'copy'
            shutil.copytree(CORE,copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            self.assertTrue(verify(copy)['ok'])
            result=backup(root/'recovery.zip',root=copy)
            (copy/'__init__.py').write_text('damaged',encoding='utf-8')
            (copy/'assistant/memory.py').unlink()
            (copy/'unwanted.py').write_text('unexpected',encoding='utf-8')
            report=verify(copy)
            self.assertFalse(report['ok']);self.assertIn('__init__.py',report['changed'])
            self.assertIn('assistant/memory.py',report['missing']);self.assertIn('unwanted.py',report['extra'])
            with self.assertRaises(RuntimeError):backup(root/'bad.zip',root=copy)
            with self.assertRaises(ValueError):restore(result['archive'],'0'*64,root/'bad-restore')
            destination=root/'restored'
            self.assertTrue(restore(result['archive'],result['sha256'],destination)['verified'])
            self.assertTrue(verify(destination/'graph_research')['ok'])
            self.assertEqual((copy/'__init__.py').read_text(),'damaged')
            with self.assertRaises(FileExistsError):restore(result['archive'],result['sha256'],destination)
            process=subprocess.run([sys.executable,'-I',str(CORE.parent/'tools/recover_release.py'),result['archive'],
                                    '--sha256',result['sha256'],'--destination',str(root/'standalone')],cwd=copy,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertTrue(json.loads(process.stdout)['verified'])
            self.assertTrue(verify(root/'standalone/graph_research')['ok'])

    def test_recovery_rejects_path_traversal_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as bundle:bundle.writestr('graph_research/../../escape','x')
            with self.assertRaises(ValueError):restore(archive,sha256(archive),root/'new')
            self.assertFalse((root/'new').exists());self.assertFalse((root/'escape').exists())

    def test_corrupted_session_recovers_previous_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);session=ResearchSession(root/'session',root/'packages')
            session.ask('保存记录',ScriptedModel([{'action':'final','answer':'记录完成'}]))
            (session.directory/'session.json').write_text('incomplete',encoding='utf-8')
            recovered=ResearchSession(session.directory)
            self.assertIn('recovery_notice',recovered.state)
            self.assertEqual(recovered.state['question'],'保存记录')
            model=ScriptedModel([{'action':'final','answer':'恢复完成'}])
            self.assertEqual(recovered.continue_run(model)['status'],'model_analysis_only')

    def test_concurrent_or_stale_session_cannot_execute_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=ResearchSession(root/'session',root/'packages')
            stale=ResearchSession(root/'session',root/'packages')
            first.ask('hello',ScriptedModel([{'action':'final','answer':'ok'}]))
            model=ScriptedModel([])
            with self.assertRaisesRegex(RuntimeError,'changed'):stale.ask('hello',model)
            self.assertEqual(model.contexts,[])
            with exclusive_lock(root/'session/.session.lock'):
                with self.assertRaises(RuntimeError):ResearchSession(root/'session').reply('again',model)

    def test_broken_and_legacy_extensions_do_not_block_native_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('bad','legacy'):(root/name).mkdir()
            (root/'bad/tool.json').write_text('{broken',encoding='utf-8')
            (root/'legacy/tool.json').write_text(json.dumps({'name':'old','source':'def run(args): return 0'}),encoding='utf-8')
            store=ToolStore(root);registry=ToolRegistry();errors=store.load_into(registry)
            self.assertEqual({e['action'] for e in errors},{'quarantined','disabled_legacy'})
            self.assertEqual(len(registry.tools),47)
            self.assertEqual(registry.call('graph_invariants',{'kind':'path','n':3})['diameter'],2)

    def test_credentials_are_not_inherited_by_calculation_environment(self):
        from graph_research.runtime.runner import clean_environment
        with patch.dict(os.environ,{'RESEARCH_API_KEY':'secret','CLOUD_PASSWORD':'secret','UNUSUAL_CREDENTIAL':'secret'}):
            result=clean_environment('task')
            self.assertFalse(any(value=='secret' for value in result.values()))

    def test_decode_log_falls_back_through_console_codepages(self):
        from graph_research.runtime.runner import _decode_log
        self.assertEqual(_decode_log('héllo'.encode('utf-8')),'héllo')
        self.assertEqual(_decode_log('错误 107'.encode('cp936')),'错误 107')
        self.assertEqual(_decode_log(b'\xff\xfeh\x00i\x00'),'hi')
        self.assertEqual(_decode_log(b'plain ascii'),'plain ascii')


@unittest.skipUnless(os.name=='nt','Windows OS isolation backend')
class WindowsExecutionTests(unittest.TestCase):
    def test_native_stdlib_denial_is_visible_and_never_retried_or_mislabelled(self):
        from types import SimpleNamespace
        from graph_research.runtime.runner import WorkerFailure
        from graph_research.runtime.observability import error_details
        launches=[]
        class DeniedBootstrap:
            startup_phase='running';startup_seconds={};process=SimpleNamespace(pid=1);final_usage={'available':False}
            def __init__(self,argv,workspace,env,**kwargs):
                launches.append(argv);kwargs['prepare']()
                (workspace/'bootstrap-stderr.log').write_text('Fatal Python error: Failed to import encodings module\nPermissionError: [Errno 13] Permission denied: C:/PRIVATE_TOKEN/Lib/encodings/__init__.py\nSECRET_VALUE',encoding='utf-8')
            def wait(self,*args):return 107
            def close(self):pass
        with tempfile.TemporaryDirectory() as tmp,patch('graph_research.runtime.windows.WindowsTask',DeniedBootstrap):
            with self.assertRaises(WorkerFailure) as caught:
                run_worker('probe',{'operation':'echo','payload':'never computed'},directory=Path(tmp)/'tasks')
            error=caught.exception;detail=error_details(error)
            self.assertEqual(error.phase,'before_worker_entry');self.assertEqual(detail['cause_code'],'python_stdlib_access_denied')
            self.assertIn('encodings',str(error));self.assertIn('PermissionError',str(error))
            self.assertNotIn('SECRET_VALUE',str(error));self.assertNotIn('PRIVATE_TOKEN',json.dumps(detail))
            self.assertNotIn('venv configuration error',str(error))
            self.assertEqual(len(launches),1);self.assertIn('-I',launches[0])
            receipt=read_json(Path(error.execution_directory)/'execution.json')[0]
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['error_details']['startup'],detail['startup'])

    def test_exit_code_alone_never_asserts_a_permission_or_configuration_cause(self):
        from graph_research.runtime.runner import _startup_issue
        issue=_startup_issue({'phase':'before_worker_entry','worker_exit_code':107,'logs':{}})
        self.assertEqual(issue['code'],'protected_worker_startup_failed')
        self.assertIsNone(_startup_issue({'phase':'worker_reported','logs':{}}))

    def test_venv_launcher_error107_is_captured_before_python_entry(self):
        if sys.prefix==sys.base_prefix:self.skipTest('Requires the Windows venv redirector')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);launcher=root/'launcher';launcher.mkdir()
            copied=launcher/'python.exe';shutil.copy2(sys.executable,copied)
            (launcher/'pyvenv.cfg').write_text('include-system-site-packages = false\n',encoding='utf-8')
            with patch('graph_research.runtime.runner.sys.executable',str(copied)):
                with self.assertRaisesRegex(RuntimeError,'0x6b'):
                    run_worker('probe',{'operation':'memory'},directory=root/'tasks')
            task=next((root/'tasks').iterdir());receipt=read_json(task/'execution.json')[0]
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['startup']['worker_exit_code'],107)
            self.assertEqual(receipt['startup']['phase'],'before_worker_entry')
            self.assertTrue(receipt['startup']['job_assigned'])
            self.assertIn('home',receipt['startup']['logs']['bootstrap-stderr.log']['tail'].lower())
            self.assertEqual(receipt['error_details']['cause_code'],'venv_configuration_invalid')
            self.assertFalse((task/'result.json').exists())

    def test_echo_probe_roundtrip_proves_bootstrap_without_loading_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_worker('probe',{'operation':'echo','payload':'gate'},directory=Path(tmp)/'tasks')
            self.assertEqual(result['echo'],'gate');self.assertIsInstance(result['pid'],int)

    def test_unknown_tool_error_is_structured_and_rendered_once(self):
        from graph_research.runtime.runner import WorkerFailure
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tools').mkdir()
            with self.assertRaises(WorkerFailure) as caught:
                run_tool('bogus_tool_name',{},root/'tools',directory=root/'runs')
            exc=caught.exception
            self.assertEqual(exc.error_type,'TaskProtocolError');self.assertEqual(exc.error_code,'tool_not_found')
            self.assertEqual(str(exc),'Unknown tool: bogus_tool_name')
            self.assertEqual(exc.phase,'worker_reported')

    def test_explicit_standard_handles_capture_native_startup_and_do_not_leak_other_handles(self):
        from graph_research.runtime.windows import WindowsTask,SECURITY_ATTRIBUTES
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/'host-only.txt';outside.write_text('host handle',encoding='utf-8')
            workspace=root/'child';workspace.mkdir()
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.POINTER(SECURITY_ATTRIBUTES),ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
            kernel.CreateFileW.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            security=SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES),None,True)
            handle=kernel.CreateFileW(str(outside),0x80000000,7,ctypes.byref(security),3,0,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            code=f"import ctypes,json,sys;from pathlib import Path;k=ctypes.WinDLL('kernel32');k.GetFinalPathNameByHandleW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong];b=ctypes.create_unicode_buffer(32768);n=k.GetFinalPathNameByHandleW({handle},b,len(b),0);Path('inherited.json').write_text(json.dumps(b.value if n else None));print('early-stdout');sys.stderr.write('early-stderr');sys.exit(13)"
            try:
                with closing(WindowsTask([sys._base_executable,'-I','-B','-c',code],workspace,os.environ.copy())) as task:
                    self.assertEqual(task.wait(10),13)
                inherited=json.loads((workspace/'inherited.json').read_text())
                self.assertNotEqual((inherited or '').replace('\\\\?\\','').casefold(),str(outside).casefold())
                self.assertIn('early-stdout',(workspace/'bootstrap-stdout.log').read_text())
                self.assertIn('early-stderr',(workspace/'bootstrap-stderr.log').read_text())
            finally:kernel.CloseHandle(handle)

    def test_low_integrity_core_location_is_rejected_instead_of_silently_allowed(self):
        from graph_research.runtime.windows import WindowsTask
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);low=root/'low';low.mkdir();other=root/'other';other.mkdir()
            task=WindowsTask([sys._base_executable,'-I','-B','-c','pass'],low,os.environ.copy())
            try:self.assertEqual(task.wait(5),0)
            finally:task.close()
            with self.assertRaisesRegex(PermissionError,'medium-or-higher'):
                WindowsTask([sys._base_executable,'-I','-B','-c','pass'],other,os.environ.copy(),protected_paths=[low])

    def test_native_write_is_denied_by_os_and_calculation_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);canary=root/'canary';canary.write_text('preserve',encoding='utf-8')
            before=verify()['manifest_sha256']
            result=run_worker('probe',{'operation':'native_write','path':str(canary)},directory=root/'tasks')
            self.assertTrue(result['write_denied_by_os']);self.assertEqual(result['error'],5)
            self.assertEqual(canary.read_text(),'preserve')
            self.assertEqual(run_tool('graph_invariants',{'kind':'path','n':4},root/'packages',directory=root/'tasks')['diameter'],3)
            self.assertEqual(verify()['manifest_sha256'],before);self.assertTrue(verify()['ok'])

    def test_os_memory_cap_rejects_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_worker('probe',{'operation':'memory'},directory=tmp,limits=TaskLimits(memory_mb=64))
            self.assertTrue(result['allocation_denied'])

    def test_timeout_and_cancellation_leave_no_accepted_partial_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(TimeoutError):run_worker('probe',{'operation':'sleep'},directory=root/'timeout',limits=TaskLimits(wall_seconds=0.5))
            stop=Event();stop.set()
            with self.assertRaises(InterruptedError):run_worker('probe',{'operation':'sleep'},directory=root/'cancel',cancel=stop)
            statuses=[json.loads(p.read_text())['status'] for p in root.glob('*/task_*/execution.json')]
            self.assertEqual(sorted(statuses),['cancelled','failed'])

    def test_immediate_cancellation_releases_workspace_before_returning(self):
        from graph_research.runtime.windows import WindowsTask
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for index in range(12):
                workspace=root/str(index);workspace.mkdir()
                task=WindowsTask([sys._base_executable,'-I','-B','-c','import time;time.sleep(60)'],workspace,os.environ.copy())
                task.k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
                task.k.OpenProcess.restype=ctypes.c_void_p
                handle=task.k.OpenProcess(0x100000,False,task.process.pid)
                self.assertTrue(handle)
                try:
                    task.close()
                    self.assertEqual(task.k.WaitForSingleObject(handle,0),0)
                    (workspace/'bootstrap-stdout.log').unlink();(workspace/'bootstrap-stderr.log').unlink()
                    workspace.rmdir()
                finally:
                    task.close();task.k.CloseHandle(handle)

    def test_job_cpu_budget_and_descendant_cleanup(self):
        from graph_research.runtime.windows import WindowsTask
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cpu=root/'cpu';cpu.mkdir()
            task=WindowsTask([sys._base_executable,'-I','-B','-c','while True: pass'],cpu,os.environ.copy(),cpu_seconds=1)
            try:self.assertNotEqual(task.wait(8),0)
            finally:task.close()
            self.assertTrue(task.final_usage['available'])
            self.assertLessEqual(task.final_usage['cpu_seconds'],1.5)
            tree=root/'tree';tree.mkdir()
            code="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(60)']);Path('child.pid').write_text(str(p.pid));time.sleep(60)"
            task=WindowsTask([sys._base_executable,'-I','-B','-c',code],tree,os.environ.copy())
            child_handle=None
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            try:
                deadline=time.monotonic()+8
                while not (tree/'child.pid').exists() and time.monotonic()<deadline:Event().wait(0.05)
                self.assertTrue((tree/'child.pid').exists())
                child_handle=kernel.OpenProcess(0x100000,False,int((tree/'child.pid').read_text()))
                self.assertTrue(child_handle)
                with self.assertRaises(TimeoutError):task.wait(0.2)
            finally:task.close()
            try:self.assertEqual(kernel.WaitForSingleObject(child_handle,0),0)
            finally:
                if child_handle:kernel.CloseHandle(child_handle)


if __name__=='__main__':unittest.main()
