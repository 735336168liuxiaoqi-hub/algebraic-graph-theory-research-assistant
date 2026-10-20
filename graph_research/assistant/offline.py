"""Human-selected tools, schema-guided input and durable results; no model.

This module never imports a model adapter/configuration or sends an HTTP
request. Calculations use the same protected workers and result evidence as
the assistant. It cannot generate or install new algorithms.
"""
import argparse
import copy
import json
from pathlib import Path
import uuid

import jsonschema

from graph_research.runtime.runner import TaskLimits, run_tool
from graph_research.tools.input_guides import input_guide,show_input_guide
from .session import ResearchSession, _session_action

GROUPS=('普通图','有向图','超图','张量','矩阵','组合与多项式','绘图、布局与LaTeX','已安装的实验工具','其他已有工具')
DRAWING={'hypergraph_plot','hypergraph_editor','hypergraph_tikz','graph_tikz','hypergraph_schematic','combinatorial_plot','graph_layout'}
ENUM_LABELS={'path':'路径图 / 松路','cycle':'圈 / 松圈','star':'星图 / 超星','complete':'完全图','empty':'空图',
             'edges':'自定义边表','spring':'弹簧布局','circular':'圆周布局','A':'邻接','L':'Laplacian','Q':'无符号Laplacian',
             'alpha':'α矩阵 / 张量','rref':'行最简形','inverse':'逆矩阵','determinant':'行列式','charpoly':'特征多项式'}


def grouped_tools(registry):
    """Group the live registry; descriptions/schemas stay in the reviewed source."""
    groups={key:[] for key in GROUPS}
    for tool in registry.tools.values():
        name=tool.name
        if tool.status!='native_tested':category='已安装的实验工具'
        elif name in DRAWING:category='绘图、布局与LaTeX'
        elif name.startswith('directed_'):category='有向图'
        elif name.startswith('hypergraph_') or name=='generate_hypergraph':category='超图'
        elif name.startswith('graph_') or name in ('matching_polynomial','compare_graphs','weighted_graph_spectrum'):category='普通图'
        elif name.startswith('tensor_'):category='张量'
        elif name in ('matrix_analysis','exact_matrix_operation','quotient_matrix','integer_linear_system','block_matrix_analysis'):category='矩阵'
        elif name in ('polynomial_roots','combinatorial_calculation','linear_recurrence','symbolic_analysis'):category='组合与多项式'
        else:category='其他已有工具'
        groups[category].append(registry.describe(name))
    return [{'name':key,'tools':value} for key,value in groups.items() if value]


def _strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('JSON中存在重复字段：'+key)
            result[key]=value
        return result
    def invalid(_):raise ValueError('不能使用NaN或Infinity')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=invalid)


