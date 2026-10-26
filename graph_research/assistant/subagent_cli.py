"""One-shot JSON transport and separately named trusted user-event CLI."""
import argparse
import json
from pathlib import Path
import sys

from .subagent import create_subagent
from .task_contract import contracts,PROTOCOL,TaskProtocolError


def main(command,arguments):
    if command=='subagent-schema':
        if arguments:raise TaskProtocolError('invalid_message','subagent-schema不接受额外参数。')
        print(json.dumps(contracts(),ensure_ascii=False,indent=2));return 0
    parser=argparse.ArgumentParser(description='本机子agent接口；--root和--user由可信宿主配置，不是网络认证')
    parser.add_argument('--root',required=True);parser.add_argument('--user',required=True)
    parser.add_argument('--confirm-experiments',action='store_true',help='可选：实验初审一次；反馈暂停由任务单独设置')
    parser.add_argument('--review-policy',choices=('bounded','always'),default=None,help=argparse.SUPPRESS)
    if command=='subagent':parser.add_argument('--input',help='父agent请求JSON文件；省略时从stdin读取，最多256KiB')
    else:
        parser.add_argument('--task',required=True);parser.add_argument('--interaction',required=True);parser.add_argument('--revision',required=True,type=int)
        parser.add_argument('--action',choices=['answer','approve','reject','continue','study-feedback'],required=True)
        parser.add_argument('--feedback',help='可信用户的study反馈JSON文件；不接受代码或扩大预算')
        parser.add_argument('--text');parser.add_argument('--assessment');parser.add_argument('--scope');parser.add_argument('--event-id')
    options=parser.parse_args(arguments)
    from .task_control import SubagentLimits
    parent,portal=create_subagent(options.root,user_id=options.user,limits=SubagentLimits(confirm_experiments=options.confirm_experiments or options.review_policy=='always'))
    if command=='subagent':
        if options.input:
            with Path(options.input).open('rb') as stream:raw=stream.read(256*1024+1)
        else:raw=sys.stdin.buffer.read(256*1024+1)
        if len(raw)>256*1024:raise TaskProtocolError('invalid_message','请求超过256KiB。')
        try:message=json.loads(raw)
        except ValueError:raise TaskProtocolError('invalid_message','输入不是合法JSON。') from None
        result=parent.dispatch(message)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 2 if result['status']=='protocol_error' else 0
    common=(options.task,options.interaction,options.revision)
    if options.action=='answer':event=portal.answer(*common,options.text,event_id=options.event_id)
    elif options.action=='continue':event=portal.continue_task(*common,event_id=options.event_id)
    elif options.action=='study-feedback':
        if not options.feedback:raise TaskProtocolError('feedback_missing','study-feedback需要--feedback JSON文件。')
        from graph_research.runtime.storage import read_json
        value,_=read_json(options.feedback,max_bytes=12000)
        event=portal.study_feedback(*common,value,event_id=options.event_id)
    else:
        if not options.assessment or not options.scope:raise TaskProtocolError('approval_scope_missing','批准/拒绝必须明确指定当前评估ID及scope_sha256。')
        if options.action=='approve':event=portal.approve(*common,options.assessment,options.scope,event_id=options.event_id)
        else:event=portal.reject(*common,options.assessment,options.scope,options.text or '用户拒绝本次开发',event_id=options.event_id)
    print(json.dumps({'protocol':PROTOCOL,'host_user_event':event,'next_step':'将event_id交给父接口resume。此命令没有继续调用模型或生成代码。'},ensure_ascii=False,indent=2))
    return 0
