"""Official MCP SDK STDIO transport; stdout is exclusively protocol traffic."""
import asyncio
import base64
import json
import re
from graph_research.runtime.storage import io_path

from .contracts import GUIDE,INSTRUCTIONS,tool_definitions


def response_is_error(result):
    return result.get('status')=='protocol_error' or (result.get('request_effect',{}).get('operation') not in ('cancel','recover') and result.get('operation',{}).get('status')=='failed')


def create_server(runtime):
    """Construct only; no listener, worker, or model is started here."""
    from mcp.server import Server
    from mcp import types
    from mcp.shared.exceptions import MCPError
    from graph_research import __version__
    from graph_research.assistant.task_contract import contracts,TaskProtocolError

    async def list_tools(ctx,params):
        return types.ListToolsResult(tools=[types.Tool(name=d['name'],description=d['description'],input_schema=d['input_schema'],
            annotations=types.ToolAnnotations(read_only_hint=d['read_only'],destructive_hint=d['name']=='research_cancel',
                idempotent_hint=True,open_world_hint=runtime.configuration.model_settings is not None and d['name'] in ('research_submit','research_resume'))) for d in tool_definitions()])

    async def call_tool(ctx,params):
        result=await asyncio.to_thread(runtime.call,params.name,params.arguments if params.arguments is not None else {})
        return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False,allow_nan=False))],
            structured_content=result,is_error=response_is_error(result))

    async def list_resources(ctx,params):
        return types.ListResourcesResult(resources=[
            types.Resource(name='图论科研助手调用说明',uri='graph-research://guide',mime_type='text/plain',description='任务步骤、状态、结果查询和真实用户审批边界。'),
            types.Resource(name='图论子agent任务协议',uri='graph-research://contracts',mime_type='application/json',description='任务输入、返回与主agent操作的JSON Schema。')])

    async def list_templates(ctx,params):
        return types.ListResourceTemplatesResult(resource_templates=[
            types.ResourceTemplate(name='已有任务状态',uri_template='graph-research://tasks/{task_id}',mime_type='application/json'),
            types.ResourceTemplate(name='已登记结果附件',uri_template='graph-research://tasks/{task_id}/artifacts/{index}')])

    async def read_resource(ctx,params):
        uri=str(params.uri)
        if uri=='graph-research://guide':text=GUIDE
        elif uri=='graph-research://contracts':text=json.dumps(contracts(),ensure_ascii=False)
        elif re.fullmatch(r'graph-research://tasks/[0-9a-f]{32}',uri):
            result=await asyncio.to_thread(runtime.call,'research_get',{'task_id':uri.rsplit('/',1)[1]})
            if result.get('status')=='protocol_error':raise MCPError(-32602,result['error']['message'])
            text=json.dumps(result,ensure_ascii=False,allow_nan=False)
        else:
            match=re.fullmatch(r'graph-research://tasks/([0-9a-f]{32})/artifacts/([0-9]{1,5})',uri)
            if not match:raise MCPError(-32602,'资源URI无效；不能读取任意本机路径。')
            try:
                target,artifact=await asyncio.to_thread(runtime.artifact,match[1],int(match[2]))
                target=io_path(target)
                if target.stat().st_size>1024*1024:raise MCPError(-32602,'附件超过1MiB，请使用research_read_artifact分块读取。')
                raw=await asyncio.to_thread(target.read_bytes)
                import hashlib
                if hashlib.sha256(raw).hexdigest()!=artifact['sha256']:raise MCPError(-32602,'附件已变化，拒绝读取。')
            except (TaskProtocolError,OSError):raise MCPError(-32602,'没有可核验的该任务附件。') from None
            return types.ReadResourceResult(contents=[types.BlobResourceContents(uri=uri,mime_type=artifact.get('mime_type','application/zip'),blob=base64.b64encode(raw).decode('ascii'))])
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri,mime_type='text/plain' if uri.endswith('guide') else 'application/json',text=text)])

    return Server('graph-research',version=__version__,instructions=INSTRUCTIONS,on_list_tools=list_tools,on_call_tool=call_tool,
        on_list_resources=list_resources,on_list_resource_templates=list_templates,on_read_resource=read_resource,
        get_tool_input_schema=lambda name:runtime.schemas.get(name))


async def serve_stdio(runtime):
    from mcp.server.stdio import stdio_server
    from .user_actions import dispatch_user_actions
    from .approval_ui import ApprovalNotifier
    from contextlib import suppress

    notifier=ApprovalNotifier(runtime)
    async def user_actions():
        last_error=None
        while True:
            try:
                await asyncio.to_thread(dispatch_user_actions,runtime)
                await asyncio.to_thread(notifier.notify)
                last_error=None
            except Exception as error:
                # Delivery trouble must not stop MCP requests or echo paths,
                # task content or credentials into protocol traffic.
                import logging
                if last_error!=type(error).__name__:
                    logging.getLogger(__name__).warning('Native approval delivery unavailable (%s)',type(error).__name__)
                last_error=type(error).__name__
            await asyncio.sleep(.5)

    server=create_server(runtime)
    delivery=asyncio.create_task(user_actions())
    try:
        async with stdio_server() as (reader,writer):
            await server.run(reader,writer,server.create_initialization_options())
    finally:
        delivery.cancel()
        with suppress(asyncio.CancelledError):await delivery
