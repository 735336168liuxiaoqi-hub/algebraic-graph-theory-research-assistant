"""One local/CI quality gate. Full tests use mocks and never bill model providers."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import json
import time
import uuid
from datetime import datetime,timezone


def seal_hint(root):
    """Point at the reseal step when reviewed source changed but the manifest did not.

    Advisory only: the integrity check below still decides pass/fail. This just
    keeps the next action visible so nobody 'fixes' it by deleting the manifest.
    """
    if not (root/'.git').exists():return
    probe=subprocess.run(['git','status','--porcelain','--','graph_research'],cwd=root,capture_output=True,text=True)
    if probe.returncode!=0:return
    changed=[line[3:] for line in probe.stdout.splitlines() if line[:2].strip()]
    if changed and 'graph_research/_integrity.json' not in changed:
        print('提示：受跟踪源码有变更，但 graph_research/_integrity.json 未更新；'
              '确认改动已审查后请运行 tools/seal_release.py 重新封存，并在提交信息中注明。',flush=True)


def preflight(root):
    """Run one real protected computation before the suite.

    A host that cannot start protected workers (restricted token, broken venv
    launcher) makes every worker-dependent test fail with the same root cause,
    drowning real signals. Classify that case and exit 2 — never 0, so CI and
    hooks cannot mistake a blocked environment for a green run. Genuine
    failures (integrity mismatch, wrong result) propagate as exit 1.
    """
    print('Checking: protected worker preflight',flush=True)
    workspace=Path(tempfile.mkdtemp(prefix='gate-preflight-'))
    try:
        from graph_research.runtime.runner import run_tool,WorkerFailure
        result=run_tool('graph_invariants',{'kind':'path','n':3},workspace/'tools',directory=workspace/'runs')
        if not isinstance(result,dict) or result.get('size')!=2:raise RuntimeError('Preflight returned an unexpected result: '+repr(result))
    except Exception as exc:
        # worker_reported means the protected process started fine and the tool
        # itself failed — a real failure, not an environment blockage.
        environmental=hasattr(exc,'protected_startup_phase') or \
            (isinstance(exc,WorkerFailure) and getattr(exc,'phase',None)!='worker_reported')
        if not environmental:raise
        diagnostics=getattr(exc,'startup_diagnostics',{}) or {}
        for name,entry in diagnostics.get('logs',{}).items():
            tail=entry.get('tail') if isinstance(entry,dict) else None
            if tail:print(f'--- {name} ---\n{tail}',flush=True)
        print('Preflight blocked: 受保护工作进程在当前宿主无法启动（常见于受限令牌或损坏的 venv 启动器），'
              '继续跑测试只会产生同一根因的噪音。请在普通终端或 CI 环境运行闸门。',flush=True)
        raise SystemExit(2)
    shutil.rmtree(workspace,ignore_errors=True)


def gate_modules(root):
    """Declared gate sets must match reality; unregistered modules fail closed."""
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    from tools.test_inventory import module_sets
    try:fast,full,_=module_sets(root)
    except ValueError as error:raise SystemExit(str(error)) from error
    return fast,full


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true')
    parser.add_argument('--strict-lock',action='store_true',help='要求与发行验证环境的依赖锁完全一致；用于CI和发版')
    parser.add_argument('--report-dir',help='保存用例清单及逐项结果的新验收目录')
    options=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    profile='full' if options.full else 'fast'
    report=Path(options.report_dir).resolve() if options.report_dir else root/'outputs/checks'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    if report==root/'graph_research' or report.is_relative_to(root/'graph_research'):raise ValueError('验收目录不能位于基础包中')
    report.mkdir(parents=True,exist_ok=True)
    summary_path=report/'checks-summary.json'
    if summary_path.exists():raise FileExistsError('验收目录已有记录，请选择新目录')
    summary={'format':'graph-research-checks/1','profile':profile,'strict_lock':options.strict_lock,'status':'running','commands':[]}
    def save():summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    def execute(arguments):
        row={'arguments':arguments,'status':'running'};summary['commands'].append(row);save();started=time.perf_counter()
        try:
            print('Checking: '+' '.join(arguments),flush=True)
            result=subprocess.run([sys.executable,'-X','utf8',*arguments],cwd=root,env=environment,check=True)
            row.update(status='passed',returncode=result.returncode)
        except subprocess.CalledProcessError as error:
            row.update(status='failed',returncode=error.returncode);raise
        finally:row['seconds']=time.perf_counter()-started;save()
    environment={**os.environ,'PYTHONUTF8':'1','QT_QPA_PLATFORM':'offscreen'}
    commands=[['-I','-m','graph_research','doctor'],['-m','pip','check'],
              ['-m','ruff','check','graph_research','tests','tools'],
              ['-m','graph_research','protect','check'],['tools/check_generated.py']]
    if options.strict_lock:commands.insert(2,['tools/check_dependency_lock.py'])
    tests=['tools/run_test_suite.py','--profile',profile,'--output',str(report),'--inventory',str(report/'test-inventory.json')]
    commands.append(tests)
    started=time.perf_counter();save();print('Acceptance directory: '+str(report),flush=True)
    try:
        seal_hint(root);gate_modules(root)
        execute(['tools/run_test_suite.py','--profile',profile,'--collect-only','--output',str(report)])
        summary['phase']='protected_preflight';save();preflight(root)
        for arguments in commands:
            summary['phase']=arguments[0];execute(arguments)
        if (root/'.git').exists():subprocess.run(['git','diff','--check'],cwd=root,check=True)
        summary['status']='passed';summary['returncode']=0
    except BaseException as error:
        code=error.code if isinstance(error,SystemExit) and type(error.code) is int else getattr(error,'returncode',1)
        summary.update(status='environment_blocked' if summary.get('phase')=='protected_preflight' and code==2 else 'failed',returncode=code,exception_type=type(error).__name__)
        raise
    finally:
        summary['seconds']=time.perf_counter()-started
        summary['artifacts']=[p.name for p in report.glob('*.json') if p!=summary_path]
        save()
    print('All checks passed'+(' (full suite)' if options.full else ' (fast regressions)'))


if __name__=='__main__':main()
