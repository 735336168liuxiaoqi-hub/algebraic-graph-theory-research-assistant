"""Trusted fixed startup probes; never a computation fallback or a model tool.

Compare the selected interpreter with its base runtime reading only the selected
venv's pyvenv.cfg. Both probes retain Windows low integrity, Job/UI/resource
limits and the exact standard-handle allowlist. No ACL/config edits or elevation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def _result_error(name,result,*,executable,prefix,parent):
    """Require evidence from this probe, not merely a successful process exit."""
    if not isinstance(result,dict):return 'probe_result_not_object'
    def same_path(value,expected):
        return isinstance(value,str) and bool(value) and Path(value).resolve()==Path(expected).resolve()
    if name=='selected_interpreter':
        if result.get('selected_python_reached') is not True:return 'selected_interpreter_not_reached'
        if not same_path(result.get('executable'),executable):return 'selected_interpreter_mismatch'
        if not same_path(result.get('prefix'),prefix):return 'selected_environment_mismatch'
    else:
        if result.get('readable') is not True or result.get('exists') is not True:return 'configuration_not_readable'
        if not same_path(result.get('path'),parent['path']):return 'configuration_path_mismatch'
        if parent.get('readable') is not True or result.get('sha256')!=parent.get('sha256'):
            return 'configuration_hash_unverified'
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    options=parser.parse_args()
    if os.name!='nt':raise RuntimeError('This fixed diagnostic requires Windows')
    from graph_research import __version__
    from graph_research.runtime.integrity import assert_integrity,CORE,inventory
    from graph_research.runtime.runner import clean_environment,_startup_diagnostics
    from graph_research.runtime.windows import WindowsTask
    from graph_research.runtime.storage import safe_path
    assert_integrity()
    output=safe_path(options.output or ROOT/'outputs/startup-diagnostics'/uuid.uuid4().hex[:12])
    output.mkdir(parents=True,exist_ok=False)
    config=Path(sys.prefix)/'pyvenv.cfg'
    parent={'path':str(config),'exists':config.is_file()}
    if config.is_file():
        try:parent.update(readable=True,sha256=hashlib.sha256(config.read_bytes()).hexdigest())
        except OSError as error:parent.update(readable=False,error=str(error))
    selected="import json,sys;from pathlib import Path;Path('probe.json').write_text(json.dumps({'selected_python_reached':True,'executable':sys.executable,'prefix':sys.prefix}),encoding='utf-8')"
    # The filename is chosen by the host, not by a task or remote model.
    base="""import hashlib,json
from pathlib import Path
path=Path(CONFIG)
record={'path':str(path),'exists':path.is_file()}
try:
    data=path.read_bytes()
    text=data.decode('utf-8-sig')
    record.update(readable=True,sha256=hashlib.sha256(data).hexdigest(),has_home=any(line.strip().startswith('home') and '=' in line for line in text.splitlines()))
except (OSError,UnicodeError) as error:
    record.update(readable=False,error=type(error).__name__+': '+str(error))
Path('probe.json').write_text(json.dumps(record),encoding='utf-8')
""".replace('CONFIG',repr(str(config)))
    records=[]
    protected=[CORE,*[CORE/name for name in inventory(CORE)],CORE/'_integrity.json']
    for name,executable,code in [('selected_interpreter',sys.executable,selected),
                                 ('restricted_base_config_read',getattr(sys,'_base_executable',sys.executable),base)]:
        directory=output/name;directory.mkdir();task=None
        row={'probe':name,'executable':executable,'protection':'windows_low_integrity_and_job','computation_fallback':False}
        try:
            task=WindowsTask([executable,'-I','-B','-X','utf8','-c',code],directory,clean_environment(directory),
                             memory_mb=128,cpu_seconds=5,protected_paths=protected)
            row.update(restricted_process_created=True,job_assigned=True,process_id=task.process.pid)
            row['worker_exit_code']=task.wait(10)
        except Exception as error:
            row.update(error=type(error).__name__+': '+str(error),host_phase=getattr(error,'protected_startup_phase','unknown'))
        finally:
            if task is not None:task.close();row['measurements']=task.final_usage
        row['startup']=_startup_diagnostics(directory,row)
        result=directory/'probe.json'
        try:
            row['result']=json.loads(result.read_text(encoding='utf-8'))
            result_error=_result_error(name,row['result'],executable=executable,prefix=sys.prefix,parent=parent)
        except FileNotFoundError:result_error='probe_result_missing'
        except (OSError,ValueError):result_error='probe_result_unreadable_or_invalid'
        if result_error:row['result_error']=result_error
        row['startup']['phase']=('fixed_probe_not_reached' if result_error=='probe_result_missing' else
                                 'fixed_probe_invalid_result' if result_error else 'fixed_probe_completed')
        row['status']='passed' if row.get('worker_exit_code')==0 and not result_error and 'error' not in row else 'failed'
        records.append(row)
    report={'version':__version__,'selected_interpreter':sys.executable,'base_interpreter':getattr(sys,'_base_executable',None),
            'parent_config':parent,'probes':records,'scope':'Diagnostic only; no permission changes or unprotected execution. Original failure requires same-context evidence.'}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'probes':[{k:r[k] for k in ('probe','status','worker_exit_code','result','result_error','error') if k in r} for r in records]},ensure_ascii=False,indent=2))
    return 0 if all(r['status']=='passed' for r in records) else 1


if __name__=='__main__':raise SystemExit(main())
