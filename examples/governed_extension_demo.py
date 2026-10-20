"""Offline fixture demonstration; never use simulated consent in production."""
import argparse
import json
from importlib.resources import files
from pathlib import Path
import uuid

from graph_research.assistant import ResearchSession
from graph_research.tools.change_control import core_fingerprint


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--simulate-approval',action='store_true',help='Offline test only: simulate a human confirmation')
    parser.add_argument('--output')
    options=parser.parse_args()
    root=Path(options.output) if options.output else Path.cwd()/'outputs'/('extension-demo-'+uuid.uuid4().hex)
    tool=json.loads(files('graph_research').joinpath('data/h_index_proposal.json').read_text(encoding='utf-8'))
    request={'name':tool['name'],'goal':'增加可复用的度序列h指数算法',
             'requirements':'输入非负整数度序列，最多128项；返回h_index，空序列为0。',
             'checked_tools':[{'tool':'graph_invariants','reason':'返回度序列，但没有通用h指数算法分支'}],
             'composition_possible':False,'why_not_composition':'原工具准备度序列，新的纯JSON算法负责按定义扫描求h指数。',
             'new_algorithm':'排序并扫描至少有h项>=h的最大h。',
             'parameters':tool['parameters'],'complexity':'small',
             'acceptance_tests':[{**f,'basis':'按h指数定义手工验算的小规模测试；不是一般证明'} for f in tool['tests']]}
    decisions=[{'action':'clarify','questions':['输入是具体图还是度序列？空序列和最大规模如何约定？']},
               {'action':'assess','request':request},
               {'action':'extend','proposal':tool},
               {'action':'call','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}},
               {'action':'final','answer':'离线样例的h指数为2。独立包已通过3项验收，仅在这些样例上验证。'}]
    class OfflineModel:
        calls=0
        def complete(self,messages):
            self.calls+=1
            return decisions.pop(0)
    model=OfflineModel();before=core_fingerprint()
    session=ResearchSession(root/'session',root/'packages')
    first=session.ask('我希望增加度序列h指数计算。',model)
    assert first['status']=='awaiting_clarification'
    state=session.reply('输入度序列，最多128项，空序列返回0。',model)
    assert state['status']=='awaiting_approval'
    print(state['answer'])
    report={'offline_scripted_model':True,'real_model_called':False,'human_consent_simulated':options.simulate_approval,
            'before_approval':state['status'],'code_generated_before_approval':False,'session':str(session.directory)}
    if options.simulate_approval:
        result=session.approve(state['assessment_id'],model)
        assert result['status']=='tool_results_available',result
        assert result['observations'][-1]['result']=={'h_index':2}
        report.update(final_status=result['status'],extension=result['extension_installed'],model_calls=model.calls)
    report['original_package_unchanged']=before==core_fingerprint()
    root.mkdir(parents=True,exist_ok=True)
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
