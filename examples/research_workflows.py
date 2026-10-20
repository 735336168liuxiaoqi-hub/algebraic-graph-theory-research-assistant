"""A protected, no-model research batch and exact finite energy comparison."""
import json
from pathlib import Path
import uuid
from graph_research.assistant import OfflineToolSession,verify_bundle


def main():
    root=Path.cwd()/'outputs'/('research-workflows-'+uuid.uuid4().hex[:10])
    session=OfflineToolSession(root/'session',root/'extensions')
    cases=[{'name':'P4','input':{'kind':'path','n':4}}]
    for t in (1,2,3):
        cases.append({'name':f'超图悬挂族 t={t}','graph_type':'hypergraph','recipe':{
            'base':{'family':'path','m':2,'k':3},'parameters':{'t':t},
            'steps':[{'operation':'attach_path','roots':[{'kind':'leaf','edge':0}],'length':'t'}],
            'assertions':{'size':'t+2','order':'2*t+5','uniform':True,'linear':True,'cycle_rank':0}}})
    session.call_tool('graph_batch_study',{'cases':cases,'plot':True})
    batch=session.state['observations'][-1]
    if 'error' in batch:raise RuntimeError(batch['error'])
    print(json.dumps(batch['result']['files'],ensure_ascii=False,indent=2))
    session.call_tool('graph_energy_study',{
        'left':{'recipe':{'base':{'kind':'path','n':'t+2'}}},
        'right':{'recipe':{'base':{'kind':'complete','n':'t+2'}}},'values':[0,1,2,3]})
    energy=session.state['observations'][-1]
    if 'error' in energy:raise RuntimeError(energy['error'])
    if not verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok']:raise ArithmeticError('Bundle verification failed')
    print(json.dumps({'energy_status':energy['result']['status'],'result_bundle':session.result_bundle},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
