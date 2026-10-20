"""Traceable result references; matching fields is never a proof of model prose."""
import copy
import jsonschema
from .task_contract import obj,JSON_PATH
from .research_objects import canonical
from .planning import read_path
from .model_context import bounded

REFERENCE=obj({'observation':{'type':'integer','minimum':0},'path':JSON_PATH,'expected':{}},['observation','path'])
CLAIM=obj({'text':{'type':'string','minLength':1,'maxLength':2000},
           'kind':{'enum':['numerical','exact','enumeration','conjecture','analysis','proof']},
           'sources':{'type':'array','maxItems':8,'items':REFERENCE}},['text','kind'])
SCHEMA={'type':'array','maxItems':16,'items':CLAIM}
EXACT_TOOLS={'graph_invariants','graph_characteristic_polynomial','matching_polynomial','integer_linear_system',
             'exact_matrix_operation','linear_recurrence','combinatorial_calculation','graph_class_certificate','graph_energy_study','block_matrix_analysis','symbolic_analysis'}
NUMERICAL_TOOLS={'graph_spectrum','weighted_graph_spectrum','directed_graph_spectrum','hypergraph_spectrum','hypergraph_quotient_spectrum','matrix_analysis','tensor_operation'}
KIND_LABELS={'numerical':'数值计算','exact':'精确计算记录','enumeration':'有限范围计算','conjecture':'模型猜想','analysis':'模型分析','proof':'模型提出的证明'}
STATUS_LABELS={'field_matched':'字段值已核对，文字推论未验证','source_linked':'已关联计算来源，文字推论未验证',
               'unverified':'尚未关联可核验计算','invalid_reference':'来源或字段核对失败','unverified_proof':'证明尚未独立验证',
               'experimental':'含实验扩展结果，仅样例验收','incomplete_scope':'有限范围未穷尽，不能作为完整枚举结论'}


def evidence_kind(observation):
    if observation.get('tool_status')=='fixture_tested_experimental':return 'experimental'
    if observation.get('tool') in NUMERICAL_TOOLS:return 'numerical'
    if observation.get('tool') in ('graph_batch_study','graph_energy_study','graph_class_certificate'):return 'enumeration'
    if observation.get('tool') in EXACT_TOOLS:return 'exact'
    return 'tool_computation'


def _has_float(value):
    if isinstance(value,float):return True
    if isinstance(value,list):return any(_has_float(v) for v in value)
    if isinstance(value,dict):return any(_has_float(v) for v in value.values())
    return False


def audit_claims(claims,observations,verify_source=None):
    try:
        if len(canonical(claims).encode('utf-8'))>64000:raise ValueError()
        jsonschema.validate(claims,SCHEMA)
    except (ValueError,TypeError,jsonschema.ValidationError):return [{'text':'模型返回的结论引用格式无效，请结合原始结果核对。','kind':'analysis','status':'invalid_reference','sources':[]}]
    result=[];checked={}
    for claim in claims:
        row={'text':claim['text'],'kind':claim['kind'],'status':'unverified','sources':[]};matches=[];invalid=False
        for ref in claim.get('sources',[]):
            source={'observation':ref['observation'],'path':copy.deepcopy(ref['path'])}
            try:
                item=observations[ref['observation']]
                if not item.get('ok') or 'tool' not in item:raise ValueError('所指计算没有成功结果。')
                value=read_path(item['result'],ref['path'])
                if ref['observation'] not in checked:checked[ref['observation']]=bool(verify_source(ref['observation'])) if verify_source is not None else False
                if not checked[ref['observation']]:raise ValueError('计算缺少有效执行回执。')
                source.update(tool=item['tool'],kind=evidence_kind(item),value=bounded(value,1800),research_refs=copy.deepcopy(item.get('research_refs',[])))
                if isinstance(item['result'],dict):source['scope']={key:bounded(item['result'][key],1200) for key in ('conditions','assumptions','warnings','status','complete','exhaustive','precision','residual','seed','iterations') if key in item['result']}
                if source['kind']=='exact' and _has_float(value):source['kind']='numerical'
                if 'expected' in ref:
                    if canonical(ref['expected'])!=canonical(value):raise ValueError('声明值与实际字段不一致。')
                    matches.append(True)
                else:matches.append(False)
                source['verified_execution']=True
            except (ValueError,IndexError,KeyError,TypeError,OSError) as error:source['error']=str(error);invalid=True
            row['sources'].append(source)
        if invalid:row['status']='invalid_reference'
        elif row['sources']:
            row['status']='field_matched' if all(matches) else 'source_linked'
            kinds={s.get('kind') for s in row['sources']}
            if claim['kind']=='exact' and kinds!={'exact'}:row['kind']='numerical' if 'numerical' in kinds else 'enumeration' if kinds=={'enumeration'} else 'analysis'
            if 'experimental' in kinds:row['status']='experimental'
            if claim['kind']=='enumeration':
                for ref in claim.get('sources',[]):
                    data=observations[ref['observation']]['result']
                    if isinstance(data,dict) and (data.get('exhaustive') is False or data.get('status') in ('undetermined','budget_exhausted','partial')):row['status']='incomplete_scope'
        if claim['kind']=='proof' and not invalid:row['status']='unverified_proof'
        result.append(row)
    return result


def claim_text(claim):return KIND_LABELS.get(claim['kind'],claim['kind'])+' · '+STATUS_LABELS.get(claim['status'],claim['status'])+'\n'+claim['text']
