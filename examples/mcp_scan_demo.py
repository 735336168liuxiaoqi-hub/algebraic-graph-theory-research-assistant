"""Official SDK alpha-scan acceptance; all computation is local and budgeted."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


async def run(root):
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    from graph_research.assistant.results import verify_bundle
    from graph_research.runtime.storage import write_json
    from graph_research import __version__
    parameters=StdioServerParameters(command=sys.executable,args=['-I','-X','utf8','-m','graph_research','mcp','--root',str(root/'state'),
        '--user','scan-demo','--results-root',str(root/'results'),'--max-tool-calls','12'])
    task={'version':1,'request_id':'loose-cycle-k4-scan-v030','objective':'六边4一致松圈α=0..1扫描',
          'execution':{'mode':'scan','scan':{'generator':{'family':'cycle','m':6,'k':4},'alphas':[i/10 for i in range(11)],'method':'auto'}},
          'constraints':{'max_tool_calls':12,'max_model_calls':0,'allow_extensions':False}}
    started=time.monotonic();polls=0
    async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=30) as client:
        response=await client.call_tool('research_submit',{'task':task,'wait_seconds':5});result=response.structured_content;identifier=result['task_id']
        deadline=time.monotonic()+90
        while not result.get('terminal') and time.monotonic()<deadline:
            response=await client.call_tool('research_get',{'task_id':identifier,'wait_seconds':5,'until':'terminal'});result=response.structured_content;polls+=1
        assert result['status']=='completed' and result['budget']['used']=={'model_calls':0,'tool_calls':12}
        assert result['summary']['scan']['successful_points']==11
        assert all(r['data']['verification']['passed'] for r in result['results'][1:])
        assert all('perron_vector' not in r.get('data',{}) for r in result['results'])
        bundle=result['artifacts'][0];assert verify_bundle(bundle['path'],bundle['sha256'])['ok']
        again=await client.call_tool('research_submit',{'task':task});assert again.structured_content['budget']['used']['tool_calls']==12
    report={'version':__version__,'official_sdk':True,'task_id':identifier,'status':result['status'],'usage':result['budget']['used'],
            'points':result['summary']['scan']['points'],'query_calls':polls,'end_to_end_client_seconds':time.monotonic()-started,
            'bundle':bundle,'bundle_verified':True,'same_request_reused':True,'real_model_requests':0}
    write_json(root/'report.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);options=parser.parse_args()
    from graph_research.runtime.storage import safe_path
    root=safe_path(options.output);root.mkdir(parents=True,exist_ok=False);asyncio.run(run(root))


if __name__=='__main__':main()
