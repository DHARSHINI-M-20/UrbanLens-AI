from __future__ import annotations

import io
import json

from app.services.bedrock_service import BedrockService


class FakeBedrockRuntime:
    def __init__(self):
        self.request = None

    def converse(self, **request):
        self.request = request
        return {"output": {"message": {"content": [{"text": '{"building_use":"commercial","confidence":0.9}'}]}}}


class FakeTextOnlyBedrockRuntime:
    def __init__(self):
        self.request = None

    def invoke_model(self, **request):
        self.request = request
        return {"body": io.BytesIO(json.dumps({"output": {"message": {"content": [
            {"text": '{"building_use":"commercial","confidence":0.9}'}
        ]}}}).encode())}


def test_image_escalation_uses_converse_image_block_and_existing_profile(monkeypatch):
    runtime = FakeBedrockRuntime()
    service = BedrockService(region="ap-south-1", inference_profile="apac.amazon.nova-lite-v1:0")
    monkeypatch.setattr(service, "_make_client", lambda: runtime)
    image_bytes = b"\x89PNG\r\n\x1a\nfixture-image-data"

    result = service.invoke_nova_lite("Inspect this selected view", image_bytes=image_bytes)

    assert result.status == "ok"
    assert result.model_id == "apac.amazon.nova-lite-v1:0"
    assert runtime.request["modelId"] == "apac.amazon.nova-lite-v1:0"
    assert runtime.request["messages"][0]["content"][1] == {
        "image": {"format": "png", "source": {"bytes": image_bytes}}
    }
    assert runtime.request["inferenceConfig"]["maxTokens"] == 512
    assert service.parse_structured_response(result.response).building_use == "commercial"


def test_text_only_nova_call_keeps_existing_invoke_model_path(monkeypatch):
    runtime = FakeTextOnlyBedrockRuntime()
    service = BedrockService(region="ap-south-1", inference_profile="apac.amazon.nova-lite-v1:0")
    monkeypatch.setattr(service, "_make_client", lambda: runtime)

    result = service.invoke_nova_lite("Text-only fallback")

    assert result.status == "ok"
    assert result.model_id == "apac.amazon.nova-lite-v1:0"
    assert runtime.request["modelId"] == "apac.amazon.nova-lite-v1:0"
    assert "image" not in json.loads(runtime.request["body"])["messages"][0]["content"][0]
