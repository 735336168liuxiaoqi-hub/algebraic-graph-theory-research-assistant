"""Trusted local library management and explicit external-development approval."""
import argparse
import json
from graph_research.tools.library import ToolLibrary
from .development import from_host


def library_command(arguments):
    parser=argparse.ArgumentParser(description='持久扩展工具库；修改/审批仅供可信用户界面或本机用户执行')
    parser.add_argument('action',choices=['list','activate','disable','development-show','approve','reject'])
    parser.add_argument('--tool-dir');parser.add_argument('--root');parser.add_argument('--user')
    parser.add_argument('--name');parser.add_argument('--version');parser.add_argument('--development-id');parser.add_argument('--scope-sha256');parser.add_argument('--reason',default='用户拒绝')
    parser.add_argument('--query',default='');parser.add_argument('--limit',type=int,default=20);parser.add_argument('--offset',type=int,default=0)
    options=parser.parse_args(arguments)
    if options.action in ('development-show','approve','reject'):
        if not options.root or not options.user or not options.development_id:parser.error('开发管理需要--root、--user和--development-id')
        service=from_host(options.root,options.user,options.tool_dir)
        if options.action=='approve':
            if not options.scope_sha256:parser.error('请先查看评估，再用--scope-sha256确认当前范围')
            result=service.approve(options.development_id,options.scope_sha256)
        elif options.action=='reject':result=service.reject(options.development_id,options.reason)
        else:result=service.get(options.development_id)
    else:
        if not options.tool_dir:parser.error('工具库管理需要--tool-dir')
        library=ToolLibrary(options.tool_dir)
        if options.action=='list':result=library.catalog(options.query,options.limit,options.offset)
        else:
            if not options.name or not options.version:parser.error('启停/切换需要--name和精确--version')
            result=library.select(options.name,options.version,enabled=options.action=='activate')
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
