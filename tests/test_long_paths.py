"""Real Windows path depths, publication semantics, export retention and MCP."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
import sys
import zipfile
from unittest.mock import patch

from graph_research.runtime.storage import atomic_text,io_path,logical_path,safe_path,read_json,write_json,storage_error
from graph_research.errors import PathBoundaryError,PathLengthError,SessionBusyError
from graph_research.runtime.integrity import CORE,IntegrityError
from graph_research.runtime.evidence import file_hash
from graph_research.workflows.batch import graph_batch_study


class StorageDiagnosisTests(unittest.TestCase):
    def test_create_failure_is_not_retried_as_disappearing_temporary(self):
        with tempfile.TemporaryDirectory() as tmp,patch('graph_research.runtime.storage.tempfile.mkstemp',side_effect=FileNotFoundError('creation failed')) as create,patch('graph_research.runtime.storage.time.sleep') as sleep:
            with self.assertRaises(FileNotFoundError):atomic_text(Path(tmp)/'result.txt','payload')
            self.assertEqual(create.call_count,1);sleep.assert_not_called()

    def test_disappearing_created_temporary_retries_io_without_recomputing(self):
        with tempfile.TemporaryDirectory() as tmp:
            name='rename' if os.name=='nt' else 'link';publish_file=getattr(os,name);calls=[]
            def publish(source,target):
                calls.append(1)
                if len(calls)==1:Path(source).unlink();raise FileNotFoundError('synthetic temporary disappearance')
                return publish_file(source,target)
            with patch('graph_research.runtime.storage.os.'+name,side_effect=publish):atomic_text(Path(tmp)/'result.txt','same already-computed payload')
            self.assertEqual(len(calls),2);self.assertEqual((Path(tmp)/'result.txt').read_text(),'same already-computed payload')

    def test_export_io_failures_keep_rows_and_register_only_published_files(self):
        cases=[{'name':'P3','input':{'kind':'path','n':3}}]
        with tempfile.TemporaryDirectory() as tmp,patch('pathlib.Path.cwd',return_value=Path(tmp)):
            real=atomic_text
            def no_csv(path,*args,**kwargs):
                if Path(path).suffix=='.csv':raise OSError('synthetic disk error')
                return real(path,*args,**kwargs)
            with patch('graph_research.workflows.batch.atomic_text',side_effect=no_csv):result=graph_batch_study(cases,['structure','spectrum'])
            self.assertEqual(result['status'],'partial');self.assertEqual(result['calculation_status'],'complete');self.assertEqual(result['export_status'],'partial')
            self.assertNotIn('csv',result['files']);self.assertIn('csv',result['export_errors']);self.assertEqual(result['rows'][0]['results']['structure']['size'],2)
            self.assertEqual(read_json(result['files']['json'])[0],result)
            with patch('graph_research.workflows.batch.atomic_text',side_effect=OSError('synthetic disk error')):failed=graph_batch_study(cases)
            self.assertEqual(failed['export_status'],'failed');self.assertEqual(failed['calculation_status'],'complete');self.assertEqual(failed['files'],{})

    def test_security_failures_are_not_downgraded_to_export_warnings(self):
        with tempfile.TemporaryDirectory() as tmp,patch('pathlib.Path.cwd',return_value=Path(tmp)):
            with patch('graph_research.workflows.batch.atomic_text',side_effect=PathBoundaryError('blocked')),self.assertRaises(PathBoundaryError):
                graph_batch_study([{'name':'P3','input':{'kind':'path','n':3}}])

    def test_export_issue_metadata_does_not_label_completed_math_as_failed_execution(self):
        from graph_research.assistant.results import export_issues
        observations=[{'tool':'graph_batch_study','ok':True,'result':{'calculation_status':'complete','export_status':'failed','rows':[{}]}}]
        self.assertEqual(export_issues(observations),[{'call_id':'call-0001','tool':'graph_batch_study','export_status':'failed'}])
        self.assertTrue(observations[0]['ok']);self.assertEqual(observations[0]['result']['calculation_status'],'complete')

    def test_unpublished_staging_file_is_not_registered_as_a_scientific_artifact(self):
        from graph_research.runtime.evidence import output_inventory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'outputs').mkdir();(root/'outputs/.gr-orphan.csv').write_text('incomplete');(root/'outputs/published.csv').write_text('complete')
            inventory=output_inventory(root);self.assertEqual([row['path'] for row in inventory],['outputs/published.csv'])

    def test_mcp_error_codes_separate_integrity_paths_locks_and_runtime(self):
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        with tempfile.TemporaryDirectory() as tmp:
            runtime=MCPResearchRuntime(HostConfiguration(tmp,'diagnosis'))
            for error,code,retry in [(IntegrityError('changed'),'core_integrity_failed',False),(PathLengthError('too long'),'path_too_long',False),
                                     (PathBoundaryError('escape'),'sandbox_violation',False),(SessionBusyError('busy'),'host_busy',True),
                                     (RuntimeError('unexpected'),'host_runtime_error',False),(PermissionError('denied'),'io_permission_denied',False)]:
                with patch.object(runtime,'catalog',side_effect=error):result=runtime.call('research_catalog',{})
                self.assertEqual(result['error']['code'],code);self.assertEqual(result['error']['retryable'],retry)
            self.assertFalse(storage_error(FileNotFoundError('missing'),'create')['retryable'])

    def test_background_integrity_failure_is_specific_and_spends_no_calculation_budget(self):
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        from graph_research.mcp.worker import run_job
        with tempfile.TemporaryDirectory() as tmp:
            runtime=MCPResearchRuntime(HostConfiguration(tmp,'worker-diagnosis'))
            task={'version':1,'request_id':'integrity-worker','objective':'diagnosis','execution':{'mode':'tools','steps':[{'id':'p','tool':'graph_invariants','arguments':{'n':3}}]}}
            queued=runtime.parent.submit(task,defer=True);identifier=uuid.uuid4().hex;path=runtime.directory/'jobs'/(identifier+'.json')
            job={'version':1,'job_id':identifier,'task_id':queued['task_id'],'operation':'start','event_id':None,'configuration':runtime.configuration.public(),'state':'queued','created_at':time.time(),'error':None}
            write_json(path,job)
            with patch('graph_research.mcp.worker.assert_integrity',side_effect=IntegrityError('synthetic changed core')):run_job(path)
            saved=read_json(path)[0];self.assertEqual(saved['error']['code'],'core_integrity_failed');self.assertFalse(saved['error']['retryable'])
            self.assertEqual(runtime.parent.get(queued['task_id'])['budget']['used']['tool_calls'],0)


class PinnedRuntimeTests(unittest.TestCase):
    def test_staging_verifies_hash_and_rejects_unsafe_archive_before_creating_directory(self):
        from tools.stage_runtime import stage
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wheel=root/'bad.whl'
            with zipfile.ZipFile(wheel,'w') as archive:archive.writestr('../escape.py','bad')
            with self.assertRaises(ValueError):stage(wheel,'0'*64,root/'bad-hash')
            with self.assertRaises(ValueError):stage(wheel,file_hash(wheel),root/'bad-member')
            self.assertFalse((root/'bad-hash').exists());self.assertFalse((root/'bad-member').exists())

    def test_pinned_runtime_loads_its_own_core_and_detects_changes_without_resealing(self):
        from tools.stage_runtime import stage
        before=file_hash(CORE/'data/tool_docs.json')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wheel=root/'reviewed.whl'
            with zipfile.ZipFile(wheel,'w',zipfile.ZIP_DEFLATED) as archive:
                for path in CORE.rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':archive.write(path,'graph_research/'+path.relative_to(CORE).as_posix())
            result=stage(wheel,file_hash(wheel),root/'runtime')
            command=[sys.executable,'-I','-B','-X','utf8',str(root/'runtime/mcp.py'),'--check']
            checked=subprocess.run(command,capture_output=True,text=True,encoding='utf-8');self.assertEqual(checked.returncode,0,checked.stderr)
            health=json.loads(checked.stdout);self.assertTrue(health['core_verified']);self.assertTrue(Path(health['package_file']).is_relative_to(root/'runtime'))
            self.assertFalse(result['host_configuration_modified']);self.assertFalse(health['state_created'])
            with self.assertRaises(FileExistsError):stage(wheel,file_hash(wheel),root/'runtime')
            copy=root/'runtime/package/graph_research/data/tool_docs.json';copy.write_bytes(copy.read_bytes()+b' ')
            blocked=subprocess.run(command,capture_output=True,text=True,encoding='utf-8');self.assertNotEqual(blocked.returncode,0);self.assertIn('Pinned runtime changed',blocked.stderr)
        self.assertEqual(file_hash(CORE/'data/tool_docs.json'),before)


@unittest.skipUnless(os.name=='nt','Windows native path and protected-worker regression')
class WindowsDeepPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.addCleanup(self.clean)

    def clean(self):
        # Exact newly-created test directory, checked before recursive cleanup.
        resolved=logical_path(io_path(self.root).resolve());base=logical_path(io_path(tempfile.gettempdir()).resolve())
        if resolved.parent!=base:raise RuntimeError('Unexpected test cleanup root')
        if io_path(resolved).exists():shutil.rmtree(io_path(resolved))
        self.temp.cleanup()

    def target(self,length):
        folder=self.root/('边界-'+str(length))
        while len(str(folder/'comparison.csv'))+50<length:folder=folder/('路径-'+'x'*35)
        extra=length-len(str(folder/'comparison.csv'))-1
        if extra>0:folder=folder/('z'*extra)
        self.assertEqual(len(str(folder/'comparison.csv')),length)
        return folder/'comparison.csv'

    def test_publish_read_hash_backup_and_no_clobber_at_real_path_boundaries(self):
        for length in (250,259,260,280,320):
            with self.subTest(length=length):
                path=self.target(length);atomic_text(path,'中文 payload',root=self.root)
                self.assertEqual(io_path(path).read_text(encoding='utf-8'),'中文 payload')
                self.assertEqual(file_hash(path),hashlib.sha256('中文 payload'.encode()).hexdigest())
                with self.assertRaises(FileExistsError):atomic_text(path,'clobber',root=self.root)
                atomic_text(path,'replacement',overwrite=True,root=self.root)
                state=path.with_name('state.json');write_json(state,{'value':1});write_json(state,{'value':2},backup=True)
                self.assertEqual(read_json(state)[0],{'value':2});self.assertEqual(read_json(str(state)+'.previous')[0],{'value':1})

    def test_prefix_spellings_share_the_same_boundary_and_reject_devices(self):
        path=self.root/'file.txt';self.assertEqual(safe_path(path,root=self.root),safe_path(io_path(path),root=io_path(self.root)))
        with self.assertRaises(PathBoundaryError):safe_path(io_path(CORE/'data/tool_docs.json'))
        with self.assertRaises(PathBoundaryError):safe_path(io_path(self.root.parent/'escape.txt'),root=self.root)
        for name in (r'\\.\C:\data',r'\\?\GLOBALROOT\Device\HarddiskVolume1\data'):
            with self.assertRaises(PathBoundaryError):logical_path(name)
        self.assertEqual(str(io_path(r'\\server\share\folder')),r'\\?\UNC\server\share\folder')

    def test_actual_protected_worker_rejects_prefixed_core_and_external_writes(self):
        from graph_research.runtime.runner import run_worker
        outside=self.root/'outside.txt';outside.write_text('original',encoding='utf-8');before=file_hash(CORE/'data/tool_docs.json')
        for path in (outside,CORE/'data/tool_docs.json'):
            result=run_worker('probe',{'operation':'guard_write','path':str(io_path(path))},directory=self.root/'runs')
            self.assertTrue(result['write_denied_by_guard'])
        self.assertEqual(outside.read_text(),'original');self.assertEqual(file_hash(CORE/'data/tool_docs.json'),before)

    def test_prefixed_junction_cannot_escape_the_root(self):
        outside=self.root/'outside';outside.mkdir();link=self.root/'link'
        try:link.symlink_to(outside,target_is_directory=True)
        except OSError:
            command="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(outside).replace("'","''")+"' | Out-Null"
            created=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',command],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertEqual(created.returncode,0,created.stderr)
        try:
            with self.assertRaises(PathBoundaryError):atomic_text(io_path(link/'escape.txt'),'bad',root=self.root)
            self.assertFalse((outside/'escape.txt').exists())
        finally:
            self.assertEqual(link.parent,self.root);io_path(link).rmdir()

    def test_real_deep_mcp_twelve_cases_exports_plot_inspection_and_bundle(self):
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        from graph_research.assistant.results import verify_bundle
        root=self.root/('宿主-'+ 'd'*max(1,92-len(str(self.root))-4))
        runtime=MCPResearchRuntime(HostConfiguration(str(root),'deep-path',results_directory=str(self.root/'成果')))
        cases=[{'name':'P'+str(n)+'-'+str(i),'input':{'kind':'path','n':n}} for i,n in enumerate([3,4,5,6,7,8]*2)]
        arguments={'cases':cases,'calculations':['structure','spectrum','charpoly'],'plot':True}
        task={'version':1,'request_id':'deep-mcp-batch','objective':'深目录批量导出回归','execution':{'mode':'tools','steps':[{'id':'batch','tool':'graph_batch_study','arguments':arguments}]}}
        result=runtime.call('research_submit',{'task':task,'wait_seconds':5,'detail':'full'});deadline=time.monotonic()+40
        while result.get('transport',{}).get('active') and time.monotonic()<deadline:result=runtime.call('research_get',{'task_id':result['task_id'],'wait_seconds':2,'until':'terminal','detail':'full'})
        self.assertEqual(result['status'],'completed',result);data=result['results'][0]['data']
        self.assertEqual(data['calculation_status'],'complete');self.assertEqual(data['export_status'],'complete');self.assertEqual(len(data['rows']),12)
        import sympy as sp
        x=sp.Symbol('x')
        for case,row in zip(cases,data['rows']):
            n=case['input']['n'];self.assertEqual(row['name'],case['name']);self.assertEqual(row['status'],'complete')
            self.assertEqual(row['results']['structure']['order'],n);self.assertEqual(row['results']['structure']['size'],n-1)
            expected=sorted(2*math.cos(math.pi*j/(n+1)) for j in range(1,n+1))
            self.assertTrue(all(abs(a-b)<1e-12 for a,b in zip(row['results']['spectrum']['spectrum'],expected)))
            a,b=sp.Integer(1),x
            for _ in range(2,n+1):a,b=b,sp.expand(x*b-a)
            self.assertEqual(sp.expand(sp.sympify(row['results']['charpoly']['polynomial'])-b),0)
        self.assertGreaterEqual(len(data['files']['csv']),260);self.assertEqual(set(data['files']),{'csv','md','json','png','svg','pdf'})
        self.assertEqual(read_json(data['files']['json'])[0],data)
        inspected=runtime.call('research_inspect_result',{'task_id':result['task_id'],'call_id':'call-0001','path':['rows'],'limit':20})
        self.assertEqual(len(inspected['value']),12)
        self.assertTrue(verify_bundle(result['artifacts'][0]['path'],result['artifacts'][0]['sha256'])['ok'])
        offset=0;raw=bytearray()
        while True:
            part=runtime.call('research_read_artifact',{'task_id':result['task_id'],'index':0,'offset':offset});raw.extend(base64.b64decode(part['data_base64']))
            if part['eof']:break
            offset=part['next_offset']
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['artifacts'][0]['sha256'])
        self.assertEqual(runtime.call('research_get',{'task_id':result['task_id']})['budget']['used']['tool_calls'],1)
