"""One reviewed contract source for runtime tools, model context and manuals.

Documentation adds semantics to the existing schemas; it never broadens input
validation or changes a mathematical implementation. New experimental tools
retain their status and are not presented as reviewed native capabilities.
"""
import copy
from functools import lru_cache
from importlib import import_module
from importlib.resources import files
import inspect
import json
from pathlib import Path

import jsonschema


@lru_cache(maxsize=1)
def _source():
    return json.loads(files("graph_research").joinpath("data/tool_docs.json").read_text(encoding="utf-8"))


def conventions():
    """Return independent copies of cross-tool mathematical/input conventions."""
    return copy.deepcopy(_source()["conventions"])


def _schema_copy(schema):
    """Break even internal aliases in reusable schema fragments.

    deepcopy preserves aliasing: weights and vertex_degrees historically share
    NUMBERS. Each parameter needs its own annotation/default object instead.
    """
    return json.loads(json.dumps(schema,allow_nan=False))


def _annotate_nested(schema, common):
    if not isinstance(schema,dict):
        return
    for name,child in schema.get("properties",{}).items():
        if name in common:
            child.setdefault("description",common[name])
        _annotate_nested(child,common)
    if isinstance(schema.get("items"),dict):
        _annotate_nested(schema['items'],common)
    for key in ('anyOf','oneOf','allOf'):
        for child in schema.get(key,[]):
            _annotate_nested(child,common)


def enrich_tool(tool):
    """Attach reviewed semantics, copied schemas and actual Python defaults.

    The schema remains the input authority. None defaults are recorded in the
    contract but not inserted into a non-nullable schema as a valid argument.
    """
    source = _source()
    record = source['tools'].get(tool.name) if tool.status=='native_tested' else None
    if record is None:
        # Dynamic tools must not inherit the native validation claim.
        provided = copy.deepcopy(tool.documentation or {})
        tool.documentation = {**provided,"coverage":"extension_unreviewed","returns":provided.get('returns',"由该扩展工具提供；验收样例中的expected仅描述这些样例，尚无原生人工核对的一般返回契约。"),
                              "limits":["只在扩展工具列出的验收样例上通过，不是一般正确性的证明。",*provided.get('limitations',[])],
                              "effects":"bounded_extension","examples":provided.get('examples',[])}
        tool.parameters = _schema_copy(tool.parameters)
        for parameter in tool.parameters.get('properties',{}).values():
            parameter.setdefault('description','扩展提供的参数，语义以该工具用途及验收样例为准；尚未原生人工核对。')
        return
    record = copy.deepcopy(record)
    schema = _schema_copy(tool.parameters)
    descriptions = {**source['common_parameters'],**record['parameters']}
    names = set(schema.get('properties',{}))
    if names-descriptions.keys():
        raise ValueError(f"Missing parameter documentation for {tool.name}: {sorted(names-descriptions.keys())}")
    if set(record['parameters'])-names:
        raise ValueError(f"Stale parameter documentation for {tool.name}")
    _annotate_nested(schema,source['common_parameters'])
    signature = inspect.signature(tool.function)
    defaults = {}
    for name,parameter in schema['properties'].items():
        parameter['description'] = descriptions[name]
        if name in signature.parameters:
            default = signature.parameters[name].default
            if default is not inspect.Parameter.empty:
                defaults[name] = default
                if default is not None and jsonschema.Draft202012Validator(parameter).is_valid(default):
                    parameter['default'] = default
        if name=='operation' and 'operations' in record:
            if set(parameter['enum'])!=set(record['operations']):
                raise ValueError(f"Operation documentation differs from enum for {tool.name}")
            parameter['description'] += ' '+ '; '.join(f"{k}: {v}" for k,v in record['operations'].items())
        if name=='family' and 'variants' in record:
            if set(parameter['enum'])!=set(record['variants']):
                raise ValueError(f"Family documentation differs from enum for {tool.name}")
            parameter['description'] += ' '+ '; '.join(f"{k}: {v}" for k,v in record['variants'].items())
    for example in record['examples']:
        jsonschema.validate(example['arguments'],schema)
    record.update(coverage='reviewed_native',defaults=defaults,
                  python_callable=f'{tool.function.__module__}.{tool.function.__qualname__}',
                  python_signature=str(signature))
    tool.description = f"{record['summary']} 适用：{record['use_for']} 不适用：{record['not_for']}"
    tool.parameters,tool.documentation = schema,record


def tool_definition(tool, detail='full'):
    """full for reference; model for calls; index for a brief inventory."""
    if detail not in ('full','model','index'):
        raise ValueError('Catalog detail must be full, model or index')
    from .capabilities import tool_availability
    base = {'name':tool.name,'description':tool.description,'status':tool.status,
            'availability':tool_availability(tool.name)}
    doc = tool.documentation or {}
    if detail=='index':
        return {**base,'category':doc.get('category','扩展工具')}
    base['parameters'] = copy.deepcopy(tool.parameters)
    if detail=='full':
        base['documentation'] = copy.deepcopy(doc)
    else:
        base['documentation'] = {k:copy.deepcopy(doc[k]) for k in
                                ('coverage','preconditions','returns','limits','effects') if k in doc}
        if doc.get('examples'):
            base['documentation']['example_arguments'] = copy.deepcopy(doc['examples'][0]['arguments'])
    return base