def read_arguments(path):
    """Read a bounded data file, never Python expressions or code."""
    with Path(path).expanduser().open('rb') as stream:raw=stream.read(256*1024+1)
    if len(raw)>256*1024:raise ValueError('参数文件不能超过256KiB')
    value=_strict_json(raw.decode('utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('参数文件应是一个JSON对象，例如{"kind":"path","n":3}')
    return value


def validation_message(exc):
    path='参数'+''.join(f'[{part}]' if isinstance(part,int) else '.'+part for part in exc.absolute_path)
    rules={'type':'数据类型不符合要求','required':'缺少必填字段','additionalProperties':'包含未定义字段',
           'minimum':'小于允许的最小值','maximum':'超过允许的最大值','minItems':'数据项不足','maxItems':'数据项过多',
           'enum':'请使用列出的选项','anyOf':'数据不符合允许的格式','oneOf':'数据不符合允许的格式'}
    return path+'：'+rules.get(exc.validator,'不符合参数约束')+'；请核对工具说明。'


class OfflineToolSession(ResearchSession):
    """A separate manual workspace. Never turn model/approval sessions into one."""
    def __init__(self,directory,tool_directory=None,*,user_id=None,memory_directory=None,memory_enabled=None,limits=None,results_directory=None):
        super().__init__(directory,tool_directory,user_id=user_id,memory_directory=memory_directory,memory_enabled=memory_enabled,results_directory=results_directory,results_mode='offline')
        if (self.state or self.turns or (self.directory/'session.json').exists()) and self.task_context.get('interaction_mode')!='offline_tools':
            raise ValueError('该目录属于其他会话；请为无API模式选择新目录，避免改变原会话或审批。')
        self.task_context={'interaction_mode':'offline_tools','model_calls':0}
        self.limits=limits or TaskLimits()

    @_session_action
    def call_tool(self,name,arguments,*,cancel_event=None,graph_inputs=None):
        """Validate first, then record one human-requested protected calculation."""
        registry=self._registry()
        if name not in registry.tools:raise ValueError('未登记的工具，不能在无API模式执行：'+str(name))
        definition=registry.describe(name)
        if not definition['availability']['available']:raise ValueError('此工具缺少可选依赖，请先安装['+definition['availability']['install_extra']+']；没有执行计算。')
        if not isinstance(arguments,dict):raise ValueError('参数必须是JSON对象')
        encoded=json.dumps(arguments,allow_nan=False)
        if len(encoded)>100000:raise ValueError('参数超过工具入口的100000字符上限')
        arguments=json.loads(encoded)
        jsonschema.validate(arguments,definition['parameters'])
        if graph_inputs:
            from graph_research.graph_input.adapters import validate_bindings
            graph_inputs=validate_bindings(definition,arguments,graph_inputs)
            if len(json.dumps({'arguments':arguments,'graph_inputs':graph_inputs},ensure_ascii=False).encode('utf-8'))>240*1024:raise ValueError('图输入来源与计算参数过大，请缩小批量或简化标签后再执行。')
        text='手动调用 '+name+'\n参数：'+json.dumps(arguments,ensure_ascii=False,allow_nan=False)
        if graph_inputs:text+='\n图输入与编号对照（资料）：'+json.dumps(graph_inputs,ensure_ascii=False,allow_nan=False)
        if not self.turns:
            self.state={'question':'无API模式：按分类手动调用已有工具','conversation':[],'observations':[]}
        self.state['conversation']=self.state.get('conversation',[])+[{'role':'user','content':text}]
        self._begin_turn(text);self._cancel.clear();(self.directory/'.cancel').unlink(missing_ok=True)
        self.state.update(status='running',answer='正在执行所选工具；模型调用为0。')
        self._save()
        observation={'tool':name,'arguments':arguments,'tool_status':registry.tools[name].status}
        if graph_inputs:observation['graph_inputs']=copy.deepcopy(graph_inputs)
        try:
            if cancel_event is not None and cancel_event.is_set():raise InterruptedError('用户取消了本次计算')
            value=run_tool(name,arguments,self.store.directory,directory=self.directory/'tasks',limits=self.limits,
                           cancel=cancel_event if cancel_event is not None else self._cancel,cancel_file=self.directory/'.cancel',include_receipt=True,**({'graph_inputs':graph_inputs} if graph_inputs else {}))
            observation.update(ok=True,result=value['result'],execution=value['execution'])
            self.state.update(status='tool_results_available',answer='手动计算完成：'+name+'。执行记录已保存；模型调用为0。')
        except (InterruptedError,KeyboardInterrupt):
            observation.update(ok=False,error='用户取消了本次计算')
            self.state.update(status='cancelled',answer='本次计算已取消，保留此前成功结果。')
        except Exception as exc:
            observation.update(ok=False,error=type(exc).__name__+': '+str(exc))
            from graph_research.runtime.observability import error_details
            observation['error_details']=error_details(exc,phase='offline.tool_execution')
            self.state.update(status='tool_execution_failed',answer='本次工具执行失败，未当作成功结果：'+observation['error'])
        self.state['observations'].append(observation);self._observe_tools(registry);self._save();self._finalize_output()
        return copy.deepcopy(observation)


class FormCancelled(Exception):pass


def parse_parameter(text,schema):
    """Parse data only. Numeric lists/rows have a small, explicit shorthand."""
    text=text.strip();candidates=[]
    if len(text)>100000:raise ValueError('单项参数过长')
    if 'enum' in schema:
        for item in schema['enum']:
            if text==str(item):return copy.deepcopy(item)
        if text.isdigit() and 1<=int(text)<=len(schema['enum']):return copy.deepcopy(schema['enum'][int(text)-1])
    if schema.get('type')=='boolean':
        if text.casefold() in ('是','true','y','yes','1'):return True
        if text.casefold() in ('否','false','n','no','0'):return False
    try:candidates.append(_strict_json(text))
    except ValueError:pass
    if schema.get('type')=='array' and not text.startswith(('[','{')):
        try:
            rows=text.replace('；',';').split(';')
            values=[[_strict_json(cell.strip()) for cell in row.replace('，',',').split(',')] for row in rows]
            if all(type(v) in (int,float) for row in values for v in row):
                # A single row still represents a matrix/edge if items says array.
                nested=schema.get('items',{}).get('type')=='array'
                candidates.append(values if len(rows)>1 or nested else values[0])
        except (ValueError,AttributeError):pass
    candidates.append(text)
    for value in candidates:
        if jsonschema.Draft202012Validator(schema).is_valid(value):return value
    raise ValueError('格式或范围不符合要求，请按参数说明重新填写。')


def _form(definition,initial,*,input_fn,print_fn):
    arguments=copy.deepcopy(initial);schema=definition['parameters'];required=set(schema.get('required',[]))
    fields={field['name']:field for field in input_guide(definition)['fields']}
    print_fn('逐项填写：回车保留显示值；可选项留空则省略；/省略 删除当前可选值；/返回 放弃本次填写。')
    print_fn('输入例子只作格式参考，不会自动填写；/帮助 重看当前参数的格式与例子。')
    for name,field in schema.get('properties',{}).items():
        print_fn('\n'+name+('（必填）' if name in required else '（可选）')+'：'+field.get('description',''))
        help_field=fields[name]
        def help_current():
            print_fn('输入方式：'+help_field['format'])
            print_fn('留空规则：'+help_field['omission'])
            if help_field['input_example'] is not None:print_fn('当前参数输入例子：'+help_field['input_example'])
        help_current()
        if 'enum' in field:
            print_fn('选项：'+'；'.join(f'{i+1}={v}'+('（'+ENUM_LABELS[str(v)]+'）' if str(v) in ENUM_LABELS else '') for i,v in enumerate(field['enum'])))
        current=arguments.get(name,field.get('default'))
        has_current=name in arguments or 'default' in field
        while True:
            default=json.dumps(current,ensure_ascii=False) if has_current else '未填'
            text=input_fn(f'{name} [{default}]：').strip()
            if text=='/帮助':help_current();continue
            if text=='/返回':raise FormCancelled()
            if text=='/省略':
                if name in required:print_fn('这是必填项，不能省略。');continue
                arguments.pop(name,None);break
            if not text:
                if has_current:
                    arguments[name]=copy.deepcopy(current);break
                if name not in required:arguments.pop(name,None);break
                print_fn('请填写必填项。');continue
            try:arguments[name]=parse_parameter(text,field);break
            except ValueError as exc:print_fn(str(exc))
    return arguments


def collect_arguments(definition,*,input_fn=input,print_fn=print):
    """Never execute while browsing/editing. Every route ends with validation."""
    while True:
        print_fn('参数方式：1 逐项填写；2 从示例开始并修改；3 导入参数JSON文件；4 粘贴完整参数JSON（单行）；0 返回')
        method=input_fn('参数方式：').strip()
        if method=='0':raise FormCancelled()
        try:
            if method in ('1','2'):
                initial={}
                if method=='2':
                    examples=definition.get('documentation',{}).get('examples',[])
                    if not examples:print_fn('该工具没有登记示例，请选择逐项填写。');continue
                    for i,example in enumerate(examples):print_fn(f'{i+1} '+json.dumps(example['arguments'],ensure_ascii=False))
                    selected=input_fn('示例编号 [1]：').strip() or '1'
                    if not selected.isdigit() or not 1<=int(selected)<=len(examples):print_fn('示例编号无效。');continue
                    initial=examples[int(selected)-1]['arguments']
                arguments=_form(definition,initial,input_fn=input_fn,print_fn=print_fn)
            elif method=='3':
                path=input_fn('参数文件路径（UTF-8 JSON，/返回 取消）：').strip()
                if path=='/返回':raise FormCancelled()
                arguments=read_arguments(path)
            elif method=='4':
                text=input_fn('完整参数JSON（单行，/返回 取消）：').strip()
                if text=='/返回':raise FormCancelled()
                if len(text)>100000:raise ValueError('参数过长')
                arguments=_strict_json(text)
            else:print_fn('请选择列出的参数方式。');continue
            jsonschema.validate(arguments,definition['parameters'])
            if len(json.dumps(arguments,allow_nan=False))>100000:raise ValueError('参数超过100000字符上限')
            return arguments
        except jsonschema.ValidationError as exc:print_fn(validation_message(exc))
        except (OSError,UnicodeError,ValueError) as exc:print_fn('参数未通过：'+str(exc))


def _select(text,items,key):
    if text.isdigit() and 1<=int(text)<=len(items):return items[int(text)-1]
    return next((item for item in items if item[key]==text),None)


def _show_bundle(session,print_fn):
    if session.result_bundle:print_fn('本次使用的累计结果包：'+session.result_bundle['archive'])
    if session.result_bundle:print_fn('输入 v 查看整理后的结果页面；完整精度可在页面下载JSON。')
    if session.export_error:print_fn('计算记录已保留，打包未完成：'+session.export_error)


def run_offline_console(session,*,input_fn=input,print_fn=print):
    print_fn('无API工具模式：按分类选择已有功能，不需要模型、密钥或主agent。')
    print_fn('无API模式不自动分析自然语言、不生成新工具；计算仍受时间和内存限制。')
    print_fn('会话目录：'+str(session.directory))
    registry=session._registry();groups=grouped_tools(registry)
    for warning in session.state.get('extension_warnings',[]):print_fn('扩展未启用：'+str(warning))
    try:
        while True:
            print_fn('\n工具分类')
            for i,group in enumerate(groups):print_fn(f'{i+1} {group["name"]}（{len(group["tools"])}项）')
            print_fn('v 查看结果页面；r 最近结果；e 导出累计结果；0 退出')
            text=input_fn('请选择分类：').strip()
            if text in ('0','/退出','q'):break
            if text=='v':
                try:print_fn('结果页面：'+session.view_results(open_browser=True)['html'])
                except Exception as exc:print_fn('结果页面未打开：'+str(exc))
                continue
            if text in ('r','e'):
                observations=session.state.get('observations',[])
                if not observations:print_fn('尚无计算记录。');continue
                if text=='r':
                    for index,item in list(enumerate(observations))[-10:]:print_fn(f'{index+1} '+str(item.get('tool'))+'：'+('成功' if item.get('ok') else '失败或取消'))
                else:
                    try:session.export_results()
                    except Exception as exc:print_fn('导出未完成：'+str(exc))
                _show_bundle(session,print_fn);continue
            group=_select(text,groups,'name')
            if group is None:print_fn('请选择有效分类。');continue
            while True:
                print_fn('\n'+group['name'])
                for i,definition in enumerate(group['tools']):
                    suffix='' if definition['availability']['available'] else '【缺少依赖，暂不可用】'
                    summary=definition.get('documentation',{}).get('summary',definition['description'])
                    print_fn(f'{i+1} {summary} [{definition["name"]}]'+suffix)
                text=input_fn('请选择功能（编号或函数名，v 查看结果，0 返回分类）：').strip()
                if text=='0':break
                if text=='v':
                    try:print_fn('结果页面：'+session.view_results(open_browser=True)['html'])
                    except Exception as exc:print_fn('结果页面未打开：'+str(exc))
                    continue
                definition=_select(text,group['tools'],'name')
                if definition is None:print_fn('请选择当前分类中的功能。');continue
                show_input_guide(definition,print_fn)
                if not definition['availability']['available']:
                    print_fn('需要安装可选依赖['+definition['availability']['install_extra']+']，尚未执行计算。');continue
                if definition['status']!='native_tested':print_fn('实验工具：仅通过登记的验收样例，不代表一般正确性。')
                while True:
                    try:arguments=collect_arguments(definition,input_fn=input_fn,print_fn=print_fn)
                    except FormCancelled:break
                    print_fn('将运行：'+definition['name']+'\n'+json.dumps(arguments,ensure_ascii=False,indent=2))
                    print_fn(f'模型调用0次；每次计算用时上限{session.limits.wall_seconds}秒、内存{session.limits.memory_mb}MiB。')
                    choice=input_fn('1 开始计算；2 重新填写；0 返回功能菜单：').strip()
                    if choice=='2':continue
                    if choice!='1':break
                    print_fn('正在计算……')
                    try:
                        observation=session.call_tool(definition['name'],arguments)
                        print_fn(session.state['answer'] if observation['ok'] else '本次计算未完成；此前成功结果保留。')
                        from graph_research.rendering.results import terminal_result
                        print_fn(terminal_result(observation))
                        _show_bundle(session,print_fn)
                    except Exception as exc:print_fn('未能开始计算：'+str(exc))
                    break
    except (EOFError,KeyboardInterrupt):pass
    print_fn('已退出无API模式；已保存的计算和结果包可继续使用。')
    return 0


def offline_command(arguments,*,input_fn=input,print_fn=print):
    parser=argparse.ArgumentParser(description='无API工具模式：分类选择、参数填写、受限计算与累计结果包')
    parser.add_argument('--session');parser.add_argument('--tool-dir');parser.add_argument('--user');parser.add_argument('--memory-dir')
    parser.add_argument('--results-root',help='成果保存目录；默认使用成果中心的设置')
    parser.add_argument('--memory',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--list',action='store_true',help='只列出分类和工具，不执行计算')
    parser.add_argument('--describe',metavar='TOOL',help='查看一个工具的输入方式与例子，不进入会话或执行计算')
    parser.add_argument('--timeout',type=float,default=30);parser.add_argument('--memory-mb',type=int,default=1024)
    options=parser.parse_args(arguments)
    if options.describe:
        from graph_research.tools import ToolRegistry
        registry=ToolRegistry()
        if options.describe not in registry.tools:raise ValueError('没有该原生工具：'+options.describe)
        show_input_guide(registry.describe(options.describe),print_fn)
        return 0
    if options.list:
        from graph_research.tools import ToolRegistry
        for group in grouped_tools(ToolRegistry()):
            print_fn(group['name'])
            for tool in group['tools']:print_fn('  '+tool['name']+'：'+tool['documentation'].get('summary',tool['description']))
        return 0
    if not 0<options.timeout<=300:raise ValueError('计算用时上限需在0到300秒之间')
    directory=Path(options.session) if options.session else Path.cwd()/'outputs'/('offline_'+uuid.uuid4().hex[:12])
    from .result_catalog import ResultPreferences
    session=OfflineToolSession(directory,options.tool_dir,user_id=options.user,memory_directory=options.memory_dir,memory_enabled=options.memory,
                               limits=TaskLimits(wall_seconds=options.timeout,memory_mb=options.memory_mb),results_directory=options.results_root or ResultPreferences().active)
    return run_offline_console(session,input_fn=input_fn,print_fn=print_fn)
