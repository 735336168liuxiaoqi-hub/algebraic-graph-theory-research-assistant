"""Trusted fixed entry for external-agent extension validation, without model keys."""
import sys
from graph_research.runtime.storage import read_json
from graph_research.runtime.runner import TaskLimits
from .development import from_host


def main():
    from graph_research.runtime.integrity import assert_integrity
    from pathlib import Path
    assert_integrity()
    job,_=read_json(sys.argv[1],max_bytes=16000)
    service=from_host(job['root'],job['user_id'],job['tool_directory'],TaskLimits(**job['limits']))
    if type(job.get('sequence')) is not int or job['sequence'] not in (1,2) or Path(sys.argv[1]).resolve()!=service.path(job['id'])/('job-'+str(job['sequence'])+'.json'):raise ValueError('Development job path differs from its host scope')
    service.execute(job['id'],job['reservation'])


if __name__=='__main__':main()
