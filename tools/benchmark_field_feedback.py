"""Paired local algorithm benchmark, same graph/precision/checker; no models."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);options=parser.parse_args()
    from graph_research.hypergraphs import HyperCycle
    from graph_research.runtime.runner import run_tool,TaskLimits
    from graph_research.runtime.storage import safe_path,write_json,read_json
    from graph_research.runtime.evidence import file_hash
    from graph_research import __version__
    root=safe_path(options.output);root.mkdir(parents=True,exist_ok=False);edges=HyperCycle(6,4).hyperedges();rows=[]
    for alpha in (0,.3,.6,.9):
        for method in ('iteration','auto'):
            started=time.monotonic();record=run_tool('hypergraph_spectrum',{'edges':edges,'alpha':alpha,'method':method},root/'tools',directory=root/'tasks',limits=TaskLimits(),include_receipt=True)
            result=record['result'];receipt_path=Path(record['execution']['directory'])/'execution.json';receipt,_=read_json(receipt_path)
            assert file_hash(receipt_path)==record['execution']['receipt_sha256'] and result['verification']['passed']
            rows.append({'alpha':alpha,'requested_method':method,'method':result['method'],'rho':result['rho'],'iterations':result['iterations'],
                         'wall_seconds':time.monotonic()-started,'measurements':receipt['measurements'],'execution':record['execution']})
    for alpha in (0,.3,.6,.9):
        pair=[r for r in rows if r['alpha']==alpha];assert abs(pair[0]['rho']-pair[1]['rho'])<1e-9
    report={'version':__version__,'rows':rows,'real_model_requests':0,
            'scope':'paired protected tool runs, same inputs/precision/independent checker; wall includes process startup, verification and receipt; not a model/token or human-time A/B'}
    write_json(root/'report.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
