"""Offline API onboarding acceptance: MockTransport only, no real credentials."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from graph_research.assistant import ResearchSession,verify_bundle
from graph_research.assistant.model import ConfiguredModel,ModelAPIError
from graph_research.assistant.model_config import setup_wizard,save_configuration,configuration_status,load_settings
from graph_research.runtime.integrity import verify
from graph_research.runtime.storage import safe_path,write_json,atomic_text


def body(mode,decision):
    text=json.dumps(decision,ensure_ascii=False)
    if mode=='responses':return {'output':[{'content':[{'type':'output_text','text':text}]}]}
    return {'choices':[{'message':{'content':text}}]}


def main():
    parser=argparse.ArgumentParser(description='模拟API接入与科研调用，不连接真实服务商')
    parser.add_argument('--output',default='outputs/api-onboarding-v014-'+uuid.uuid4().hex[:8])
    root=safe_path(parser.parse_args().output);root.mkdir(parents=True,exist_ok=False)
    before=verify();config=root/'example-public-model.json'
    clean={key:value for key,value in os.environ.items() if not key.startswith('RESEARCH_')}
    key='OFFLINE_EXAMPLE_FAKE_KEY';mock_requests=[];transcript=[]
    with patch.dict(os.environ,{**clean,'RESEARCH_MODEL_CONFIG':str(config),'RESEARCH_API_KEY':key},clear=True):
        answers=iter(['1','https://example.invalid/v1/chat/completions','offline-example-model','y'])
        setup_wizard(config,input_fn=lambda _:next(answers),print_fn=transcript.append)
        local=configuration_status(config);assert local['valid'] and local['connection_tested'] is False
        assert key not in config.read_text(encoding='utf-8')
        probes=[]
        for mode in ('chat_completions','responses'):
            save_configuration({'base_url':'https://example.invalid/v1','model':'offline-example-model','mode':mode},config)
            def handler(request):
                mock_requests.append(str(request.url))
                return httpx.Response(200,json=body(mode,{'action':'final','answer':'连接成功'}))
            client=httpx.Client(transport=httpx.MockTransport(handler))
            with patch('graph_research.assistant.model.httpx.Client',return_value=client):
                probes.append(ConfiguredModel(config_path=config).test_connection())
        save_configuration({'base_url':'https://example.invalid/v1','model':'offline-example-model','mode':'chat_completions'},config)
        failures=[]
        for status in (401,404,429):
            def handler(request):
                mock_requests.append(str(request.url));return httpx.Response(status,text=key)
            client=httpx.Client(transport=httpx.MockTransport(handler))
            with patch('graph_research.assistant.model.httpx.Client',return_value=client):
                try:ConfiguredModel(config_path=config).test_connection()
                except ModelAPIError as exc:failures.append({'http_status':status,'code':exc.code,'message':str(exc)})
                else:raise AssertionError('Expected a diagnosed mock failure')
        decisions=[{'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
                   {'action':'final','answer':'本地工具计算：三顶点路图P3的直径为2。'}]
        def scientific_handler(request):
            mock_requests.append(str(request.url))
            assert key not in request.content.decode('utf-8')
            return httpx.Response(200,json=body('chat_completions',decisions.pop(0)))
        scientific_model=ConfiguredModel(config_path=config)
        # Create a fresh mock client for each ordinary HTTP call, as production
        # closes its client after a request. No real transport is used here.
        client_class=httpx.Client
        def mock_client(**kwargs):return client_class(transport=httpx.MockTransport(scientific_handler))
        session=ResearchSession(root/'session',root/'packages')
        with patch('graph_research.assistant.model.httpx.Client',side_effect=mock_client):
            state=session.ask('计算P3的直径。',scientific_model)
        assert state['status']=='tool_results_available' and state['observations'][0]['result']['diameter']==2
        assert session.result_bundle and session.export_error is None
        checked=verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])
        assert checked['summary']['verified_calls']==1
    report={'real_provider_requests':0,'mock_http_requests':len(mock_requests),'public_setup_and_status_offline':True,
            'both_protocols_verified':probes,'diagnostic_failures_verified':failures,'native_tool_via_http_adapter_verified':True,
            'result_bundle':session.result_bundle,'core_unchanged':verify()['manifest_sha256']==before['manifest_sha256']}
    assert key not in json.dumps(report,ensure_ascii=False)
    atomic_text(root/'wizard-preview.txt','\n'.join(transcript)+'\n')
    write_json(root/'validation.json',report)
    print(json.dumps({'report':str(root/'validation.json'),'real_provider_requests':0,'mock_requests':len(mock_requests),
                      'both_protocols_verified':True,'native_calculation_and_result_bundle_verified':True},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
