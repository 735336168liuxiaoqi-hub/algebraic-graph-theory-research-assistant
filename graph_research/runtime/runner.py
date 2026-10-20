"""One protected host entry point for tool/extension/elimination processes."""
from dataclasses import dataclass
import json
import math
import os
import re
from pathlib import Path
import sys
import uuid
import time
from datetime import datetime,timezone

from .storage import safe_path,atomic_text,io_path
from .integrity import assert_integrity,CORE,inventory
from .observability import Timings,recording,measure,annotate,diagnostic_id,bounded_timings


@dataclass(frozen=True)
class TaskLimits:
    wall_seconds:float=30
    cpu_seconds:int=30
    memory_mb:int=1024
    max_processes:int=8
    output_bytes:int=4*1024*1024
    artifact_bytes:int=64*1024*1024

    def __post_init__(self):
        if type(self.wall_seconds) not in (int,float) or not math.isfinite(self.wall_seconds) or not 0<self.wall_seconds<=3600:raise ValueError('Invalid wall-time limit')
        for name,low,high in [('cpu_seconds',1,3600),('memory_mb',64,4096),('max_processes',1,8),('output_bytes',1024,16*1024*1024),('artifact_bytes',1024,256*1024*1024)]:
            value=getattr(self,name)
            if type(value) is not int or not low<=value<=high:raise ValueError('Invalid task limit: '+name)


def clean_environment(workspace):
    workspace=Path(workspace)
    result={key:os.environ[key] for key in ('SystemRoot','WINDIR','SYSTEMDRIVE','PATH','PATHEXT') if key in os.environ}
    result.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONUTF8='1',
                  PYTHONPATH=str(Path(__file__).resolve().parents[2]),
                  OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                  TEMP=str(workspace/'temp'),TMP=str(workspace/'temp'),HOME=str(workspace/'home'),USERPROFILE=str(workspace/'home'),
                  LOCALAPPDATA=str(workspace/'cache'),APPDATA=str(workspace/'config'),MPLCONFIGDIR=str(workspace/'cache'),MPLBACKEND='Agg',
                  RESEARCH_GUARDED_RUN=str(workspace))
    return result


class WorkerFailure(RuntimeError):
    """Worker process failed before producing a result; carries startup diagnostics.

    exit_code/phase/logs let callers distinguish host-environment failures
    (restricted token, broken venv launcher) from real computation failures.
    """
    def __init__(self,message,*,exit_code=None,phase=None,logs=None):
        self.exit_code=exit_code;self.phase=phase;self.logs=logs or {}
        self.error_type=None;self.error_code=None
        super().__init__(message)


def _decode_log(raw):
    """Worker logs may arrive in the console codepage; try plausible encodings."""
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):return raw.decode('utf-16')
    for encoding in ('utf-8','cp936','cp1252'):
        try:return raw.decode(encoding)
        except UnicodeDecodeError:continue
    return raw.decode('utf-8',errors='replace')


def _startup_diagnostics(workspace,details):
    """Bounded launcher/worker evidence; never infer permissions from an exit code."""
    result={**details,'phase':'before_worker_entry','logs':{}}
    try:
        path=safe_path(workspace/'startup-status.json',root=workspace)
        if io_path(path).is_file() and io_path(path).stat().st_size<=16384:
            document=json.loads(io_path(path).read_text(encoding='utf-8'))
            if isinstance(document,dict):result['worker_status']=document;result['phase']=document.get('phase','unknown')
    except (OSError,ValueError):result['status_read_error']=True
    for name in ('bootstrap-stdout.log','bootstrap-stderr.log','stderr.log'):
        try:
            path=safe_path(workspace/name,root=workspace)
            if not io_path(path).is_file():continue
            with io_path(path).open('rb') as stream:
                size=io_path(path).stat().st_size;stream.seek(max(0,size-4096));raw=stream.read(4096)
            result['logs'][name]={'tail':_decode_log(raw),'truncated':size>4096,'bytes':size}
        except (OSError,ValueError,UnicodeError):result['logs'][name]={'read_error':True}
    if result.get('worker_exit_code')==107 and result['phase']=='before_worker_entry':
        result['exit_hint']='CPython Windows venv launcher uses107 for pyvenv.cfg read/parse errors; inspect bootstrap-stderr.log. This is not a Win32 permission diagnosis.'
    return result


def run_worker(kind,request,*,directory=None,limits=None,cancel=None,cancel_file=None,include_receipt=False,operation_id=None):
    """Run one protected attempt, retaining typed failures and timing evidence."""
    timings=Timings();identifier=diagnostic_id()
    with recording(timings,identifier):
        try:return _run_worker(kind,request,directory=directory,limits=limits,cancel=cancel,cancel_file=cancel_file,
                               include_receipt=include_receipt,operation_id=operation_id,_timings=timings,_identifier=identifier)
        except BaseException as error:
            annotate(error,phase=timings.failed_stage,identifier=identifier)
            raise


