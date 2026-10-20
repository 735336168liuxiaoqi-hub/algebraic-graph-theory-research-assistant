"""End-to-end local MCP demonstration using the official client; no model API."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from graph_research import __version__
from graph_research.assistant import verify_bundle
from graph_research.runtime.storage import atomic_text


async def run(root,user,protocol='legacy'):
    parameters=StdioServerParameters(command=sys.executable,args=['-I','-X','utf8','-m','graph_research','mcp','--root',str(Path(root).resolve()),'--user',user,'--results-root',str(Path(root).resolve()/'results')])
    task={'version':1,'request_id':'mcp-demo-p3-spectrum-rank','objective':'计算P3邻接谱并复核矩阵秩',
          'execution':{'mode':'tools','steps':[{'id':'spectrum','tool':'graph_spectrum','arguments':{'kind':'path','n':3}},
               {'id':'rank','tool':'matrix_analysis','arguments':{},'bindings':{'matrix':{'step':'spectrum','path':['matrix']}}}]},
          'constraints':{'max_model_calls':0,'max_tool_calls':2,'allow_extensions':False}}
    async with Client(parameters,mode=protocol,cache=None,read_timeout_seconds=30) as client:
        tools=await client.list_tools();catalog=await client.call_tool('research_catalog',{})
        started=time.monotonic();submitted=await client.call_tool('research_submit',{'task':task});submit_seconds=time.monotonic()-started
        if submitted.is_error:raise RuntimeError(submitted.structured_content)
        task_id=submitted.structured_content['task_id'];deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            response=await client.call_tool('research_get',{'task_id':task_id,'wait_seconds':2});result=response.structured_content
            if response.is_error:raise RuntimeError(result)
            if not result.get('transport',{}).get('active'):break
        if result['status']!='completed':raise RuntimeError(result)
        value=await client.call_tool('research_inspect_result',{'task_id':task_id,'call_id':'call-0002','path':['rank']})
        assert value.structured_content['value']==2
        archive=result['artifacts'][0];assert verify_bundle(archive['path'],archive['sha256'])['ok']
    async with Client(parameters,mode=protocol,cache=None,read_timeout_seconds=30) as client:
        duplicate=await client.call_tool('research_submit',{'task':task});reused=duplicate.structured_content
        assert reused['task_id']==task_id and reused['budget']['used']['tool_calls']==2
    return {'version':__version__,'official_sdk_client':True,'protocol_mode':protocol,'mcp_tools':len(tools.tools),
            'native_tools':len(catalog.structured_content['tools']),'submit_seconds':submit_seconds,'task_id':task_id,'status':result['status'],
            'matrix_rank':value.structured_content['value'],'usage':result['budget']['used'],'bundle':archive,
            'bundle_verified':True,'same_request_across_reconnection_reused':True,'real_api_requests':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--user',default='mcp-demo')
    parser.add_argument('--protocol',choices=['legacy','auto'],default='legacy');parser.add_argument('--output',default='outputs/mcp-demo/report.json')
    options=parser.parse_args();report=asyncio.run(run(options.root,options.user,options.protocol))
    atomic_text(options.output,json.dumps(report,ensure_ascii=False,indent=2)+'\n',overwrite=True);print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
