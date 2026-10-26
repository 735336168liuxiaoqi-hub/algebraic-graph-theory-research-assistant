"""Host-owned immutable graph versions; models may reference but never write them."""
import copy
import re

from graph_research.graph_input import GraphDocument
from graph_research.graph_input.adapters import graph_patch,validate_bindings,result_graph
from graph_research.runtime.serialization import canonical_json as canonical, json_fingerprint as fingerprint


def empty_objects():return {'active':None,'versions':[]}


def validate_ref(ref):
    if not isinstance(ref,dict) or set(ref)!={'id','version'} or not isinstance(ref['id'],str) or not re.fullmatch(r'G[1-9][0-9]{0,5}',ref['id']) or type(ref['version']) is not int or not 1<=ref['version']<=128:
        raise ValueError('研究对象引用需要明确的id和version。')
    return copy.deepcopy(ref)


def get_object(objects,ref):
    validate_ref(ref)
    for record in objects['versions']:
        if record['id']==ref['id'] and record['version']==ref['version']:
            if fingerprint(record['document'])!=record['sha256']:raise ValueError('研究对象快照校验失败。')
            return copy.deepcopy(record)
    raise ValueError('研究对象或版本不存在，请明确选择图对象。')


def validate_objects(objects):
    if not isinstance(objects,dict) or set(objects)!={'active','versions'} or not isinstance(objects['versions'],list) or len(objects['versions'])>128 or len(canonical(objects).encode('utf-8'))>2*1024*1024:raise ValueError('研究对象库格式或容量无效。')
    seen={}
    for record in objects['versions']:
        if not isinstance(record,dict) or not {'id','version','document','sha256'}<=set(record) or set(record)-{'id','version','document','sha256','origin_call'}:raise ValueError('研究对象快照字段无效。')
        if 'origin_call' in record and (not isinstance(record['origin_call'],str) or not re.fullmatch('[0-9a-f]{32}',record['origin_call'])):raise ValueError('图对象执行来源无效。')
        ref={k:record[k] for k in ('id','version')};validate_ref(ref)
        if record['version']!=seen.get(record['id'],0)+1:raise ValueError('研究对象版本必须连续且不能重复。')
        seen[record['id']]=record['version']
        graph=GraphDocument(record['document'])
        if graph.to_dict()!=record['document'] or fingerprint(record['document'])!=record['sha256']:raise ValueError('研究对象快照校验失败。')
    if objects['active'] is not None:get_object(objects,objects['active'])
    return copy.deepcopy(objects)


def add_graph(objects,graph,object_id=None,*,origin_call=None):
    objects=validate_objects(objects)
    if not isinstance(graph,GraphDocument):raise ValueError('需要经过验证的图对象。')
    if origin_call:
        for old in objects['versions']:
            if old.get('origin_call')==origin_call:
                if fingerprint(graph.to_dict())!=old['sha256']:raise ValueError('同一执行来源的图结果发生变化。')
                ref={k:old[k] for k in ('id','version')};objects['active']=ref;return objects,ref
    if len(objects['versions'])>=128:raise ValueError('本会话已保存128个图版本，请新建对话。')
    if object_id is None:object_id='G'+str(max([int(r['id'][1:]) for r in objects['versions']]+[0])+1)
    elif object_id not in {r['id'] for r in objects['versions']}:raise ValueError('只能为已存在的对象增加版本。')
    version=max([r['version'] for r in objects['versions'] if r['id']==object_id]+[0])+1
    ref={'id':object_id,'version':version};data=graph.to_dict()
    objects['versions'].append({**ref,'document':data,'sha256':fingerprint(data),**({'origin_call':origin_call} if origin_call else {})});objects['active']=ref
    return validate_objects(objects),ref


def object_context(objects):
    return {'active':copy.deepcopy(objects['active']),'versions':[
        {'id':r['id'],'version':r['version'],'name':r['document']['name'],'sha256':r['sha256'],
         'summary':GraphDocument(r['document']).summary(),'vertex_mapping':[{'index':i,'label':v} for i,v in enumerate(r['document']['vertices'])]}
        for r in objects['versions']]}


def prepare_call(definition,arguments,refs,objects):
    if not isinstance(arguments,dict):raise ValueError('工具参数必须是JSON对象。')
    if not isinstance(refs,dict) or not 1<=len(refs)<=12:raise ValueError('图对象绑定最多12项。')
    arguments=copy.deepcopy(arguments);bindings=[];identities=[]
    for target,ref in refs.items():
        record=get_object(objects,ref)
        prepared=graph_patch(GraphDocument(record['document']),definition,target,arguments)
        for key,value in prepared['patch'].items():
            if key in arguments and arguments[key]!=value:raise ValueError('模型参数与绑定图冲突：'+key+'；请只提交操作参数，由程序填入图结构。')
        for key in prepared['remove']:
            if key in arguments:raise ValueError('参数与绑定图的布局或度信息不一致：'+key)
        arguments.update(prepared['patch'])
        bindings.append({k:prepared[k] for k in ('target','patch','vertex_mapping','case_index') if k in prepared}|{'document':record['document']})
        identities.append({'target':target,**validate_ref(ref),'sha256':record['sha256']})
    sources=validate_bindings(definition,arguments,bindings)
    if len(canonical({'arguments':arguments,'graph_inputs':sources,'research_refs':identities}).encode('utf-8'))>240*1024:raise ValueError('图来源和计算参数过大，请缩小输入。')
    return arguments,sources,identities


def validate_execution_refs(refs,sources):
    if not isinstance(refs,list) or not 1<=len(refs)<=12 or len(refs)!=len(sources or []):raise ValueError('研究对象来源与图输入不一致。')
    for ref,source in zip(refs,sources):
        if not isinstance(ref,dict) or set(ref)!={'target','id','version','sha256'}:raise ValueError('研究对象来源字段无效。')
        validate_ref({k:ref[k] for k in ('id','version')})
        if ref['target']!=source['target'] or ref['sha256']!=fingerprint(source['document']):raise ValueError('研究对象来源与执行图不一致。')


def capture_graph(objects,observation):
    if not observation.get('ok') or observation.get('tool') not in {'graph_edit','graph_recipe','graph_construction','generate_hypergraph','hypergraph_transform'}:return objects,None
    graph=result_graph(observation)
    refs=observation.get('research_refs',[])
    object_id=refs[0]['id'] if len(refs)==1 else None
    return add_graph(objects,graph,object_id,origin_call=observation.get('operation_id'))