def _run_worker(kind,request,*,directory,limits,cancel,cancel_file,include_receipt,operation_id,_timings,_identifier):
    """Run approved worker kinds only; never accept a model-provided command.

    Windows OS restrictions are mandatory. Other platforms fail closed rather
    than claiming the same protection without an implemented backend.
    """
    if kind not in ('tool','extension','elimination','probe'):raise ValueError('Unsupported worker kind')
    with measure('host.integrity_before'):core=assert_integrity()
    started_at=datetime.now(timezone.utc).isoformat()
    wall_started=time.monotonic()
    if os.name!='nt':raise RuntimeError('Protected execution currently requires Windows; no unprotected fallback is enabled')
    limits=limits or TaskLimits()
    encoded=json.dumps(request,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode('utf-8'))>256*1024:raise ValueError('Worker input exceeds 256KB')
    parent=safe_path(directory or Path.cwd()/'outputs'/'protected-tasks')
    if operation_id is not None and (not isinstance(operation_id,str) or not re.fullmatch('[0-9a-f]{32}',operation_id)):raise ValueError('Invalid host operation ID')
    workspace=parent/('task_'+(operation_id or uuid.uuid4().hex));workspace.mkdir(parents=True,exist_ok=False)
    request_file=workspace/'request.json';result_file=workspace/'result.json'
    from .windows import WindowsTask
    source_root=Path(__file__).resolve().parents[2]
    bootstrap='import time;_started=time.perf_counter();import sys;sys.path.insert(0,'+repr(str(source_root))+');from graph_research.runtime.entry import main;main(diagnostic_id='+repr(_identifier)+',bootstrap_started=_started)'
    argv=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,kind,str(request_file),str(result_file)]
    def prepare():
        with measure('host.request_preparation'):
            for name in ('temp','home','cache','config'):(workspace/name).mkdir()
            io_path(request_file).write_text(encoded,encoding='utf-8')
    def monitor():
        if cancel_file is not None and Path(cancel_file).exists():raise InterruptedError('Task cancelled by user')
        total=0
        for index,path in enumerate(io_path(workspace).rglob('*')):
            if index>512:raise RuntimeError('Task created too many files')
            # TOCTOU: the worker publishes staged temp files (link+unlink) and
            # antivirus may quarantine files mid-scan; a vanished file simply
            # contributes no bytes.
            try:
                if path.is_file():total+=path.stat().st_size
            except FileNotFoundError:continue
            if total>limits.artifact_bytes:raise RuntimeError('Task artifact size limit reached')
        try:
            if io_path(result_file).exists() and io_path(result_file).stat().st_size>limits.output_bytes:raise RuntimeError('Task result size limit reached')
        except FileNotFoundError:pass
    task=None;measurements={'available':False}
    startup={'host_phase':'preparing_restrictions','interpreter':sys.executable,'base_interpreter':getattr(sys,'_base_executable',None)}
    try:
        with measure('host.process_startup'):
            task=WindowsTask(argv,workspace,clean_environment(workspace),memory_mb=limits.memory_mb,cpu_seconds=limits.cpu_seconds,
                             max_processes=limits.max_processes,prepare=prepare,protected_paths=[CORE,*[CORE/name for name in inventory(CORE)],CORE/'_integrity.json'])
        startup.update(host_phase=task.startup_phase,process_id=task.process.pid,restricted_process_created=True,job_assigned=True)
        with measure('host.worker_wait'):code=task.wait(limits.wall_seconds,cancel,monitor)
        startup['worker_exit_code']=code
        startup['stage_seconds']=getattr(task,'startup_seconds',{})
        with measure('host.process_teardown'):task.close()
        measurements=getattr(task,'final_usage',{'available':False});task=None
        # The worker has exited; sweep staged temp files it could not unlink
        # itself (antivirus holds), so later directory scans and teardown
        # cleanup do not trip over them. Best-effort.
        for stale in io_path(workspace).glob('.*-*'):
            try:
                if stale.is_file():stale.unlink()
            except OSError:pass
        monitor()
        if not io_path(result_file).is_file():
            hint='; possible venv configuration error, inspect bootstrap-stderr.log' if code==107 else ''
            raise WorkerFailure(f'Protected worker exited without a complete result (code {code:#x}){hint}; diagnostics: {workspace / "execution.json"}',
                                exit_code=code,phase=startup.get('host_phase'))
        with measure('host.result_read'):payload=json.loads(io_path(result_file).read_text(encoding='utf-8'))
        if code or not payload.get('ok'):
            error=payload.get('error',f'Worker failed with exit code {code:#x}')
            if isinstance(error,dict):
                # Worker-reported failure: keep the original type/code, render once.
                failure=WorkerFailure(error.get('message','Calculation failed'),exit_code=code,phase='worker_reported')
                failure.error_type=error.get('type');failure.error_code=error.get('code')
                failure.error_details={key:error[key] for key in ('phase','exception_type','errno','winerror','cause_code','field_path','validation') if key in error}
                failure.diagnostic_id=_identifier
                raise failure
            raise RuntimeError(str(error))
        with measure('host.integrity_after'):assert_integrity()
        from .evidence import file_hash,output_inventory,environment_info
        with measure('host.evidence_preparation'):
            environment=environment_info();request_hash=file_hash(request_file);result_hash=file_hash(result_file);artifacts=output_inventory(workspace)
        startup=_startup_diagnostics(workspace,startup)
        child=startup.get('worker_status',{})
        if not child.get('timings'):child=payload.get('diagnostics',{})
        child_timing=bounded_timings(child.get('timings')) if isinstance(child,dict) and child.get('diagnostic_id')==_identifier else None
        receipt={'status':'complete','kind':kind,'protection':'windows_low_integrity_and_job','limits':limits.__dict__,
                 'started_at':started_at,'finished_at':datetime.now(timezone.utc).isoformat(),
                 'measurements':{**measurements,'host_elapsed_seconds':time.monotonic()-wall_started},
                 'startup':startup,
                 'core_manifest_sha256':core['manifest_sha256'],'environment':environment,
                 'tool_provenance':payload.get('tool_provenance'),
                 'diagnostic_id':_identifier,'timings':{'host':_timings.snapshot(),'worker':child_timing,
                    'scope':'Host snapshot ends before receipt publication. Worker final status includes result publication when available. Timings overlap across processes; do not add host.worker_wait and worker stages.'},
                 'request_sha256':request_hash,'result_sha256':result_hash,'artifacts':artifacts}
        atomic_text(workspace/'execution.json',json.dumps(receipt,ensure_ascii=False,allow_nan=False),overwrite=True)
        if include_receipt:
            return {'result':payload['result'],'execution':{'task_id':workspace.name,'directory':str(workspace),'receipt_sha256':file_hash(workspace/'execution.json'),'diagnostic_id':_identifier}}
        return payload['result']
    except BaseException as exc:
        # Failed/incomplete artifacts remain inspectable but never count as a
        # successful computation. Preserve the actual failure for the caller.
        if hasattr(exc,'protected_startup_phase'):startup['host_phase']=exc.protected_startup_phase
        diagnostics=_startup_diagnostics(workspace,startup)
        if isinstance(exc,WorkerFailure):
            # A worker-reported failure keeps its 'worker_reported' phase; the
            # startup-derived phase only fills in when the failure has none.
            if exc.phase is None:exc.phase=diagnostics.get('phase')
            if not exc.logs:exc.logs=diagnostics.get('logs',{})
        if hasattr(exc,'protected_startup_seconds'):diagnostics['stage_seconds']=exc.protected_startup_seconds
        detail=annotate(exc,phase=_timings.failed_stage or diagnostics.get('phase'),identifier=_identifier)
        exc.execution_directory=str(workspace);exc.startup_diagnostics=diagnostics
        from .evidence import environment_info,file_hash
        try:failure_environment=environment_info()
        except (OSError,ValueError):failure_environment={}
        failure_hashes={}
        for label,path in (('request_sha256',request_file),('result_sha256',result_file)):
            try:failure_hashes[label]=file_hash(path) if path.is_file() else None
            except OSError:failure_hashes[label]=None
        try:atomic_text(workspace/'execution.json',json.dumps({'status':'cancelled' if isinstance(exc,(InterruptedError,KeyboardInterrupt)) else 'failed',
                                                         'error':type(exc).__name__+': '+str(exc),'started_at':started_at,'finished_at':datetime.now(timezone.utc).isoformat(),
                                                         'error_details':detail,'diagnostic_id':_identifier,
                                                         'timings':{'host':_timings.snapshot(),'worker':bounded_timings(diagnostics.get('worker_status',{}).get('timings'))},
                                                         'core_manifest_sha256':core['manifest_sha256'],'environment':failure_environment,
                                                         **failure_hashes,
                                                         'startup':diagnostics,
                                                         'measurements':{**measurements,'host_elapsed_before_teardown_seconds':time.monotonic()-wall_started}}),overwrite=True)
        except Exception as receipt_error:
            exc.failure_receipt_error=annotate(receipt_error,phase='host.failure_receipt',identifier=_identifier)
        raise
    finally:
        if task is not None:task.close()


def run_tool(name,arguments,tool_directory,*,directory=None,limits=None,cancel=None,cancel_file=None,include_receipt=False,graph_inputs=None,research_refs=None,operation_id=None):
    """Public bounded calculation API used by the assistant and CLI."""
    from graph_research.tools.library import active_identity
    expected=active_identity(tool_directory,name)
    return run_worker('tool',{'name':name,'arguments':arguments,'tool_directory':str(Path(tool_directory).resolve()),**({'expected_tool':expected} if expected else {}),**({'graph_inputs':graph_inputs} if graph_inputs else {}),**({'research_refs':research_refs} if research_refs else {})},
                      directory=directory,limits=limits,cancel=cancel,cancel_file=cancel_file,include_receipt=include_receipt,operation_id=operation_id)
