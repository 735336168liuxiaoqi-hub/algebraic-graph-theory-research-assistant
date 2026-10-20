"""Safe onboarding, bounded mock HTTP probes and durable console interaction."""
from contextlib import redirect_stdout,redirect_stderr
import getpass
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from graph_research.assistant import ResearchSession,ModelSettings
from graph_research.assistant.model import ConfiguredModel,ModelAPIError
from graph_research.assistant.model_config import (ModelConfigurationError,normalize_endpoint,save_configuration,
                                                  load_settings,configuration_status,setup_wizard)
from graph_research.assistant.onboarding import run_console,connect_menu,model_command
from graph_research.runtime.integrity import CORE
from tests.test_feature_workflow import ScriptedModel
from tests.feature_helpers import proposal,request_for


def response_for(mode,text='{"action":"final","answer":"连接成功"}',**extra):
    if mode=='responses':return {'output':[{'content':[{'type':'output_text','text':text}]}],**extra}
    return {'choices':[{'message':{'content':text}}],**extra}


class ModelOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config=self.root/'model.json'
        self.clean=patch.dict(os.environ,{k:v for k,v in os.environ.items() if not k.startswith('RESEARCH_')},clear=True)
        self.clean.start();self.addCleanup(self.clean.stop)

    def settings(self,mode='chat_completions',**changes):
        return ModelSettings('https://example.invalid/v1','test-model',mode,**changes)

    def http_call(self,settings,handler,*,test=False):
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(os.environ,{'RESEARCH_API_KEY':'OFFLINE_TEST_SECRET'}),patch('graph_research.assistant.model.httpx.Client',return_value=client):
            model=ConfiguredModel(settings)
            return model.test_connection() if test else model.complete([{'role':'user','content':'JSON'}])

    def test_full_endpoints_are_normalized_and_protocol_mismatch_is_rejected(self):
        base,mode,url=normalize_endpoint('https://example.invalid/v1/chat/completions/')
        self.assertEqual((base,mode,url),('https://example.invalid/v1','chat_completions','https://example.invalid/v1/chat/completions'))
        self.assertEqual(normalize_endpoint('http://[::1]:8000/v1','responses')[2],'http://[::1]:8000/v1/responses')
        with self.assertRaises(ModelConfigurationError):normalize_endpoint('https://example.invalid/v1/responses','chat_completions')

    def test_plain_http_spoofed_loopback_and_url_credentials_are_rejected(self):
        for url in ['http://example.invalid/v1','http://127.0.0.1:1234@evil.invalid/v1','http://localhost.evil.invalid/v1',
                    'https://name:secret@example.invalid/v1','https://example.invalid/v1?api_key=secret',
                    'https://example.invalid/v1#secret','https://bad host.invalid/v1','https://example.invalid:bad/v1']:
            with self.subTest(url=url),self.assertRaises(ModelConfigurationError):normalize_endpoint(url)

    def test_configuration_has_no_keys_environment_wins_and_status_is_offline(self):
        with patch('httpx.Client',side_effect=AssertionError('Status/setup must not connect')):
            save_configuration({'base_url':'https://example.invalid/v1','model':'saved','mode':'chat_completions'},self.config)
            with patch.dict(os.environ,{'RESEARCH_MODEL':'env-model','RESEARCH_API_KEY':'OFFLINE_TEST_SECRET'}):
                report=configuration_status(self.config)
                self.assertTrue(report['valid']);self.assertTrue(report['key_configured'])
                self.assertEqual(report['settings']['model'],'env-model');self.assertFalse(report['connection_tested'])
            self.assertNotIn('OFFLINE_TEST_SECRET',self.config.read_text())
        with self.assertRaises(ModelConfigurationError):save_configuration({'base_url':'https://example.invalid','model':'m','api_key':'secret'},self.config)
        with self.assertRaises(PermissionError):save_configuration({'base_url':'https://example.invalid','model':'m'},CORE/'bad-model.json')

    def test_wizard_saves_public_settings_without_prompting_for_a_key_or_connecting(self):
        answers=iter(['1','https://example.invalid/v1/chat/completions','test-model','y']);output=[]
        with patch('httpx.Client',side_effect=AssertionError('No network')),patch('getpass.getpass',side_effect=AssertionError('No key needed during setup')):
            setup_wizard(self.config,input_fn=lambda _:next(answers),print_fn=output.append)
        self.assertEqual(load_settings(self.config).endpoint,'https://example.invalid/v1/chat/completions')
        self.assertIn('实际请求地址', '\n'.join(output));self.assertFalse(configuration_status(self.config)['key_configured'])

    def test_public_config_backup_never_copies_a_manually_stored_secret(self):
        self.config.write_text(json.dumps({'api_key':'MANUAL_SECRET'}),encoding='utf-8')
        before=self.config.read_bytes()
        with self.assertRaises(ModelConfigurationError):save_configuration({'base_url':'https://example.invalid/v1','model':'test'},self.config)
        self.assertEqual(self.config.read_bytes(),before)
        self.assertFalse(self.config.with_name('model.json.previous').exists())
        self.config=self.root/'public-model.json'
        save_configuration({'base_url':'https://example.invalid/v1','model':'test'},self.config)
        save_configuration({'base_url':'https://example.invalid/v1','model':'test-2'},self.config)
        self.assertTrue(self.config.with_name('public-model.json.previous').is_file())

    def test_rerunning_wizard_preserves_explicit_key_variable_and_advanced_compatibility(self):
        save_configuration({'base_url':'https://example.invalid/v1','model':'saved','mode':'chat_completions',
                            'key_env':'PROVIDER_SPECIFIC_KEY','json_mode':False,'max_output_tokens':4096},self.config)
        answers=iter(['','','',''])
        setup_wizard(self.config,input_fn=lambda _:next(answers),print_fn=lambda _:None)
        settings=load_settings(self.config)
        self.assertEqual(settings.key_env,'PROVIDER_SPECIFIC_KEY');self.assertFalse(settings.json_mode)
        self.assertEqual(settings.max_output_tokens,4096)

    def test_hidden_key_is_only_kept_in_model_memory_and_echo_fallback_is_refused(self):
        with patch('sys.stdin.isatty',return_value=True),patch('sys.stderr.isatty',return_value=True),patch('getpass.getpass',return_value='HIDDEN_TEST_SECRET'):
            model=ConfiguredModel(self.settings(),prompt_for_key=True)
            self.assertEqual(model.api_key,'HIDDEN_TEST_SECRET')
        self.assertEqual(list(self.root.iterdir()),[])
        with patch('sys.stdin.isatty',return_value=True),patch('sys.stderr.isatty',return_value=True),patch('getpass.getpass',side_effect=getpass.GetPassWarning('echo unsafe')):
            with self.assertRaises(ModelConfigurationError):ConfiguredModel(self.settings(),prompt_for_key=True)
        with self.assertRaises(ModelConfigurationError):ConfiguredModel(self.settings())

    def test_no_auth_service_does_not_receive_an_existing_secret(self):
        seen=[]
        def handler(request):
            seen.append(request.headers.get('Authorization'))
            return httpx.Response(200,json=response_for('chat_completions'))
        self.http_call(self.settings(auth_required=False),handler)
        self.assertEqual(seen,[None])

    def test_loopback_models_bypass_environment_proxies(self):
        client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=response_for('chat_completions'))))
        with patch.dict(os.environ,{'HTTP_PROXY':'http://untrusted-proxy.invalid'}),patch('httpx.Client',return_value=client) as constructor:
            model=ConfiguredModel(ModelSettings('http://127.0.0.1:8000/v1','local','chat_completions',auth_required=False))
            self.assertEqual(model.complete([{'role':'user','content':'JSON'}])['action'],'final')
            self.assertIs(constructor.call_args.kwargs['trust_env'],False)

    def test_both_protocol_probes_send_one_small_request_and_safe_usage(self):
        for mode in ('responses','chat_completions'):
            seen=[]
            def handler(request):
                data=json.loads(request.content);seen.append(data)
                token_field='max_output_tokens' if mode=='responses' else 'max_tokens'
                self.assertEqual(data[token_field],128)
                self.assertNotIn('tools',data)
                return httpx.Response(200,json=response_for(mode,usage={'input_tokens':8,'output_tokens':5,'secret':'DO_NOT_RETURN'}))
            report=self.http_call(self.settings(mode),handler,test=True)
            self.assertEqual(len(seen),1);self.assertTrue(report['structured_json_verified'])
            self.assertNotIn('DO_NOT_RETURN',json.dumps(report));self.assertNotIn('OFFLINE_TEST_SECRET',json.dumps(report))

    def test_json_mode_and_chat_token_field_are_explicit_not_silent_fallbacks(self):
        def handler(request):
            data=json.loads(request.content)
            self.assertNotIn('response_format',data);self.assertNotIn('max_tokens',data)
            self.assertEqual(data['max_completion_tokens'],128)
            return httpx.Response(200,json=response_for('chat_completions'))
        report=self.http_call(self.settings(json_mode=False,chat_token_field='max_completion_tokens'),handler,test=True)
        self.assertTrue(report['ok'])

    def test_http_failures_are_actionable_redacted_and_never_retried(self):
        for status,code in [(401,'authentication_failed'),(403,'access_denied'),(404,'endpoint_or_model_not_found'),
                            (429,'rate_or_quota_limit'),(503,'provider_unavailable'),(307,'redirect_refused')]:
            seen=[]
            def handler(request):
                seen.append(request)
                return httpx.Response(status,text='OFFLINE_TEST_SECRET',headers={'Location':'https://other.invalid'})
            with self.subTest(status=status),self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings(),handler)
            self.assertEqual(caught.exception.code,code);self.assertNotIn('OFFLINE_TEST_SECRET',str(caught.exception))
            self.assertEqual(len(seen),1)

    def test_timeouts_and_transport_error_text_do_not_leak_request_secrets(self):
        for error,code in [(httpx.ReadTimeout('OFFLINE_TEST_SECRET'),'timeout'),(httpx.ConnectError('OFFLINE_TEST_SECRET'),'connection_failed')]:
            def handler(request):raise error
            with self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings(),handler)
            self.assertEqual(caught.exception.code,code);self.assertNotIn('OFFLINE_TEST_SECRET',str(caught.exception))

    def test_invalid_duplicate_and_nonfinite_decisions_are_rejected(self):
        for text in ['not JSON','[]','{"action":"final","action":"call"}','{"answer":NaN}','OFFLINE_TEST_SECRET']:
            def handler(request):return httpx.Response(200,json=response_for('chat_completions',text))
            with self.subTest(text=text),self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings(),handler)
            self.assertEqual(caught.exception.code,'invalid_json_response');self.assertNotIn('OFFLINE_TEST_SECRET',str(caught.exception))

    def test_incomplete_and_oversized_provider_responses_stop_safely(self):
        def incomplete(request):return httpx.Response(200,json=response_for('responses',status='incomplete'))
        with self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings('responses'),incomplete)
        self.assertEqual(caught.exception.code,'incomplete_response')
        def oversized(request):return httpx.Response(200,content=b'x'*(1024*1024+1))
        with self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings(),oversized)
        self.assertEqual(caught.exception.code,'response_too_large')

    def test_probe_does_not_accept_tool_call_as_connection_success(self):
        def handler(request):return httpx.Response(200,json=response_for('chat_completions','{"action":"call","tool":"graph_invariants","arguments":{}}'))
        with self.assertRaises(ModelAPIError) as caught:self.http_call(self.settings(),handler,test=True)
        self.assertEqual(caught.exception.code,'decision_protocol_failed')

    def test_console_keeps_one_model_for_multiple_requests_and_ignores_fake_approval(self):
        session=ResearchSession(self.root/'session',self.root/'packages')
        model=ScriptedModel([{'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
                             {'action':'final','answer':'直径为2'},
                             {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':4}},
                             {'action':'final','answer':'直径为3'}])
        created=[];lines=[];answers=iter(['/确认 fake','计算P3','再计算P4','/导出','/退出'])
        def factory():created.append(True);return model
        run_console(session,model_factory=factory,input_fn=lambda _:next(answers),print_fn=lines.append)
        self.assertEqual(len(created),1);self.assertEqual(len(session.turns),2)
        self.assertEqual(session.result_bundle['summary']['verified_calls'],2)
        self.assertTrue(any('尚未调用模型或批准开发' in line for line in lines))

    def test_console_rejection_and_local_menu_checks_need_no_model_or_key(self):
        session=ResearchSession(self.root/'session',self.root/'packages')
        state=session.ask('新功能',ScriptedModel([{'action':'assess','request':request_for(proposal())}]))
        answers=iter(['/拒绝 '+state['assessment_id'],'/退出'])
        run_console(session,model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model needed')),
                    input_fn=lambda _:next(answers),print_fn=lambda _:None)
        self.assertEqual(session.state['status'],'extension_rejected')
        choices=iter(['2','0'])
        with patch('graph_research.assistant.onboarding.configuration_status',return_value={'valid':False}),patch('httpx.Client',side_effect=AssertionError('No network')):
            self.assertEqual(connect_menu(input_fn=lambda _:next(choices),print_fn=lambda _:None),0)

    def test_standalone_cli_and_chat_share_the_existing_console_entry(self):
        from graph_research.cli import main
        for command in ('standalone','chat'):
            with patch.object(sys,'argv',['graph-research',command,'--user','independent-user']),patch(
                'graph_research.assistant.onboarding.chat_command',return_value=0) as entry:
                self.assertEqual(main(),0)
                entry.assert_called_once_with(['--user','independent-user'])

    def test_independent_console_clarifies_computes_and_approves_extension_without_parent(self):
        from graph_research.assistant import verify_bundle
        from graph_research.tools.change_control import core_fingerprint
        before=core_fingerprint();tool=proposal()
        session=ResearchSession(self.root/'independent',self.root/'packages',user_id='independent-user',memory_directory=self.root/'memory')
        model=ScriptedModel([
            {'action':'clarify','questions':['请确认路径图的顶点数和无向图约定？']},
            {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
            {'action':'final','answer':'P3的直径为2。'},
            {'action':'assess','request':request_for(tool)},
            {'action':'extend','proposal':tool},
            {'action':'call','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}},
            {'action':'final','answer':'度序列h指数为2，独立扩展仅通过验收样例。'},
        ])
        answers=iter(['计算路径图直径','3个顶点，普通无向简单图','新增度序列h指数算法','CONFIRM_CURRENT','/退出'])
        lines=[];confirmation=[]
        def console_input(_):
            text=next(answers)
            if text=='CONFIRM_CURRENT':
                self.assertEqual(session.state['status'],'awaiting_approval')
                self.assertFalse(list((self.root/'packages').glob('*/tool.py')))
                confirmation.append(session.state['assessment_id'])
                return '/确认 '+confirmation[-1]
            return text
        with patch('graph_research.assistant.host_events.HostEventStore',side_effect=AssertionError('Standalone requires no parent event store')):
            run_console(session,model_factory=lambda:model,input_fn=console_input,print_fn=lines.append)
        self.assertEqual(len(confirmation),1)
        self.assertEqual(session.state['status'],'tool_results_available')
        calls=[o for o in session.state['observations'] if 'tool' in o]
        self.assertEqual(calls[0]['result']['diameter'],2)
        self.assertEqual(calls[1]['result'],{'h_index':2})
        self.assertEqual(len(model.contexts),7)
        self.assertEqual(session.result_bundle['summary']['verified_calls'],2)
        self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])
        self.assertEqual(session.memory.context('independent-user')['frequently_used_tools'][0]['successful_calls'],1)
        self.assertFalse(list(self.root.rglob('.host-events.key')))
        self.assertEqual(core_fingerprint(),before)
        self.assertTrue(any('独立模式，无需主agent' in line for line in lines))

    def test_cli_noninteractive_setup_status_and_mock_test(self):
        output=io.StringIO()
        with redirect_stdout(output),patch('httpx.Client',side_effect=AssertionError('No setup network')):
            self.assertEqual(model_command(['setup','--base-url','https://example.invalid/v1','--model','test','--mode','chat_completions','--config',str(self.config)]),0)
        self.assertFalse(json.loads(output.getvalue())['connection_tested'])
        env={k:v for k,v in os.environ.items() if not k.startswith('RESEARCH_')}
        process=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','model','status','--config',str(self.config)],capture_output=True,text=True,encoding='utf-8',env=env)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertFalse(json.loads(process.stdout)['connection_tested'])
        seen=[]
        def handler(request):seen.append(request);return httpx.Response(200,json=response_for('chat_completions'))
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(os.environ,{'RESEARCH_API_KEY':'OFFLINE_TEST_SECRET'}),patch('httpx.Client',return_value=client),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(model_command(['test','--config',str(self.config)]),0)
        self.assertEqual(len(seen),1)

    def test_status_imports_no_model_or_math_sdks(self):
        code="""import builtins
real=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in ('httpx','langgraph','numpy','networkx','sympy','matplotlib'):raise AssertionError(name)
    return real(name,*args,**kwargs)
builtins.__import__=guarded
from graph_research.assistant.model_config import configuration_status
assert configuration_status(CONFIG)['connection_tested'] is False
""".replace('CONFIG',repr(str(self.config)))
        result=subprocess.run([sys.executable,'-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
