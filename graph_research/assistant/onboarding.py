"""Chinese setup/diagnostics and a persistent terminal research conversation."""
import argparse
import json
from pathlib import Path
import sys
import uuid

from .model_config import configuration_status,load_public_config,save_configuration,setup_wizard,load_settings


def model_command(arguments):
    parser=argparse.ArgumentParser(description='模型接入：配置向导、本地检查、一次最小连接测试')
    sub=parser.add_subparsers(dest='action',required=True)
    setup=sub.add_parser('setup',help='只配置公开信息，不保存密钥、不连接网络')
    for name in ('base-url','model','key-env'):setup.add_argument('--'+name)
    setup.add_argument('--mode',choices=['responses','chat_completions'])
    setup.add_argument('--auth',choices=['required','none'])
    setup.add_argument('--timeout',type=float)
    setup.add_argument('--max-output-tokens',type=int,help='高级选项：0表示不指定')
    setup.add_argument('--json-mode',choices=['on','off'])
    setup.add_argument('--chat-token-field',choices=['max_tokens','max_completion_tokens'])
    setup.add_argument('--config')
    for name in ('status','test'):
        command=sub.add_parser(name);command.add_argument('--config')
        if name=='test':command.add_argument('--max-output-tokens',type=int,default=128,help='一次测试的输出上限，默认128，可显式调整至16..4096')
    options=parser.parse_args(arguments)
    if options.action=='setup':
        edited=any(getattr(options,name) is not None for name in ('base_url','model','key_env','mode','auth','timeout','max_output_tokens','json_mode','chat_token_field'))
        if not edited:setup_wizard(options.config);return 0
        values=load_public_config(options.config)
        for name in ('base_url','model','key_env','mode','chat_token_field'):
            if getattr(options,name) is not None:values[name]=getattr(options,name)
        if options.auth is not None:values['auth_required']=options.auth=='required'
        if options.timeout is not None:values['timeout_seconds']=options.timeout
        if options.max_output_tokens is not None:values['max_output_tokens']=options.max_output_tokens or None
        if options.json_mode is not None:values['json_mode']=options.json_mode=='on'
        settings,path=save_configuration(values,options.config)
        print(json.dumps({'saved':True,'configuration_file':str(path),'saved_settings':settings.public(),
                          'request_url':settings.endpoint,'connection_tested':False,
                          'next_step':'运行model status核对生效配置；可选model test会发出一次短请求。'},ensure_ascii=False,indent=2))
        return 0
    if options.action=='status':
        report=configuration_status(options.config);print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['valid'] else 2
    # Only this explicit subcommand sends a diagnostic API request. Do not
    # silently retry, change providers, weaken TLS, or include research history.
    from .model import ConfiguredModel,ModelAPIError
    from .model_config import ModelConfigurationError
    print(f'将发送一次短JSON测试请求，最多请求{options.max_output_tokens}个输出token，可能产生少量服务商用量；不发送科研记录、不调用计算工具。',file=sys.stderr)
    try:
        settings=load_settings(options.config)
        print('实际测试目标：'+settings.endpoint+'；模型：'+settings.model,file=sys.stderr)
        report=ConfiguredModel(settings,prompt_for_key=True).test_connection(max_output_tokens=options.max_output_tokens)
    except (ModelAPIError,ModelConfigurationError) as exc:
        print(json.dumps({'ok':False,'error_code':getattr(exc,'code','configuration_error'),'message':str(exc),'automatic_retries':0},ensure_ascii=False,indent=2))
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0


