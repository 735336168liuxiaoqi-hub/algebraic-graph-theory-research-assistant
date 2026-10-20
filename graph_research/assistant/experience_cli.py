"""Trusted local experience capture/review; never register these as model tools."""
import argparse
import json

from .experience import ExperienceStore,search_experiences,read_experience
from .experience_evidence import capture_call
from .subagent import create_subagent


def experience_command(arguments):
    """Manage derived cases; approval binds the exact inspected content hash."""
    parser=argparse.ArgumentParser(description='科研经验管理；仅可信宿主在用户实际审阅后调用，MCP只开放读取')
    parser.add_argument('action',choices=['list','show','capture','review','forget','clear'])
    parser.add_argument('--root',required=True);parser.add_argument('--user',required=True)
    parser.add_argument('--id');parser.add_argument('--task');parser.add_argument('--call')
    parser.add_argument('--query',default='');parser.add_argument('--tool');parser.add_argument('--status',choices=['candidate','approved','rejected'])
    parser.add_argument('--limit',type=int,default=10);parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--content-sha256');parser.add_argument('--decision',choices=['approve','reject']);parser.add_argument('--note',default='')
    options=parser.parse_args(arguments)
    parent,_=create_subagent(options.root,user_id=options.user);service=parent._service;directory=service.memory_directory
    if options.action=='list':result=search_experiences(directory,options.user,options.query,tool=options.tool,limit=options.limit,offset=options.offset,reviewed_only=False,status=options.status)
    elif options.action=='show':
        if not options.id:parser.error('show requires --id')
        result=read_experience(directory,options.user,options.id,reviewed_only=False)
    elif options.action=='capture':
        if not options.task or not options.call:parser.error('capture requires --task and --call')
        result=capture_call(service,options.task,options.call)
    elif options.action=='review':
        if not options.id or not options.content_sha256 or not options.decision:parser.error('review requires --id, --content-sha256 and --decision')
        result=ExperienceStore(directory).review(options.user,options.id,options.content_sha256,'approved' if options.decision=='approve' else 'rejected',options.note)
    elif options.action=='forget':
        if not options.id:parser.error('forget requires --id')
        result=ExperienceStore(directory).forget(options.user,options.id)
    else:result=ExperienceStore(directory).clear(options.user)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
