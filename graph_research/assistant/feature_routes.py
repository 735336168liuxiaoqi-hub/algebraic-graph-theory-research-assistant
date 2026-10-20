"""Host capability routing: composition, restricted algorithm, manual brief or clarify."""
import copy
from datetime import datetime,timezone
import json
import uuid
from graph_research.runtime.storage import write_json,atomic_text


def feature_route(request,registry):
    if not isinstance(request,dict) or 'source' in request:raise ValueError('先描述需求和能力缺口，不能在评估中提交源码。')
    if len(json.dumps(request,ensure_ascii=False,allow_nan=False).encode('utf-8'))>100000:raise ValueError('需求评估过大。')
    if request.get('composition_possible') is True:return {'kind':'composition'}
    mode=request.get('implementation_mode','restricted');libraries=request.get('required_libraries',[])
    if mode not in ('restricted','manual','uncertain') or not isinstance(libraries,list) or len(libraries)>12 or any(not isinstance(v,str) or not 1<=len(v)<=64 for v in libraries):raise ValueError('实现方式或依赖声明无效。')
    if mode=='uncertain' or request.get('validation_ready') is False or not request.get('requirements') or len(request.get('acceptance_tests',[]))<2:
        return {'kind':'clarify','questions':['请补充明确的数学定义、输入输出及规模范围。','请给出至少两个可独立核对的验收例子及依据；不确定的预期值不要作为正确性标准。']}
    if mode=='manual' or libraries:
        checked=request.get('checked_tools',[])
        if not checked or any(not isinstance(c,dict) or c.get('tool') not in registry.tools or not isinstance(c.get('reason'),str) for c in checked):raise ValueError('独立开发说明也需要核对现有工具及不能联动解决的原因。')
        return {'kind':'manual','reason':'需要声明的外部库或超出受限纯JSON算法能力；应独立开发、评估和验收，当前不生成或安装源码。'}
    return {'kind':'restricted'}


def development_brief(request,route,directory):
    identifier=uuid.uuid4().hex;record={'id':identifier,'kind':'manual_development','created_at':datetime.now(timezone.utc).isoformat(),
        'request':copy.deepcopy(request),'reason':route['reason'],'authorization':'none','estimated_money':None,
        'estimate_note':'独立开发的时间、模型消耗及验收环境需要另行评估；本说明不授予执行、安装或付费权限。',
        'requirements':['单独封包，不修改原基础包','明确依赖、输入规模、复杂度和失败行为','提供独立可复核样例及边界、反例测试','安装前评估消耗并获得本次用户确认']}
    path=directory/identifier;write_json(path/'development-brief.json',record)
    text='独立开发需求\n\n'+str(request.get('goal',''))+'\n\n'+str(request.get('requirements',''))+'\n\n'+route['reason']+'\n'+record['estimate_note']+'\n\n完整范围：\n'+json.dumps(request,ensure_ascii=False,indent=2)
    atomic_text(path/'development-brief.md',text)
    return record
