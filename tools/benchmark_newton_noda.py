"""User-run frozen pilot benchmark; no model/API calls or holdout access.

Each invocation creates a new output directory, preserving all unsuccessful
fixed points in the denominator. Direct Python is the default; --protected
additionally exercises the existing Windows resource/isolation backend.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',choices=['pilot','unresolved'],default='pilot')
    parser.add_argument('--method',choices=['newton_noda','auto','iteration'],default='newton_noda')
    parser.add_argument('--max-iterations',type=int,default=20000)
    parser.add_argument('--tolerance',type=float,default=1e-11)
    parser.add_argument('--include-endpoint',action='store_true')
    parser.add_argument('--protected',action='store_true')
    parser.add_argument('--output',type=Path)
    options=parser.parse_args()
    from graph_research import __version__
    from graph_research.tools import ToolRegistry
    from graph_research.runtime.integrity import assert_integrity
    from graph_research.runtime.storage import safe_path
    assert_integrity()
    fixture=ROOT/'tests/data'/('high_alpha_pilot.json' if options.cases=='pilot' else 'high_alpha_unresolved.json')
    payload=fixture.read_bytes();cases=json.loads(payload)['cases']
    output=safe_path(options.output or ROOT/'outputs/newton-noda'/('run-'+uuid.uuid4().hex[:12]))
    output.mkdir(parents=True,exist_ok=False)
    registry=ToolRegistry();records=[];submissions=[];started=time.perf_counter()
    fixed=sum(len(c['alphas']) for c in cases);total=fixed+(len(cases) if options.include_endpoint else 0)
    metadata={'version':__version__,'method':options.method,'fixture_sha256':hashlib.sha256(payload).hexdigest(),
              'tolerance':options.tolerance,'max_iterations':options.max_iterations,'fixed_points':fixed,'total_requested_points':total,
              'execution':'protected' if options.protected else 'direct_python','model_calls':0,'holdout_read':False}
    def save():
        documents={'report.json':{**metadata,'completed_points':len(records),'successful_points':len(submissions),
                                 'failed_points':sum(r['status']!='success' for r in records),'wall_seconds':time.perf_counter()-started,'records':records},
                   'submissions.json':{'results':submissions}}
        for name,data in documents.items():
            target=output/name;temporary=output/(name+'.tmp')
            temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            temporary.replace(target)
    save()
    for case in cases:
        for alpha in case['alphas']+([case['endpoint_alpha']] if options.include_endpoint else []):
            args={'edges':case['edges'],'alpha':float(alpha),'method':options.method,'tolerance':options.tolerance,'max_iterations':options.max_iterations}
            row={'case_id':case['case_id'],'alpha':alpha,'input_sha256':case['input_sha256']};begin=time.perf_counter();cpu=time.process_time()
            try:
                if options.protected:
                    from graph_research.runtime.runner import run_tool,TaskLimits
                    receipt=run_tool('hypergraph_spectrum',args,ROOT/'tool_packages',directory=output/'tasks',limits=TaskLimits(),include_receipt=True)
                    result=receipt['result'];row['execution_receipt']=receipt
                else:result=registry.call('hypergraph_spectrum',args)
                if result.get('verification',{}).get('passed') is not True:raise ArithmeticError('Independent certificate unavailable or failed')
                row.update(status='success',result=result)
                submissions.append({**result,'case_id':case['case_id'],'alpha':alpha,'input_sha256':case['input_sha256']})
            except Exception as error:
                row.update(status='unresolved',error=type(error).__name__+': '+str(error))
                if hasattr(error,'execution_directory'):row['execution_directory']=error.execution_directory
                if hasattr(error,'startup_diagnostics'):row['startup']=error.startup_diagnostics
            row.update(wall_seconds=time.perf_counter()-begin,host_process_cpu_seconds=time.process_time()-cpu)
            records.append(row);save()
            print(f"{len(records)}/{total} {case['case_id']} alpha={alpha}: {row['status']}",flush=True)
    print(json.dumps({'output':str(output.resolve()),'successful_points':len(submissions),'requested_points':total},ensure_ascii=False))
    return 0 if len(submissions)==total else 1


if __name__=='__main__':raise SystemExit(main())