def function_definitions(registry):
    """Vendor-neutral name/description/parameters triples, not a wire protocol.

    The host must wrap these in its chosen provider's API. Limits, return
    meanings and preconditions are retained in the description for adapters
    that accept no custom metadata keys.
    """
    result = []
    for tool in registry.tools.values():
        doc = tool.documentation or {}
        description = tool.description
        from .capabilities import tool_availability
        availability = tool_availability(tool.name)
        if not availability['available']:
            description += ' 当前环境不可用，缺少'+','.join(availability['missing_requirements'])+f"；需要[{availability['install_extra']}]可选依赖。"
        for key,title in [('preconditions','前提'),('returns','返回'),('limits','限制'),('effects','副作用')]:
            value = doc.get(key)
            if value:
                description += f" {title}："+('；'.join(value) if isinstance(value,list) else str(value))
        if tool.status!='native_tested':
            description += f' 状态：{tool.status}，未获得原生工具的一般验证。'
        result.append({'name':tool.name,'description':description,'parameters':copy.deepcopy(tool.parameters)})
    return result


def library_api_index():
    """Index callable signatures; entries are NOT model-callable tool names.

    Missing docstrings remain explicitly marked instead of fabricating a
    mathematical contract from a function's name.
    """
    result = []
    for module_name in ('graphs','hypergraphs','tensors','combinatorics','polynomials','linear_algebra','algebra.recurrences','algebra.integer_systems','algebra.analysis','algebra.blocks','graphs.weighted','graphs.classification','workflows.recipes','workflows.internal_paths','workflows.energy','workflows.batch','workflows.environment','graph_input.document','graph_input.adapters','graph_input.storage','plotting','rendering.layouts','tools.library_entries','layout_editor','tikz','elimination','assistant.memory','assistant.session','assistant.result_catalog','assistant.result_cleanup','assistant.spectral_scan','hypergraphs.spectral_certificate','hypergraphs.spectral_methods','hypergraphs.newton_noda','schematics.document','schematics.tikz','mcp.telemetry','assistant.claims','assistant.governance','assistant.feature_routes','assistant.evaluation','assistant.streaming','assistant.model_config','assistant.model_profiles','assistant.model_capabilities','mcp.contracts','mcp.runtime'):
        module = import_module('graph_research.'+module_name)
        for name,value in inspect.getmembers(module):
            if name.startswith('_') or not (inspect.isfunction(value) or inspect.isclass(value)):
                continue
            if not getattr(value,'__module__','').startswith('graph_research.'):
                continue
            members = [(f'{module.__name__}.{name}',value)]
            if inspect.isclass(value):
                members += [(f'{module.__name__}.{name}.{n}',v) for n,v in inspect.getmembers(value)
                            if not n.startswith('_') and (inspect.isfunction(v) or inspect.ismethod(v))]
            for qualified,callable_value in members:
                try: signature = str(inspect.signature(callable_value))
                except (ValueError,TypeError): signature = '(signature unavailable)'
                text = inspect.getdoc(callable_value) or ''
                result.append({'python_api':qualified,'signature':signature,'docstring':text,
                               'documentation_status':'has_docstring' if text else 'needs_detail',
                               'model_callable':False})
    return result


def render_reference(registry):
    native_count = sum((t.documentation or {}).get('coverage')=='reviewed_native' for t in registry.tools.values())
    lines = ['# 工具功能说明（自动生成）','',
             '由tool_docs.json、实际函数签名及JSON Schema合成；请修改来源后重新生成。',
             f'这是{native_count}个已核对原生工具及已加载扩展的调用契约，不是Sage全部函数的等价性声明。','',
             '## 通用约定','']+['- '+s for s in conventions()]
    for tool in registry.tools.values():
        d = tool.documentation or {}
        lines += ['',f'## {tool.name}','',tool.description,'',f"状态：{tool.status}；副作用：{d.get('effects','未说明')}。"]
        for key,title in [('preconditions','前提'),('returns','返回'),('limits','限制')]:
            value = d.get(key)
            if value:
                lines += ['',f'**{title}**：'+('；'.join(value) if isinstance(value,list) else str(value))]
        lines += ['','| 参数 | 必填 | 省略时的Python默认值 | 含义 |','| --- | --- | --- | --- |']
        for name,schema in tool.parameters.get('properties',{}).items():
            defaults = d.get('defaults',{})
            default = repr(defaults[name]) if name in defaults else '—'
            description = schema.get('description','扩展工具自行提供，尚未统一核对').replace('|','\\|').replace('\n',' ')
            lines.append(f"| `{name}` | {'是' if name in tool.parameters.get('required',[]) else '否'} | `{default}` | {description} |")
        if d.get('examples'):
            lines += ['','示例（已验证输入格式；计算结果以实际调用为准）：','',
                      '```json',json.dumps({'action':'call','tool':tool.name,'arguments':d['examples'][0]['arguments']},ensure_ascii=False,indent=2),'```']
        if d.get('related_tools'):
            lines += ['','相关工具：'+', '.join(f'`{s}`' for s in d['related_tools'])+'。']
    return '\n'.join(lines)+'\n'


def export_documentation(registry,directory):
    """Write portable JSON contracts and a human-readable reference; no calls."""
    from graph_research.runtime.storage import safe_path,atomic_text
    directory = safe_path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    outputs = {
        'tool-catalog.json':{'format':'graph-research-tool-contracts','version':1,
                             'conventions':conventions(),'tools':registry.catalog(detail='full')},
        'function-definitions.json':function_definitions(registry),
        'library-api-index.json':library_api_index()}
    paths = {}
    for name,data in outputs.items():
        path = directory/name
        atomic_text(path,json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),overwrite=True)
        paths[name] = str(path.resolve())
    path = directory/'TOOL_REFERENCE.md'
    atomic_text(path,render_reference(registry),overwrite=True)
    paths[path.name] = str(path.resolve())
    return paths
