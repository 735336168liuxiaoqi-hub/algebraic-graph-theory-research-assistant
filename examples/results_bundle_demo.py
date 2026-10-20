"""Offline multi-request conversation: calculate, plot, eliminate and export."""
import argparse
import json
from pathlib import Path
import sys
import uuid
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_research.assistant import ResearchSession,verify_bundle
from graph_research.runtime.integrity import verify
from graph_research.runtime.storage import safe_path,write_json


class OfflineModel:
    def __init__(self,*decisions):self.decisions=list(decisions)
    def complete(self,messages):return self.decisions.pop(0)


def call(name,**arguments):return {'action':'call','tool':name,'arguments':arguments}
def final(text):return {'action':'final','answer':text}


def main():
    parser=argparse.ArgumentParser(description='多轮多次计算及结果包离线示例，不调用真实模型')
    parser.add_argument('--output',default='outputs/results-v013-'+uuid.uuid4().hex[:8])
    root=safe_path(parser.parse_args().output);root.mkdir(parents=True,exist_ok=False)
    before=verify()
    session=ResearchSession(root/'session',root/'packages')
    session.ask('计算三顶点路图P3的结构和邻接谱。',OfflineModel(
        call('graph_invariants',kind='path',n=3),call('graph_spectrum',kind='path',n=3),
        final('P3有3个顶点、2条边，直径为2；邻接谱数值约为sqrt(2)、0、-sqrt(2)，数值误差见原始结果。')))
    assert session.result_bundle and session.export_error is None
    edges=[[0,1],[1,2],[2,3],[3,0]]
    session.reply('再为四阶圈图C4出图，并导出LaTeX/TikZ。',OfflineModel(
        call('hypergraph_plot',edges=edges,vertices=[0,1,2,3],layout='circular'),
        call('graph_tikz',edges=edges,vertices=[0,1,2,3],positions=[{'vertex':0,'xy':[1,0]},{'vertex':1,'xy':[0,1]},{'vertex':2,'xy':[-1,0]},{'vertex':3,'xy':[0,-1]}]),
        final('C4的PNG/SVG和TikZ文件已生成。二元超边表示普通图的边；图表与代码均随结果包保存。')))
    session.reply('最后计算一条三元超边的邻接张量特征多项式。',OfflineModel(
        call('hypergraph_tensor_charpoly',edges=[[0,1,2]],matrix='A'),
        final('精确消元得到12次普通张量特征多项式，保留代数重数；具体展开式、因式分解和计算约定见原始结果。')))
    assert session.state['observations'][0]['result']['diameter']==2
    assert session.state['observations'][-1]['result']['degree']==12
    exported=session.export_results(root/'conversation-results.zip')
    one=session.export_results(root/'second-turn-results.zip',turn=2)
    checked=verify_bundle(exported['archive'],exported['sha256'])
    assert checked['summary']['turn_count']==3 and checked['summary']['verified_calls']==5 and checked['summary']['artifact_count']==4
    assert verify_bundle(one['archive'],one['sha256'])['summary']['turn_count']==1
    # This is our freshly generated, checksum-verified bundle. The preview is a
    # convenience for reviewing the portable HTML, not a general unzip API.
    preview=root/'preview';preview.mkdir()
    with zipfile.ZipFile(exported['archive']) as bundle:bundle.extractall(preview)
    assert verify()['manifest_sha256']==before['manifest_sha256']
    report={'real_model_calls':0,'multi_request_export_verified':True,'core_unchanged':True,
            'conversation_results':exported,'second_turn_results':one,'verification':checked,'preview':str(preview/'report.html')}
    write_json(root/'validation.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
