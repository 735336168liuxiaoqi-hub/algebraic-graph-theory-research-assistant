"""Create a genuine result-page example, including a deliberately failed call."""
import argparse
import json
from pathlib import Path
import uuid

from graph_research.assistant import OfflineToolSession,verify_bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/results-ui-v017')
    options=parser.parse_args();out=Path(options.output).resolve();out.mkdir(parents=True,exist_ok=True)
    session=OfflineToolSession(out/('session-'+uuid.uuid4().hex[:8]),out/'packages')
    calls=[('graph_invariants',{'kind':'path','n':4}),
           ('graph_spectrum',{'kind':'path','n':4}),
           ('matrix_analysis',{'matrix':[[2,1,0],[1,2,1],[0,1,2]]}),
           ('graph_characteristic_polynomial',{'kind':'path','n':4}),
           ('hypergraph_plot',{'edges':[[0,1,2],[2,3],[3,4,5]],'edge_labels':True}),
           ('graph_tikz',{'edges':[[0,1],[1,2],[2,3]]})]
    for name,arguments in calls:
        result=session.call_tool(name,arguments)
        assert result['ok'],result
    failed=session.call_tool('graph_invariants',{'kind':'edges','n':2,'edges':[[0,2]]})
    assert not failed['ok']
    assert verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok']
    view=session.view_results()
    report={'mode':'offline','model_calls':0,'successful_calculations':len(calls),'deliberate_failure_examples':1,
            'session':str(session.directory),'view':view,'result_bundle':session.result_bundle}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
