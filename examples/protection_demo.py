"""Offline protected runtime/recovery acceptance demo; never edits live core."""
import argparse
import json
from pathlib import Path
import sys
from threading import Event
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_research.runtime.runner import run_tool,run_worker,TaskLimits
from graph_research.runtime.integrity import verify,backup,restore
from graph_research.runtime.storage import safe_path,write_json


def main():
    parser=argparse.ArgumentParser(description='离线验证保护和恢复，不连接真实模型')
    parser.add_argument('--output',default='outputs/protection-v012-'+uuid.uuid4().hex[:8])
    root=safe_path(parser.parse_args().output);root.mkdir(parents=True,exist_ok=False)
    before=verify();canary=root/'outside-canary.txt';canary.write_text('preserve',encoding='utf-8')
    proof=run_worker('probe',{'operation':'native_write','path':str(canary)},directory=root/'tasks')
    assert proof['write_denied_by_os'] and canary.read_text()=='preserve'
    memory=run_worker('probe',{'operation':'memory'},directory=root/'tasks',limits=TaskLimits(memory_mb=64))
    assert memory['allocation_denied']
    try:run_worker('probe',{'operation':'sleep'},directory=root/'tasks',limits=TaskLimits(wall_seconds=0.5))
    except TimeoutError:timeout=True
    else:raise AssertionError('Expected timeout')
    stop=Event();stop.set()
    try:run_worker('probe',{'operation':'sleep'},directory=root/'tasks',cancel=stop)
    except InterruptedError:cancelled=True
    else:raise AssertionError('Expected cancellation')
    cases={
        'graph_invariants':{'kind':'path','n':4},
        'graph_spectrum':{'kind':'path','n':3},
        'exact_matrix_operation':{'matrix':[[1,2],[3,4]],'operation':'determinant'},
        'hypergraph_tensor_charpoly':{'edges':[[0,1,2]]},
        'tensor_charpoly':{'data':[[0,1],[1,0]]},
        'hypergraph_editor':{'edges':[[0,1,2],[2,3]]},
        'hypergraph_tikz':{'edges':[[0,1,2],[2,3]]},
        'graph_tikz':{'edges':[[0,1],[1,2]]},
        'hypergraph_plot':{'edges':[[0,1,2],[2,3]]},
    }
    results={name:run_tool(name,arguments,root/'packages',directory=root/'tasks') for name,arguments in cases.items()}
    assert results['graph_invariants']['diameter']==3
    assert abs(results['graph_spectrum']['rho']-2**0.5)<1e-10
    assert results['exact_matrix_operation']['determinant']=='-2'
    assert results['hypergraph_tensor_charpoly']['degree']==12 and results['tensor_charpoly']['degree']==2
    assert Path(results['hypergraph_editor']['editor']).is_file()
    for name in ('hypergraph_tikz','graph_tikz','hypergraph_plot'):
        assert all(Path(path).is_file() for path in results[name]['files'].values())
    archive=backup(root/'core-recovery.zip')
    recovered=restore(archive['archive'],archive['sha256'],root/'recovered-runtime')
    after=verify();assert after['ok'] and after['manifest_sha256']==before['manifest_sha256']
    report={'real_model_calls':0,'os_native_write_denied':True,'memory_limit_verified':True,'timeout_verified':timeout,
            'cancellation_verified':cancelled,'normal_tools_work_after_failures':True,'protected_tool_cases':list(results),
            'core_integrity_unchanged':True,'core_files_checked':after['files_checked'],'recovery_backup':archive,
            'fresh_copy_recovery':recovered,'tool_results':results}
    write_json(root/'validation.json',report)
    print(json.dumps({'report':str(root/'validation.json'),'protected_tool_cases_passed':len(results),
                      'os_write_and_limits_verified':True,'core_unchanged':True,'recovery_backup':archive},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
