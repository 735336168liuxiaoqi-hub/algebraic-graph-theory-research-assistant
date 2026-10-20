"""Small model views with explicit references to full local JSON data."""
import copy
import json
import re
import jsonschema

from .research_objects import canonical,get_object
from .planning import read_path
from .task_contract import obj,JSON_PATH


def summary(value,depth=0):
    if isinstance(value,str):return value if len(value)<=1200 else {'_truncated':'text','length':len(value),'preview':value[:1200]}
    if isinstance(value,(dict,list)) and depth>=4:return {'_truncated':type(value).__name__,'length':len(value)}
    if isinstance(value,list):
        preview=[summary(v,depth+1) for v in value[:8]]
        return preview if len(value)<=8 else {'_truncated':'list','length':len(value),'preview':preview}
    if isinstance(value,dict):
        result={k:summary(v,depth+1) for k,v in list(value.items())[:24]}
        if len(value)>24:result['_truncated_keys']=len(value)-24
        return result
    return value


def bounded(value,limit=16000):
    if len(canonical(value).encode('utf-8'))<=limit:return copy.deepcopy(value)
    result=summary(value)
    if len(canonical(result).encode('utf-8'))>limit:result={'_truncated':'large_json','note':'请使用更具体的JSON路径读取，完整数据保存在本地。'}
    return result


def model_catalog(catalog,request,decisions):
    inventory=[{'name':tool['name'],'description':tool['description'][:400],'status':tool.get('status'),'availability':tool.get('availability')} for tool in catalog]
    tokens=set(re.findall(r'[a-z][a-z_0-9]+|[\u4e00-\u9fff]{2}',request.lower()))
    recent=[d.get('tool') for d in decisions[-4:] if d.get('tool')]
    def score(tool):
        text=(tool['name']+' '+tool['description']).lower()
        return sum(len(token) for token in tokens if token in text)+(100 if tool['name'] in recent else 0)
    selected=sorted(catalog,key=score,reverse=True)[:6]
    return inventory,selected


def observations_context(observations):
    result=[]
    for index in range(max(0,len(observations)-12),len(observations)):
        item=observations[index]
        row={key:copy.deepcopy(item[key]) for key in ('tool','ok','plan_id','plan_step','research_refs','output_graph_ref','operation') if key in item}
        for key in ('arguments','error','result'):
            if key in item:row[key]=bounded(item[key],6000)
        row['result_ref']={'observation':index,'path':[]};result.append(row)
    return result


def objects_context(objects):
    active=objects['active'];recent={(r['id'],r['version']) for r in objects['versions'][-3:]}
    rows=[]
    for record in objects['versions']:
        row={k:copy.deepcopy(record[k]) for k in ('id','version','sha256')}
        data=record['document'];row.update(name=data['name'],graph_type=data['graph_type'],order=len(data['vertices']),size=len(data['edges']),directed=data['directed'],weighted=data['weighted'])
        if {'id':record['id'],'version':record['version']}==active or (record['id'],record['version']) in recent:
            row['vertex_mapping']=[{'index':i,'label':v} for i,v in enumerate(data['vertices'])]
        rows.append(row)
    return {'active':copy.deepcopy(active),'versions':rows}


def plan_context(plan):
    if not plan:return None
    return {k:copy.deepcopy(plan[k]) for k in ('id','title','status','cursor','error') if k in plan}|{
        'steps':[{k:copy.deepcopy(s[k]) for k in ('id','description','tool','status','graph_refs','bindings') if k in s} for s in plan['steps']]}


INSPECT=obj({'tools':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'type':'string'}},
             'result':obj({'observation':{'type':'integer','minimum':0},'path':JSON_PATH},['observation','path']),
             'object':obj({'ref':obj({'id':{'type':'string'},'version':{'type':'integer'}},['id','version']),'path':JSON_PATH},['ref','path'])})


def inspect_data(query,registry,allowed,objects,observations):
    jsonschema.validate(query,INSPECT)
    if not query:raise ValueError('请指定要读取的工具契约、结果或图对象。')
    result={'query':copy.deepcopy(query)}
    if 'tools' in query:
        if not set(query['tools'])<=allowed:raise ValueError('只能读取本任务允许的工具说明。')
        result['tools']=[registry.tools[name].definition(detail='model') for name in query['tools']]
    if 'result' in query:
        ref=query['result'];index=ref['observation']
        if index>=len(observations) or not observations[index].get('ok') or 'result' not in observations[index]:raise ValueError('没有这个成功计算结果。')
        result['result']=bounded(read_path(observations[index]['result'],ref['path']))
    if 'object' in query:
        ref=query['object'];result['object']=bounded(read_path(get_object(objects,ref['ref'])['document'],ref['path']))
    return result
