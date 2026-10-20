"""Offline user-memory demonstration; no provider, credentials or auto-approval."""
import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_research.assistant import ResearchSession,UserMemoryStore


class OfflineModel:
    def __init__(self,*decisions):self.decisions=list(decisions);self.contexts=[]
    def complete(self,messages):
        self.contexts.append(json.loads(messages[1]['content']))
        return self.decisions.pop(0)


def main():
    parser=argparse.ArgumentParser(description='离线验证用户记忆，不连接模型')
    parser.add_argument('--output',default='outputs/user-memory-v011-'+uuid.uuid4().hex[:10])
    root=Path(parser.parse_args().output).resolve()
    if (root/'memory/memory.sqlite3').exists():raise ValueError('Use a new output directory for an independent demo')
    directory=root/'memory'
    first=ResearchSession(root/'alice-first',root/'packages',user_id='demo-alice',memory_directory=directory)
    first.ask('记住：以后回答简洁一些',OfflineModel({'action':'final','answer':'已记录简洁回答偏好。'}))
    first.reply('计算五阶圈图的直径',OfflineModel(
        {'action':'call','tool':'graph_invariants','arguments':{'kind':'cycle','n':5}},
        {'action':'final','answer':'工具计算的直径为2。'}))
    assert first.state['observations'][0]['result']['diameter']==2
    second=ResearchSession(root/'alice-second',root/'packages',user_id='demo-alice',memory_directory=directory)
    model=OfflineModel({'action':'final','answer':'已读取历史偏好；仅验证接口。'})
    second.ask('读取我的偏好',model)
    alice_context=model.contexts[0]['user_memory']
    assert alice_context['preferences']=={'response_detail':'concise'}
    assert alice_context['frequently_used_tools']==[{'tool':'graph_invariants','successful_calls':1}]
    other=ResearchSession(root/'bob',root/'packages',user_id='demo-bob',memory_directory=directory)
    model=OfflineModel({'action':'final','answer':'没有沿用其他用户的偏好。'})
    other.ask('读取我的偏好',model)
    assert model.contexts[0]['user_memory']=={'preferences':{},'frequently_used_tools':[]}
    memory=UserMemoryStore(directory);before_clear=memory.profile('demo-alice')
    memory.set_enabled('demo-alice',False)
    model=OfflineModel({'action':'final','answer':'已停止读取记忆。'})
    second.reply('独立分析',model)
    assert model.contexts[0]['user_memory']=={'preferences':{},'frequently_used_tools':[]}
    memory.clear('demo-alice')
    assert memory.profile('demo-alice')['preferences']=={}
    report={'real_model_calls':0,'same_user_cross_session':True,'different_users_isolated':True,
            'native_tool_result_verified':True,'disable_and_clear_verified':True,'alice_before_clear':before_clear}
    (root/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(root/'validation.json'),**report},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
