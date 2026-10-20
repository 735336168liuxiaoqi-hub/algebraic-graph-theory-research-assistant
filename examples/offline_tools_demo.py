"""Exercise the real manual menu, with no model configuration or model SDK."""
import argparse
import json
from pathlib import Path
import sys
import uuid

from graph_research.assistant import OfflineToolSession,verify_bundle
from graph_research.assistant.offline import run_offline_console,grouped_tools
from graph_research.tools.change_control import core_fingerprint


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='outputs/offline-v016')
    options=parser.parse_args();out=Path(options.output).resolve();out.mkdir(parents=True,exist_ok=True)
    before=core_fingerprint();run=uuid.uuid4().hex[:8]
    parameter_file=out/'hypergraph-parameters.json'
    parameter_file.write_text(json.dumps({'edges':[[0,1],[1,2,3]]},ensure_ascii=False,indent=2),encoding='utf-8')
    session=OfflineToolSession(out/('session-'+run),out/('packages-'+run));transcript=[]
    answers=iter([
        '普通图','graph_invariants','2','','','4','','1','0',
        '超图','hypergraph_spectrum','4','{"edges":[[0,1,2],[2,3,4]],"alpha":0.3}','1','0',
        '矩阵','exact_matrix_operation','4','{"matrix":[[1,2],[3,4]],"operation":"determinant"}','1','0',
        '绘图、布局与LaTeX','hypergraph_tikz','3',str(parameter_file),'1','0','r','e','0',
    ])
    def receive(prompt):
        value=next(answers);transcript.append(prompt+value);return value
    run_offline_console(session,input_fn=receive,print_fn=transcript.append)
    observations=session.state['observations']
    assert len(observations)==4 and all(o['ok'] for o in observations),observations
    assert observations[0]['result']['diameter']==3
    assert observations[2]['result']['determinant']=='-2'
    assert session.result_bundle['summary']['verified_calls']==4
    verified=verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])
    assert verified['ok']
    groups=grouped_tools(session._registry())
    forbidden=('graph_research.assistant.model','graph_research.assistant.model_config','langgraph','httpx')
    assert not any(name in sys.modules for name in forbidden)
    assert core_fingerprint()==before
    (out/'console-transcript.txt').write_text('\n'.join(transcript),encoding='utf-8')
    report={'mode':'offline_tools','category_count':len(groups),'native_tool_count':sum(len(g['tools']) for g in groups),
            'model_calls':0,'model_configuration_and_sdks_loaded':False,'confirmed_tool_calls':4,
            'guided_example_customization_verified':True,'json_entry_verified':True,'parameter_file_import_verified':True,
            'numeric_hypergraph_spectrum_verified':True,'exact_matrix_verified':True,'nonuniform_hypergraph_tikz_verified':True,
            'result_bundle_verified':verified['ok'],'result_bundle':session.result_bundle,
            'core_unchanged':True,'session':str(session.directory)}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