def run_console(session,*,model_factory=None,input_fn=input,print_fn=print):
    """Keep an entered key only in the live model object across user requests."""
    model=None
    def get_model():
        nonlocal model
        if model is None:
            if model_factory is not None:model=model_factory()
            else:
                from .model import ConfiguredModel
                model=ConfiguredModel(prompt_for_key=True)
        return model
    print_fn('图论科研助手（独立模式，无需主agent）：输入研究问题即可开始；同一进程内无需反复输入密钥。')
    print_fn('命令：/退出、/查看、/导出、/继续、/执行计划 计划ID、/确认 评估ID、/拒绝 评估ID。确认开发前请阅读消耗评估。')
    print_fn('会话目录：'+str(session.directory))
    if session.state:print_fn(session.state.get('answer',''))
    while True:
        try:
            text=input_fn('你：').strip()
            if not text:continue
            if text in ('/退出','/exit'):break
            if text in ('/查看','/view'):
                print_fn('结果页面：'+session.view_results(open_browser=True)['html']);continue
            if text in ('/导出','/export'):
                result=session.export_results();print_fn('结果包：'+result['archive']);continue
            if text.startswith(('/拒绝 ','/reject ')):
                result=session.reject(text.split(maxsplit=1)[1].strip())
            elif text.startswith(('/确认 ','/approve ')):
                identifier=text.split(maxsplit=1)[1].strip()
                if session.state.get('status')!='awaiting_approval' or session.state.get('assessment_id')!=identifier:
                    print_fn('请明确指定当前等待确认的评估ID；尚未调用模型或批准开发。');continue
                result=session.approve(identifier,get_model())
            elif text.startswith('/执行计划 '):
                identifier=text.split(maxsplit=1)[1].strip();plan=session.state.get('plan',{})
                if session.state.get('status')!='awaiting_plan' or plan.get('id')!=identifier:
                    print_fn('请指定当前等待执行的计划ID。');continue
                result=session.accept_plan(identifier,plan['scope_sha256'],get_model())
            elif text=='/确认重算':
                result=session.retry_uncertain_calculation(get_model())
            elif text=='/用量':
                print_fn(json.dumps(session.workflow_usage(),ensure_ascii=False,indent=2));continue
            elif text in ('/继续','/continue'):
                if session.state.get('status') not in ('execution_error','cancelled','budget_exhausted'):
                    print_fn('当前没有待恢复的中断，请直接输入下一项需求。');continue
                result=session.continue_run(get_model())
            elif text.startswith('/'):
                print_fn('未识别的命令。可使用/退出、/查看、/导出、/继续、/确认 ID、/拒绝 ID。');continue
            else:
                selected=get_model()
                result=session.reply(text,selected) if session.state else session.ask(text,selected)
            print_fn('助手：'+result.get('answer',''))
            if result.get('status')=='recovery_required':print_fn('仅在检查记录并同意重新执行后输入：/确认重算。前次尝试继续计入预算。')
            if result.get('status')=='awaiting_plan':
                from .planning import plan_text
                print_fn(plan_text(result['plan']));print_fn('开始执行请输入：/执行计划 '+result['plan']['id']+'；也可直接回复修改需求。')
            if session.result_bundle:print_fn('对话结果包：'+session.result_bundle['archive'])
            if session.export_error:print_fn('计算记录已保留，结果打包未完成：'+session.export_error)
            if result.get('status')=='awaiting_approval':
                identifier=result['assessment_id']
                print_fn('确认开发请输入：/确认 '+identifier)
                print_fn('拒绝开发请输入：/拒绝 '+identifier)
        except (EOFError,KeyboardInterrupt):break
        except Exception as exc:print_fn('本次操作未完成：'+str(exc))
    print_fn('已退出；可通过会话目录恢复。密钥没有写入配置或科研记录。' if session.state else '已退出，未开始科研计算。')
    return 0


def chat_command(arguments):
    parser=argparse.ArgumentParser(description='独立科研助手，无需主agent：本机隐藏输入模型密钥，多轮自动打包结果；chat与standalone为同一入口')
    parser.add_argument('--session');parser.add_argument('--user');parser.add_argument('--memory-dir')
    parser.add_argument('--memory',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--config');parser.add_argument('--pricing')
    parser.add_argument('--results-root',help='成果保存目录；默认使用成果中心的设置')
    options=parser.parse_args(arguments)
    from .session import ResearchSession
    pricing=json.loads(Path(options.pricing).read_text(encoding='utf-8')) if options.pricing else None
    directory=Path(options.session) if options.session else Path.cwd()/'outputs'/('chat_'+uuid.uuid4().hex)
    from .result_catalog import ResultPreferences
    session=ResearchSession(directory,pricing=pricing,user_id=options.user,memory_directory=options.memory_dir,memory_enabled=options.memory,results_directory=options.results_root or ResultPreferences().active)
    session._require_model_mode()
    settings=load_settings(options.config)
    print('使用模型：'+settings.model+'；实际请求地址：'+settings.endpoint)
    from .model import ConfiguredModel
    return run_console(session,model_factory=lambda:ConfiguredModel(settings,prompt_for_key=True))


def connect_menu(*,input_fn=input,print_fn=print):
    """Local entry menu; no connection occurs merely by opening it."""
    while True:
        print_fn('\n图论科研助手（默认独立使用）')
        print_fn('自然语言科研对话需配置本助手的模型；接入主agent是可选的，不影响独立使用。')
        print_fn('1 配置模型（不保存密钥、不连接网络）')
        print_fn('2 检查配置（本地检查，不消耗API用量）')
        print_fn('3 测试连接（一次短请求，可能产生少量API用量）')
        print_fn('4 独立使用科研助手（持续对话、用户审批、结果自动打包）')
        print_fn('5 无API工具模式（按分类选择功能、填写参数，无需模型或密钥）')
        print_fn('0 退出')
        try:
            choice=input_fn('请选择：').strip()
            if choice=='0':return 0
            if choice=='1':setup_wizard(input_fn=input_fn,print_fn=print_fn)
            elif choice=='2':print_fn(json.dumps(configuration_status(),ensure_ascii=False,indent=2))
            elif choice=='3':model_command(['test'])
            elif choice=='4':
                user=input_fn('用户标识（用于隔离记忆，不是密钥；留空则不启用记忆）：').strip()
                chat_command(['--user',user] if user else [])
            elif choice=='5':
                from .offline import offline_command
                offline_command([],input_fn=input_fn,print_fn=print_fn)
            else:print_fn('请输入菜单中的编号。')
        except (EOFError,KeyboardInterrupt):return 0
        except Exception as exc:print_fn('操作未完成：'+str(exc))
