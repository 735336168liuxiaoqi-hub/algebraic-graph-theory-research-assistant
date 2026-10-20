"""Fixed trusted background entry; calculation itself uses protected workers."""
import os
from pathlib import Path
import sys
import time

from graph_research.runtime.storage import safe_path,read_json,write_json,exclusive_lock
from graph_research.runtime.integrity import assert_integrity,IntegrityError
from .runtime import HostConfiguration
from graph_research.runtime.observability import error_details
from graph_research.errors import TaskProtocolError


def run_job(path):
    path=safe_path(path)
    with exclusive_lock(path.with_suffix('.lock')):
        job,_=read_json(path,max_bytes=32768)
        if job.get('state')!='queued':return
        configuration=HostConfiguration.from_public(job['configuration']);parent=configuration.parent()
        expected=safe_path(parent._service.directory/'mcp/jobs'/(job['job_id']+'.json'))
        if path!=expected:raise ValueError('Worker job path does not match its host scope')
        stage='integrity_check'
        try:
            assert_integrity()
            stage='execution_lock'
            with exclusive_lock(parent._service.directory/'mcp/.execution.lock'):
                stage='task_driver'
                job.update(state='running',started_at=time.time(),pid=os.getpid());write_json(path,job)
                result=parent.start_queued(job['task_id']) if job['operation']=='start' else parent.resume(job['task_id'],job['event_id'],preserve_cancel=True)
                job.update(state='finished',finished_at=time.time(),result_revision=result.get('revision'),result_status=result.get('status'),error=result.get('error') if result.get('status')=='protocol_error' else None)
                write_json(path,job)
        except TaskProtocolError as error:
            job.update(state='finished',finished_at=time.time(),error={'code':error.code,'message':str(error),'retryable':False,**error_details(error,phase=stage)})
            write_json(path,job)
        except Exception as error:
            detail=({'code':'core_integrity_failed','retryable':False,'message':'核心完整性校验失败；请恢复已验证运行版本，不自动封存或重算。'}
                    if isinstance(error,IntegrityError) else {'code':'worker_interrupted','retryable':False,'message':'后台执行中断；已有记录已保留，请查询任务并恢复，不自动重试。'})
            job.update(state='interrupted',finished_at=time.time(),error={**detail,'stage':stage,**error_details(error,phase=stage)})
            write_json(path,job)


def main():
    if len(sys.argv)!=2:raise ValueError('A fixed host job file is required')
    run_job(Path(sys.argv[1]))


if __name__=='__main__':main()
