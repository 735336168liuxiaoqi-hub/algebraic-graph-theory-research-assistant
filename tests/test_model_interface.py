import json
import os
import unittest
from unittest.mock import patch
import httpx
from graph_research.model import ConfiguredModel


class ModelAdapterTests(unittest.TestCase):
    def test_both_http_protocols_without_network(self):
        for mode in ("responses","chat_completions"):
            with self.subTest(mode=mode):
                def handler(request):
                    payload=json.loads(request.content)
                    self.assertEqual(payload["model"],"test-model")
                    decision=json.dumps({"action":"final","answer":"离线协议测试"})
                    if mode=="responses":
                        self.assertEqual(request.url.path,"/v1/responses")
                        return httpx.Response(200,json={"output":[{"content":[{"type":"output_text","text":decision}]}]})
                    self.assertEqual(request.url.path,"/v1/chat/completions")
                    return httpx.Response(200,json={"choices":[{"message":{"content":decision}}]})
                client=httpx.Client(transport=httpx.MockTransport(handler))
                values={"RESEARCH_MODEL":"test-model","RESEARCH_API_KEY":"test-secret",
                        "RESEARCH_BASE_URL":"https://example.invalid/v1","RESEARCH_API_MODE":mode}
                with patch.dict(os.environ,values),patch("graph_research.model.httpx.Client",return_value=client):
                    result=ConfiguredModel().complete([{"role":"user","content":"JSON test"}])
                self.assertEqual(result["action"],"final")

    def test_unconfigured_model_fails_before_request(self):
        with patch.dict(os.environ,{},clear=True),patch('graph_research.assistant.model_config.load_public_config',return_value={}),patch("httpx.Client",side_effect=AssertionError("Network")):
            with self.assertRaises(ValueError): ConfiguredModel()


if __name__=="__main__": unittest.main()
