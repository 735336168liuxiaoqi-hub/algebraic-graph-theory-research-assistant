"""Local STDIO launcher and non-mutating Codex/DSH connection snippets."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from .runtime import HostConfiguration,MCPResearchRuntime


def parser():
    result=argparse.ArgumentParser(description='图论科研助手本地MCP；身份、目录、权限由可信宿主固定')
    result.add_argument('--metrics',action='store_true',help='只读取本用户MCP调用成本日志，不启动服务或计算')
    result.add_argument('--diagnostic-id',help='配合--metrics按诊断编号查询安全错误元数据')
    result.add_argument('--root',required=True,help='本机持久化状态目录，建议使用短路径')
    result.add_argument('--user',required=True,help='宿主指定用户标识；不是登录认证')
    result.add_argument('--results-root',help='短成果目录；默认使用成果中心配置的位置')
    result.add_argument('--tool-dir',help='可信宿主选择的持久扩展库；可与桌面同目录，默认按MCP用户隔离')
    result.add_argument('--allow-development',action='store_true',help='允许主agent申请并提交新工具开发；不需要助手API，仍须用户确认和受保护验收')
    result.add_argument('--allow-agent',action='store_true',help='明确启用助手内部模型规划；默认只运行已有工具')
    result.add_argument('--allow-extensions',action='store_true',help='允许提出实验扩展申请；开发仍需真实用户审批')
    result.add_argument('--model-config',help='自主模型规划使用的公开配置；密钥只读环境变量')
    result.add_argument('--max-model-calls',type=int,default=None)
    result.add_argument('--max-tool-calls',type=int,default=10)
    result.add_argument('--allowed-tool',action='append',help='工具白名单，可重复指定')
    result.add_argument('--tool-seconds',type=float,default=30)
    result.add_argument('--tool-cpu-seconds',type=int,default=30)
    result.add_argument('--tool-memory-mb',type=int,default=1024)
    return result


def configuration(options):
    from graph_research.assistant.result_catalog import ResultPreferences
    settings=None
    if options.allow_agent:
        from graph_research.assistant.model_config import load_settings
        settings=load_settings(options.model_config).public()
    elif options.model_config or options.allow_extensions or options.max_model_calls not in (None,0):
        raise ValueError('模型配置、模型预算和扩展申请需要先显式启用--allow-agent。')
    return HostConfiguration(root=options.root,user_id=options.user,max_model_calls=(8 if options.allow_agent else 0) if options.max_model_calls is None else options.max_model_calls,
        max_tool_calls=options.max_tool_calls,allow_extensions=options.allow_extensions,allowed_tools=tuple(options.allowed_tool) if options.allowed_tool else None,
        tool_seconds=options.tool_seconds,tool_cpu_seconds=options.tool_cpu_seconds,tool_memory_mb=options.tool_memory_mb,model_settings=settings,
        results_directory=options.results_root or str(ResultPreferences().active),tool_directory=options.tool_dir,allow_development=options.allow_development)


def main(arguments):
    options=parser().parse_args(arguments);host=configuration(options)
    if options.diagnostic_id and not options.metrics:raise ValueError('--diagnostic-id需要配合--metrics，不启动服务')
    if options.metrics:
        from .telemetry import RPCTelemetry
        runtime=MCPResearchRuntime(host);telemetry=RPCTelemetry(runtime.directory)
        print(json.dumps(telemetry.diagnostic(options.diagnostic_id) if options.diagnostic_id else telemetry.report(),ensure_ascii=False,indent=2));return 0
    from .server import serve_stdio
    asyncio.run(serve_stdio(MCPResearchRuntime(host)))
    return 0


def connection_configuration(arguments):
    """Print reviewed snippets only; never edit another application's files."""
    command_parser=parser();command_parser.add_argument('--format',choices=['json','codex','dsh'],default='json')
    options=command_parser.parse_args(arguments);host=configuration(options)
    args=['-I','-X','utf8','-m','graph_research','mcp','--root',host.root,'--user',host.user_id,
          '--max-tool-calls',str(host.max_tool_calls),'--tool-seconds',str(host.tool_seconds),'--tool-cpu-seconds',str(host.tool_cpu_seconds),'--tool-memory-mb',str(host.tool_memory_mb)]
    if options.allow_agent:
        args+=['--allow-agent','--max-model-calls',str(host.max_model_calls)]
        if options.model_config:args+=['--model-config',str(Path(options.model_config).resolve())]
    if options.allow_extensions:args+=['--allow-extensions']
    if options.allow_development:args+=['--allow-development']
    if options.tool_dir:args+=['--tool-dir',str(Path(options.tool_dir).resolve())]
    if options.results_root:args+=['--results-root',str(Path(options.results_root).resolve())]
    for name in options.allowed_tool or []:args+=['--allowed-tool',name]
    command=str(Path(sys.executable).resolve());env_names=[host.model_settings['key_env']] if host.model_settings and host.model_settings['auth_required'] else []
    q=lambda value:json.dumps(value,ensure_ascii=False)
    if options.format=='codex':
        print('[mcp_servers.graph_research]\ncommand = '+q(command)+'\nargs = '+q(args)+'\nstartup_timeout_sec = 30\ntool_timeout_sec = 30')
        if env_names:print('env_vars = '+q(env_names))
    elif options.format=='dsh':
        print('- id: graph-research\n  name: "@deepseek-ai/dsh-mcp-client"\n  config:\n    serverName: graph_research\n    transport: stdio\n    command: '+q(command)+'\n    args: '+q(args)+'\n    toolCallTimeoutMs: 30000')
        if env_names:print('    env:\n'+''.join('      '+key+': !!js process.env.'+key+'\n' for key in env_names).rstrip())
    else:print(json.dumps({'name':'graph_research','transport':'stdio','command':command,'args':args,'forward_environment_names':env_names},ensure_ascii=False,indent=2))
    return 0
