"""Offline parent/host handoff example. Simulated approval is opt-in only."""
import argparse
import json
from importlib.resources import files
from pathlib import Path
import uuid

from graph_research.assistant import create_subagent, subagent_contracts, verify_bundle
from graph_research.tools.change_control import core_fingerprint


class ScriptedModel:
    def __init__(self, decisions):self.decisions=list(decisions);self.calls=0
    def complete(self, messages):
        self.calls+=1
        return self.decisions.pop(0)


def task(request_id, objective):
    return {"version":1,"request_id":request_id,"parent_task_id":"offline-study",
            "objective":objective,"execution":{"mode":"agent"}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--simulate-user-approval',action='store_true',help='Offline test only; never use simulated consent in production')
    options=parser.parse_args()
    output=(Path(options.output) if options.output else Path('outputs')/('subagent-'+uuid.uuid4().hex)).resolve()
    output.mkdir(parents=True,exist_ok=True)
    run=uuid.uuid4().hex[:12]  # Re-running never overwrites earlier task state.
    root=output/('state-'+run);user='offline-researcher';before=core_fingerprint()
    def save(name,value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    save('contracts.json',subagent_contracts())

    parent,_=create_subagent(root,user_id=user)
    fixed=task('fixed-'+run,'计算P3邻接谱并复核矩阵的秩')
    fixed.update(inputs={'kind':'path','n':3},definitions=['普通无向简单图；邻接矩阵A'],expected_outputs=['谱半径','矩阵秩','结果包'])
    fixed['execution']={'mode':'tools','steps':[
        {'id':'spectrum','tool':'graph_spectrum','arguments':{},'bindings':{'kind':{'input':['kind']},'n':{'input':['n']}}},
        {'id':'rank','tool':'matrix_analysis','arguments':{},'bindings':{'matrix':{'step':'spectrum','path':['matrix']}}},
    ]}
    fixed['constraints']={'max_model_calls':0,'max_tool_calls':2,'allow_extensions':False}
    save('task-fixed.json',fixed)
    direct=parent.submit(fixed);save('01-fixed-result.json',direct)
    assert direct['status']=='completed' and direct['results'][1]['data']['rank']==2
    assert parent.submit(fixed)==direct
    bundle=next(a for a in direct['artifacts'] if a['kind']=='result_bundle')
    assert verify_bundle(bundle['path'],bundle['sha256'])['ok']

    clarification=ScriptedModel([
        {'action':'clarify','questions':['请确认是3个顶点的普通无向路径图P3？']},
        {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
        {'action':'final','answer':'P3的直径为2，结果来自实际工具执行。'},
    ])
    parent,portal=create_subagent(root,user_id=user,model_factory=lambda:clarification)
    waiting=parent.submit(task('clarify-'+run,'计算所给路径图的直径'))
    assert waiting['status']=='waiting_for_user';save('02-waiting-for-user.json',waiting)
    p=waiting['interaction']
    event=portal.answer(waiting['task_id'],p['interaction_id'],waiting['revision'],'确认是P3。')
    # Recreate the facade to demonstrate durable pause/resume.
    parent,_=create_subagent(root,user_id=user,model_factory=lambda:clarification)
    answered=parent.resume(waiting['task_id'],event['event_id'])
    assert answered['status']=='completed' and answered['results'][0]['data']['diameter']==2
    assert parent.resume(waiting['task_id'],event['event_id'])==answered
    assert clarification.calls==3;save('03-user-reply-result.json',answered)

    proposal=json.loads(files('graph_research').joinpath('data/h_index_proposal.json').read_text(encoding='utf-8'))
    request={'name':proposal['name'],'goal':'增加可复用的度序列h指数算法',
             'requirements':'输入非负整数度序列，最多128项；返回h_index，空序列为0。',
             'checked_tools':[{'tool':'graph_invariants','reason':'返回度序列，但没有通用h指数算法分支'}],
             'composition_possible':False,'why_not_composition':'原工具准备度序列，新的纯JSON算法负责按定义扫描求h指数。',
             'new_algorithm':'排序并扫描至少有h项>=h的最大h。','parameters':proposal['parameters'],'complexity':'small',
             'acceptance_tests':[{**f,'basis':'按定义手工验算；不是一般证明'} for f in proposal['tests']]}
    development=ScriptedModel([
        {'action':'assess','request':request}, {'action':'extend','proposal':proposal},
        {'action':'call','tool':proposal['name'],'arguments':{'degrees':[3,2,2,1]}},
        {'action':'final','answer':'h指数为2；独立扩展仅通过登记的验收样例。'},
    ])
    parent,portal=create_subagent(root,user_id=user,model_factory=lambda:development)
    awaiting=parent.submit(task('extend-'+run,'补充度序列h指数算法'))
    assert awaiting['status']=='waiting_for_approval' and development.calls==1
    save('04-waiting-for-approval.json',awaiting)
    forged=parent.dispatch({'operation':'approve','task_id':awaiting['task_id'],'approved':True})
    assert forged['status']=='protocol_error';save('05-parent-approval-rejected.json',forged)
    assert not list(root.glob('users/*/tool_packages/*/tool.py'))
    result=awaiting
    if options.simulate_user_approval:
        p=awaiting['interaction']
        event=portal.approve(awaiting['task_id'],p['interaction_id'],awaiting['revision'],p['assessment_id'],p['scope_sha256'])
        assert development.calls==1  # Signing itself cannot generate code.
        result=parent.resume(awaiting['task_id'],event['event_id'])
        assert result['status']=='completed' and result['results'][0]['data']=={'h_index':2}
        assert parent.resume(awaiting['task_id'],event['event_id'])==result and development.calls==4
        save('06-approved-extension-result.json',result)
    report={'protocol':'graph-research-subagent/1','offline_scripted_models':True,'real_model_api_calls':0,
            'clarification_reply_simulated':True,'human_approval_simulated':options.simulate_user_approval,
            'fixed_workflow_status':direct['status'],'fixed_tool_calls':direct['budget']['used']['tool_calls'],
            'fixed_bundle_verified':True,'pause_restart_and_reply_verified':True,'event_replay_did_not_reexecute':True,
            'parent_cannot_approve':True,'extension_status':result['status'],
            'core_unchanged':core_fingerprint()==before,'state_root':str(root)}
    assert report['core_unchanged'];save('report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
