"""Execute exactly the collected IDs; keep skipped/failed/blocked separate."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import unittest
from functools import partial

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_inventory import collect,source_files,fingerprint


class EvidenceResult(unittest.TextTestResult):
    def __init__(self,*args,journal=None,**kwargs):
        super().__init__(*args,**kwargs);self.outcomes={};self.active={};self.fixture_events=[];self.subtest_events=[]
        self.journal=journal

    def startTest(self,test):
        self.active[test.id()]=time.perf_counter();self.outcomes[test.id()]={'id':test.id(),'status':'incomplete'}
        super().startTest(test)

    def event(self,test,status,reason=None):
        target=self.outcomes.get(test.id())
        if target is None:self.fixture_events.append({'id':test.id(),'status':status,'reason':reason});return
        if target['status'] not in ('failed','error'):target['status']=status
        if reason:target['reason']=reason

    def addSuccess(self,test):super().addSuccess(test);self.event(test,'passed')
    def addFailure(self,test,error):super().addFailure(test,error);self.event(test,'failed',error[0].__name__)
    def addError(self,test,error):super().addError(test,error);self.event(test,'error',error[0].__name__)
    def addSkip(self,test,reason):super().addSkip(test,reason);self.event(test,'skipped',reason)
    def addExpectedFailure(self,test,error):super().addExpectedFailure(test,error);self.event(test,'expected_failure',error[0].__name__)
    def addUnexpectedSuccess(self,test):super().addUnexpectedSuccess(test);self.event(test,'unexpected_success')

    def addSubTest(self,test,subtest,error):
        super().addSubTest(test,subtest,error)
        if error:
            status='failed' if issubclass(error[0],test.failureException) else 'error'
            self.event(test,status,error[0].__name__)
            self.subtest_events.append({'id':test.id(),'subtest':str(subtest),'status':status,'exception_type':error[0].__name__})

    def stopTest(self,test):
        self.outcomes[test.id()]['seconds']=max(0.0,time.perf_counter()-self.active.pop(test.id()))
        if self.journal is not None:
            with self.journal.open('a',encoding='utf-8') as stream:stream.write(json.dumps(self.outcomes[test.id()],ensure_ascii=False)+'\n')
        super().stopTest(test)


def protected_worker_state():
    """Probe the low-integrity launcher once and record the verdict.

    A host may broker or deny the creation of a low-integrity child. That is a
    missing environment capability, not a product defect, so it is recorded
    explicitly: a run inside such a host is never read as many product failures.
    """
    started=time.perf_counter()
    record={'checked_at':datetime.now(timezone.utc).isoformat(),'platform':os.name,
            'protection':'windows_low_integrity_and_job'}
    if os.name!='nt':
        return {**record,'status':'unsupported','code':'non_windows',
                'hint':'Protected execution is only verified on Windows; protected cases are not product evidence here.'}
    import shutil,tempfile
    code=("import json,sys;from pathlib import Path;"
          "Path('probe.json').write_text(json.dumps({'executable':sys.executable,'prefix':sys.prefix}),encoding='utf-8')")
    task=None;directory=None
    try:
        from graph_research.runtime.runner import clean_environment
        from graph_research.runtime.windows import WindowsTask
        directory=Path(tempfile.mkdtemp(prefix='protected-preflight-'))
        task=WindowsTask([sys.executable,'-I','-B','-X','utf8','-c',code],directory,clean_environment(directory),
                         memory_mb=128,cpu_seconds=5)
        exit_code=task.wait(15)
        reached=(directory/'probe.json').is_file()
        record.update(exit_code=exit_code,worker_reached_python=reached,seconds=round(time.perf_counter()-started,3))
        if exit_code==0 and reached:
            record.update(status='available',code=None)
        else:
            record.update(status='unavailable',
                          code='venv_configuration_unreadable' if exit_code in (107,0x6b) else 'worker_startup_failed',
                          hint='A low-integrity child cannot read the venv configuration or standard library in this host context; '
                               'protected cases cannot be judged here. Run the suite from an ordinary terminal or CI, not a restricted sandbox.')
    except Exception as error:
        record.update(status='unavailable',code='probe_failed',error=type(error).__name__+': '+str(error),
                      host_phase=getattr(error,'protected_startup_phase','unknown'),seconds=round(time.perf_counter()-started,3),
                      hint='The preflight probe could not create a protected process at all; inspect host_phase before treating protected cases as failures.')
    finally:
        if task is not None:
            try:task.close()
            except Exception:pass
        if directory is not None:
            try:shutil.rmtree(directory,ignore_errors=True)
            except (Exception,SystemExit):pass
    return record


def main():
    parser=argparse.ArgumentParser(description='统一测试清单与逐项结果，包含已登记根目录测试')
    parser.add_argument('--profile',choices=('fast','full'),default='full')
    parser.add_argument('--collect-only',action='store_true');parser.add_argument('--output',required=True)
    parser.add_argument('--inventory',help='先前收集的清单；执行前必须逐项及源码哈希一致')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    output=Path(args.output).resolve()
    if any(output==p or output.is_relative_to(p) for p in (root/'graph_research',root/'dist/runtimes')):parser.error('报告不能写入基础包或固定运行副本')
    output.mkdir(parents=True,exist_ok=True);os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    try:suite,inventory=collect(root,args.profile)
    except Exception as error:
        with (output/'collection-error.json').open('x',encoding='utf-8') as stream:
            json.dump({'status':'collection_failed','exception_type':type(error).__name__,'message':str(error)},stream,ensure_ascii=False,indent=2)
        raise
    target=output/'test-inventory.json'
    if args.inventory:
        expected=json.loads(Path(args.inventory).read_text(encoding='utf-8'))
        if any(expected.get(key)!=inventory[key] for key in ('profile','test_ids','source_sha256','core_manifest_sha256')):
            raise ValueError('测试清单或源码自收集后变化，停止验收，不执行旧快照')
        inventory_path=Path(args.inventory)
    else:
        with target.open('x',encoding='utf-8') as stream:json.dump(inventory,stream,ensure_ascii=False,indent=2)
        inventory_path=target
    print(f"Collected {inventory['collected_tests']} tests: tests/={inventory['tests_directory_count']}, root={inventory['root_count']}; IDs SHA256={inventory['test_ids_sha256']}",flush=True)
    if args.collect_only:return 0
    environment=protected_worker_state()
    (output/'environment.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
    if environment.get('status')!='available':
        print(f"受保护worker不可用（{environment.get('status')}/{environment.get('code')}）：本上下文中依赖低完整性启动的用例无法判定，"
              f"其失败不构成产品缺陷证据；请改在普通终端或CI执行。详见 {output/'environment.json'}",file=sys.stderr,flush=True)
    else:
        print(f"Protected worker preflight: available (exit 0, {environment.get('seconds')}s)",flush=True)
    journal=output/'test-progress.jsonl'
    with journal.open('x',encoding='utf-8'):pass
    started=time.perf_counter();result=unittest.TextTestRunner(verbosity=1,resultclass=partial(EvidenceResult,journal=journal)).run(suite)
    rows=[result.outcomes.get(identifier,{'id':identifier,'status':'not_run'}) for identifier in inventory['test_ids']]
    counts={status:sum(row['status']==status for row in rows) for status in ('passed','failed','error','skipped','expected_failure','unexpected_success','incomplete','not_run')}
    changed=fingerprint(source_files(root))!=inventory['source_sha256']
    successful=result.wasSuccessful() and not changed and not counts['not_run'] and not counts['incomplete']
    report={'format':'graph-research-test-results/1','finished_at':datetime.now(timezone.utc).isoformat(),
            'status':'passed' if successful else 'failed','profile':args.profile,'collected_tests':len(rows),'started_tests':result.testsRun,
            'counts':counts,'seconds':time.perf_counter()-started,'source_changed_during_execution':changed,
            'test_inventory_sha256':hashlib.sha256(inventory_path.read_bytes()).hexdigest(),'source_sha256':inventory['source_sha256'],
            'tests':rows,'fixture_events':result.fixture_events,'subtest_events':result.subtest_events,
            'meaning':'Collected total includes skipped tests. Fixture errors and subtest failures are separate; environmental errors are not counted as passes.'}
    with (output/'test-results.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    if changed:print('Source changed during tests; acceptance failed even if test assertions passed.',file=sys.stderr)
    return 0 if successful else 1


if __name__=='__main__':raise SystemExit(main())
