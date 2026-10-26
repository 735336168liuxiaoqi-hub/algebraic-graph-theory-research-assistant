import argparse
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import datetime


def _main():
    parser = argparse.ArgumentParser(description="原生Python图论科研助手")
    from graph_research import __version__
    parser.add_argument('--version',action='version',version='图论科研助手 '+__version__)
    parser.add_argument("command",nargs="?",default="demo",
                        choices=["doctor","demo","catalog","call","ask","resume","mcp","mcp-config","subagent","subagent-user","subagent-schema","connect","desktop","approvals","offline","standalone","chat","model","evaluate-api","view","export","verify-results","verify-spectrum","cancel","protect","extend","memory","experience","tool-library","check-model","edit","latex","docs"])
    args, rest = parser.parse_known_args()
    if args.command=='doctor':
        if rest:parser.error('doctor does not take extra arguments')
        from graph_research.runtime.diagnostics import environment_report
        result=environment_report();print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result['ok'] else 2
    if args.command=='protect':
        from graph_research.runtime.integrity import verify,backup,restore
        protect=argparse.ArgumentParser(description='校验、备份或恢复基础包；恢复仅写入新目录')
        sub=protect.add_subparsers(dest='action',required=True)
        sub.add_parser('check')
        p=sub.add_parser('backup');p.add_argument('--output',required=True)
        p=sub.add_parser('restore');p.add_argument('archive');p.add_argument('--sha256',required=True);p.add_argument('--destination',required=True)
        options=protect.parse_args(rest)
        result=verify() if options.action=='check' else backup(options.output) if options.action=='backup' else restore(options.archive,options.sha256,options.destination)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('ok') is False else 0
    if args.command=='cancel':
        from graph_research.runtime.storage import atomic_text
        if len(rest)!=1:parser.error('cancel requires a session directory')
        directory=Path(rest[0])
        if not (directory/'session.json').is_file():raise ValueError('Session does not exist')
        atomic_text(directory/'.cancel','cancel',overwrite=True)
        print('已请求取消。正在运行的计算进程树会停止；已保存的结果保留。')
        return 0
    from graph_research.runtime.integrity import assert_integrity
    assert_integrity()
    if args.command=='tool-library':
        from graph_research.assistant.library_cli import library_command
        return library_command(rest)
    if args.command=='experience':
        from graph_research.assistant.experience_cli import experience_command
        return experience_command(rest)
    if args.command=='verify-spectrum':
        from graph_research.hypergraphs.spectral_certificate import certificate_command
        return certificate_command(rest)
    if args.command in ('mcp','mcp-config'):
        from graph_research.mcp.cli import main as mcp_main,connection_configuration
        return mcp_main(rest) if args.command=='mcp' else connection_configuration(rest)
    if args.command=='evaluate-api':
        from graph_research.assistant.evaluation import evaluation_command
        return evaluation_command(rest)
    if args.command=='desktop':
        from graph_research.desktop.app import desktop_command
        return desktop_command(rest)
    if args.command=='approvals':
        from graph_research.desktop.task_approvals import approvals_command
        return approvals_command(rest)
    if args.command=='view':
        from graph_research.assistant import ResearchSession
        view=argparse.ArgumentParser(description='打开已记录结果的离线页面，不重新调用模型或计算工具')
        view.add_argument('session');view.add_argument('--open',action='store_true',help='同时在默认浏览器打开')
        options=view.parse_args(rest)
        print(json.dumps(ResearchSession(options.session).view_results(open_browser=options.open),ensure_ascii=False,indent=2));return 0
    if args.command=='offline':
        from graph_research.assistant.offline import offline_command
        return offline_command(rest)
    if args.command in ('subagent','subagent-user','subagent-schema'):
        from graph_research.assistant.subagent_cli import main as subagent_main
        from graph_research.assistant.task_contract import TaskProtocolError,PROTOCOL
        try:return subagent_main(args.command,rest)
        except TaskProtocolError as exc:
            print(json.dumps({'protocol':PROTOCOL,'status':'protocol_error','error':{'code':exc.code,'message':str(exc)}},ensure_ascii=False));return 2
    if args.command=='connect':
        from graph_research.assistant.onboarding import connect_menu
        if rest:parser.error('connect does not take extra arguments')
        return connect_menu()
    if args.command=='model':
        from graph_research.assistant.onboarding import model_command
        return model_command(rest)
    if args.command in ('standalone','chat'):
        from graph_research.assistant.onboarding import chat_command
        return chat_command(rest)
    if args.command=='check-model':
        from graph_research.assistant.model_config import configuration_status
        report=configuration_status()
        print(json.dumps({**{name:bool(os.environ.get(name)) for name in ('RESEARCH_MODEL','RESEARCH_BASE_URL','RESEARCH_API_KEY','RESEARCH_API_MODE')},
                          'diagnostics':report},ensure_ascii=False,indent=2))
        return 0 if report['valid'] else 2
    if args.command=='verify-results':
        from graph_research.assistant.results import verify_bundle
        verify=argparse.ArgumentParser(description='只读校验科研结果包，不解压、不执行、不调用模型')
        verify.add_argument('archive');verify.add_argument('--sha256')
        options=verify.parse_args(rest)
        print(json.dumps(verify_bundle(options.archive,options.sha256),ensure_ascii=False,indent=2))
        return 0
    if args.command=='export':
        from graph_research.assistant import ResearchSession
        export=argparse.ArgumentParser(description='导出整次对话或指定一轮的科研结果，不调用模型')
        export.add_argument('session');export.add_argument('--output');export.add_argument('--turn',type=int)
        export.add_argument('--allow-incomplete',action='store_true',help='明确允许缺失/变更附件的降级导出，并记录警告')
        options=export.parse_args(rest)
        session=ResearchSession(options.session)
        print(json.dumps(session.export_results(options.output,turn=options.turn,allow_incomplete=options.allow_incomplete),ensure_ascii=False,indent=2))
        return 0
    if args.command == "demo":
        from graph_research.experiments.workflow import main as demo
        sys.argv = ["graph-research demo",*rest]
        return demo()
    if args.command == "edit":
        from graph_research.hypergraphs import Hypergraph
        editor = argparse.ArgumentParser(description="离线超图布局编辑器")
        editor.add_argument("input",nargs="?",help="包含edges/vertices的JSON，或已保存的布局JSON；省略时使用示例")
        editor.add_argument("--output",default="outputs/hypergraph-editor/editor.html")
        editor.add_argument("--positions",help="为输入超图加载已有布局JSON")
        editor.add_argument("--seed",type=int,default=42)
        editor.add_argument("--layout",choices=["spring","circular"],default="spring")
        editor.add_argument("--no-open",action="store_true",help="仅生成文件，不打开浏览器")
        editor.add_argument('--overwrite',action='store_true',help='明确允许覆盖已有导出文件')
        options = editor.parse_args(rest)
        if options.input:
            data = json.loads(Path(options.input).read_text(encoding="utf-8-sig"))
            if data.get("format")=="graph-research-layout":
                graph = Hypergraph.from_layout(options.input)
            else:
                graph = Hypergraph(data["edges"],vertices=data.get("vertices"),weights=data.get("weights"))
        else:
            graph = Hypergraph([[0,1,2],[2,3],[3,4,5,6]],vertices=list(range(8)))
        if options.positions:
            graph.load_pos(options.positions)
        path = graph.edit_layout(options.output,seed=options.seed,layout=options.layout,open_browser=not options.no_open,overwrite=options.overwrite)
        print(f"编辑器：{path}")
        print("拖动顶点后点击“保存坐标”；下载的JSON可用h.load_pos(path)加载。")
        return 0
    if args.command == "latex":
        from graph_research.hypergraphs import Hypergraph
        exporter = argparse.ArgumentParser(description="将图或保存的布局转换成LaTeX/TikZ")
        exporter.add_argument("input",help="包含edges/vertices的JSON或编辑器保存的布局JSON")
        exporter.add_argument("--output")
        exporter.add_argument("--fragment",action="store_true",help="仅导出tikzpicture片段")
        exporter.add_argument("--simple-graph",action="store_true",help="简单图：全部二元边，统一黑色")
        exporter.add_argument("--edge-labels",action="store_true")
        exporter.add_argument("--no-labels",action="store_true")
        exporter.add_argument('--overwrite',action='store_true')
        options = exporter.parse_args(rest)
        data = json.loads(Path(options.input).read_text(encoding="utf-8-sig"))
        if data.get('format')=='graph-research-graph':
            from graph_research.graph_input.document import GraphDocument
            from graph_research.rendering.presentation import document_to_tikz
            from graph_research.runtime.storage import atomic_text
            drawing=GraphDocument(data)
            if options.simple_graph and drawing.graph_type!='graph':raise ValueError('--simple-graph与输入图类型不一致。')
            style={**drawing.to_dict().get('style',{}),'edge_labels':options.edge_labels,'vertex_labels':not options.no_labels};drawing=drawing.with_updates(style=style)
            stem='graph' if drawing.graph_type=='graph' else 'hypergraph';target=Path(options.output or ('outputs/'+stem+('-tikz.tex' if options.fragment else '.tex')))
            if target.suffix.lower()!='.tex':raise ValueError('TikZ输出文件需使用.tex扩展名。')
            atomic_text(target,document_to_tikz(drawing,standalone=not options.fragment),overwrite=options.overwrite);print('LaTeX：'+str(target));return 0
        graph = Hypergraph.from_layout(options.input) if data.get("format")=="graph-research-layout" else Hypergraph(data["edges"],vertices=data.get("vertices"),weights=data.get("weights"))
        colors = None
        if options.simple_graph:
            if any(len(e)!=2 for e in graph.Edges):
                raise ValueError("简单图要求每条边恰好包含两个顶点")
            colors = ['black']*graph.size()
        stem='graph' if options.simple_graph else 'hypergraph'
        path = graph.save_tikz(options.output or ('outputs/'+stem+('-tikz.tex' if options.fragment else '.tex')),standalone=not options.fragment,
                              edge_labels=options.edge_labels,vertex_labels=not options.no_labels,edge_colors=colors,overwrite=options.overwrite)
        print(f"LaTeX：{path}")
        return 0
    if args.command == 'memory':
        from graph_research.assistant.memory import UserMemoryStore
        memory=argparse.ArgumentParser(description='按用户查看或管理本地记忆，不调用模型')
        memory.add_argument('action',choices=['show','set','forget','clear','enable','disable'])
        memory.add_argument('key',nargs='?');memory.add_argument('value',nargs='?')
        memory.add_argument('--user',required=True,help='应用提供的稳定用户标识；不是登录验证')
        memory.add_argument('--memory-dir',help='默认：主目录下.graph_research/user_memory')
        options=memory.parse_args(rest)
        if options.action=='set' and (options.key is None or options.value is None):memory.error('set requires KEY VALUE')
        if options.action=='forget' and (options.key is None or options.value is not None):memory.error('forget requires KEY only')
        if options.action not in ('set','forget') and (options.key is not None or options.value is not None):memory.error('This action takes no KEY or VALUE')
        store=UserMemoryStore(options.memory_dir)
        if options.action=='set':
            try:value=json.loads(options.value)
            except json.JSONDecodeError:value=options.value
            store.set_preference(options.user,options.key,value,source='cli')
        elif options.action=='forget':store.forget(options.user,options.key)
        elif options.action=='clear':store.clear(options.user)
        elif options.action in ('enable','disable'):store.set_enabled(options.user,options.action=='enable')
        print(json.dumps(store.profile(options.user),ensure_ascii=False,indent=2))
        return 0
    from graph_research.tools.registry import ToolRegistry
    from graph_research.tools.extensions import ToolStore
    registry = ToolRegistry()
    store = ToolStore(Path.cwd()/"tool_packages")
    if args.command == "ask":
        from graph_research.assistant.model import ConfiguredModel
        from graph_research.assistant.session import ResearchSession
        ask=argparse.ArgumentParser(description='提出科研需求，必要时先澄清和评估，等待人工确认')
        ask.add_argument('question',nargs='+');ask.add_argument('--session');ask.add_argument('--pricing',help='可选：每百万输入/输出token单价JSON，不含密钥')
        ask.add_argument('--user',help='稳定用户标识；指定后默认启用本地记忆')
        ask.add_argument('--memory-dir',help='可选的本地记忆目录')
        ask.add_argument('--model-config',help='可选：公开模型配置文件；不含密钥')
        ask.add_argument('--results-root',help='成果保存目录；默认使用成果中心的设置')
        ask.add_argument('--memory',action=argparse.BooleanOptionalAction,default=None,help='为此次会话启用/禁用记忆；启用需指定用户')
        options=ask.parse_args(rest)
        output=Path(options.session) if options.session else Path.cwd()/'outputs'/('agent_'+uuid.uuid4().hex)
        pricing=json.loads(Path(options.pricing).read_text(encoding='utf-8')) if options.pricing else None
        from graph_research.assistant.result_catalog import ResultPreferences
        session=ResearchSession(output,store.directory,pricing,user_id=options.user,memory_directory=options.memory_dir,memory_enabled=options.memory,results_directory=options.results_root or ResultPreferences().active)
        session._require_model_mode()
        result=session.ask(' '.join(options.question),ConfiguredModel(config_path=options.model_config,prompt_for_key=True))
        _show_session(session,result)
        return 0
    if args.command == 'resume':
        from graph_research.assistant.session import ResearchSession
        resume=argparse.ArgumentParser(description='继续已有会话；批准动作仅接受宿主用户明确指定评估ID')
        resume.add_argument('session');action=resume.add_mutually_exclusive_group(required=True)
        action.add_argument('--reply');action.add_argument('--approve');action.add_argument('--reject');action.add_argument('--continue',dest='continue_run',action='store_true')
        resume.add_argument('--reason',default='用户拒绝此次功能开发')
        resume.add_argument('--user',help='核对会话所属用户；省略时沿用会话绑定')
        resume.add_argument('--model-config')
        resume.add_argument('--memory',action=argparse.BooleanOptionalAction,default=None)
        options=resume.parse_args(rest);session=ResearchSession(options.session,user_id=options.user,memory_enabled=options.memory)
        session._require_model_mode()
        if options.reject:result=session.reject(options.reject,options.reason)
        else:
            from graph_research.assistant.model import ConfiguredModel
            model=ConfiguredModel(config_path=options.model_config,prompt_for_key=True)
            result=session.reply(options.reply,model) if options.reply is not None else session.approve(options.approve,model) if options.approve else session.continue_run(model)
        _show_session(session,result)
        return 0
    for error in store.load_into(registry):print('扩展已隔离：'+error['package']+'；'+error['error'],file=sys.stderr)
    if args.command == "catalog":
        catalog = argparse.ArgumentParser(description="查看工具调用契约，不执行计算")
        catalog.add_argument("--tool",help="仅查看指定工具的完整说明")
        catalog.add_argument("--detail",choices=["full","model","index"],default="full")
        options = catalog.parse_args(rest)
        value = registry.describe(options.tool) if options.tool else registry.catalog(detail=options.detail)
        print(json.dumps(value,ensure_ascii=False,indent=2))
    elif args.command == "docs":
        from graph_research.tools.contracts import export_documentation
        docs = argparse.ArgumentParser(description="从同一来源生成模型JSON目录与功能手册")
        docs.add_argument("--output",default="docs/model")
        options = docs.parse_args(rest)
        print(json.dumps(export_documentation(registry,options.output),ensure_ascii=False,indent=2))
    elif args.command == "call":
        if len(rest) != 2: parser.error("call requires TOOL_NAME and JSON_ARGUMENTS")
        from graph_research.runtime.runner import run_tool
        print(json.dumps(run_tool(rest[0],json.loads(rest[1]),store.directory),ensure_ascii=False,indent=2))
    elif args.command == "extend":
        from graph_research.assistant.session import ResearchSession
        if len(rest)!=1:parser.error('extend requires a requirements assessment JSON, not executable source')
        request=json.loads(Path(rest[0]).read_text(encoding='utf-8-sig'))
        output=Path.cwd()/'outputs'/('agent_'+uuid.uuid4().hex)
        session=ResearchSession(output,store.directory)
        assessment=session.changes.assess(request,registry)
        if assessment['kind']=='composition':print(assessment['message']);return 0
        session.state={'question':request['goal'],'conversation':[],'assessment':assessment,'assessment_id':assessment['id'],
                       'status':'awaiting_approval','answer':session.changes.approval_card(assessment)}
        session._save();_show_session(session,session.state)
    return 0


