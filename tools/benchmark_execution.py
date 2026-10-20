"""Sample real protected executions with per-stage receipts; no model/API calls."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from graph_research.runtime.runner import run_tool
from graph_research.runtime.storage import safe_path,read_json
from graph_research.runtime.observability import error_details
from graph_research.runtime.diagnostics import environment_report

CASES={
    'small-graph':('graph_invariants',{'kind':'path','n':5}),
    'matrix-spectrum':('graph_spectrum',{'kind':'complete','n':32}),
    'high-alpha':('hypergraph_spectrum',{'edges':[[0,1,2],[2,3,4],[3,5,6],[1,4,7]],'alpha':.999,'method':'auto','seed':42}),
    'batch-export':('graph_batch_study',{'cases':[{'name':'P'+str(n),'input':{'kind':'path','n':n}} for n in (3,4,5)],'calculations':['structure','spectrum','charpoly'],'plot':False})}


def distribution(values):
    ordered=sorted(values)
    return {'samples':len(values),'median_seconds':statistics.median(ordered),'p95_seconds':ordered[math.ceil(.95*len(ordered))-1],
            'min_seconds':ordered[0],'max_seconds':ordered[-1]}


def main():
    parser=argparse.ArgumentParser(description='阶段1性能采样：每个样本新建受保护进程，不使用缓存或放宽预算')
    parser.add_argument('--case',choices=['all',*CASES],default='all');parser.add_argument('--repeats',type=int,default=5)
    parser.add_argument('--output',help='新的采样目录，保留回执与原始结果')
    args=parser.parse_args()
    if not 1<=args.repeats<=20:parser.error('--repeats必须为1..20')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    output=safe_path(args.output or ROOT/'outputs/execution-profile'/stamp);output.mkdir(parents=True,exist_ok=False)
    environment=environment_report();core=ROOT/'graph_research/_integrity.json';core_hash=hashlib.sha256(core.read_bytes()).hexdigest()
    records=[];failed=False
    names=list(CASES) if args.case=='all' else [args.case]
    print('Sampling directory: '+str(output),flush=True)
    for name in names:
        tool,arguments=CASES[name]
        for index in range(args.repeats):
            item={'case':name,'sample':index+1,'tool':tool,'arguments':arguments};started=time.perf_counter()
            try:
                result=run_tool(tool,arguments,output/'empty-tools',directory=output/'runs',include_receipt=True)
                item['wall_seconds']=time.perf_counter()-started
                receipt_path=Path(result['execution']['directory'])/'execution.json';receipt=read_json(receipt_path)[0]
                if name=='small-graph' and result['result']['diameter']!=4:raise ValueError('Unexpected P5 diameter')
                if name=='matrix-spectrum' and abs(result['result']['rho']-31)>1e-8:raise ValueError('Unexpected K32 spectral radius')
                if name=='high-alpha' and not result['result']['verification']['passed']:raise ValueError('Spectrum certificate did not pass')
                if name=='batch-export' and result['result'].get('export_status')!='complete':raise ValueError('Batch export incomplete')
                item.update(status='complete',execution=result['execution'],timings=receipt.get('timings'),startup=receipt.get('startup',{}).get('stage_seconds'),
                            measurements=receipt['measurements'],result_sha256=receipt['result_sha256'])
            except Exception as error:
                item.update(status='failed',wall_seconds=time.perf_counter()-started,error=error_details(error),message=str(error));failed=True
            records.append(item)
            (output/'samples.json').write_text(json.dumps(records,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            print(f"{name} {index+1}/{args.repeats}: {item['status']} {item['wall_seconds']:.3f}s",flush=True)
            if failed:break
        if failed:break
    summaries={}
    for name in names:
        rows=[row for row in records if row['case']==name and row['status']=='complete']
        if not rows:continue
        stages={}
        for row in rows:
            for scope in ('host','worker'):
                for stage,values in ((row.get('timings') or {}).get(scope) or {}).get('stages',{}).items():
                    stages.setdefault(scope+':'+stage,[]).append(values['exclusive_seconds'])
        summaries[name]={'wall':distribution([row['wall_seconds'] for row in rows]),'stage_exclusive':{stage:distribution(values) for stage,values in sorted(stages.items())}}
    unchanged=hashlib.sha256(core.read_bytes()).hexdigest()==core_hash
    report={'format':'graph-research-execution-profile/1','status':'failed' if failed or not unchanged else 'recorded',
            'planned_samples':len(names)*args.repeats,'executed_samples':len(records),'failed_samples':sum(r['status']=='failed' for r in records),
            'unexecuted_samples':len(names)*args.repeats-len(records),'requested_repeats':args.repeats,
            'environment':environment,'core_manifest_sha256':core_hash,'core_manifest_unchanged':unchanged,
            'sampling':'Every sample starts a new protected worker. First sample is shown separately in samples.json; later samples may benefit from OS file caches, not process reuse.',
            'p95_method':'nearest rank; small samples do not establish a population P95','summaries':summaries,'samples':records,
            'timing_scope':'Host wait includes child work. Never add host and child durations; missing phases are unobserved, not zero. Tool body exclusive time includes unclassified non-math logic.',
            'real_model_requests':0}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'report':str(output/'report.json'),'status':report['status']},ensure_ascii=False),flush=True)
    return 1 if failed or not unchanged else 0


if __name__=='__main__':raise SystemExit(main())