def _show_session(session,result):
    print(result.get('answer',''));print(f'会话记录：{session.directory}')
    if session.result_bundle:
        print('对话结果包：'+session.result_bundle['archive'])
        print('结果包SHA256：'+session.result_bundle['sha256'])
    if session.export_error:print('结果已保留，但本轮结果打包未完成：'+session.export_error,file=sys.stderr)
    if result.get('status')=='awaiting_clarification':
        print(f'补充需求：python -m graph_research resume "{session.directory}" --reply "你的补充"')
    if result.get('status')=='awaiting_approval':
        identifier=result['assessment_id']
        print(f'确认开发：python -m graph_research resume "{session.directory}" --approve {identifier}')
        print(f'拒绝开发：python -m graph_research resume "{session.directory}" --reject {identifier}')


def main():
    try:
        return _main()
    except ModuleNotFoundError as exc:
        extras = {'matplotlib':'visual','jsonschema':'tools','langgraph':'assistant','httpx':'assistant','PySide6':'desktop','mcp':'mcp','mcp_types':'mcp'}
        name = (exc.name or '').split('.')[0]
        if name not in extras: raise
        print(f"当前功能需要可选依赖{name}。请安装此发行包的[{extras[name]}]依赖；完整科研助手使用[all]。",file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"操作未完成：{type(exc).__name__}: {exc}",file=sys.stderr)
        return 2
