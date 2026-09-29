"""Explicit Bedrock integration checks for Nova Lite.

These tests are intentionally separate from the normal unit suite and should only
run when the user is logged into AWS with the FarmwiseAI role and the target
Bedrock access is expected to be available.
"""

from __future__ import annotations

import os

import pytest

from app.services.bedrock_service import BedrockService


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_REAL_BEDROCK_INTEGRATION") != "1",
    reason="Real Nova Lite integration is opt-in; ordinary unit runs must not call AWS.",
)
def test_nova_lite_invoke_with_role_credentials():
    """Use the standard AWS provider chain and invoke Nova Lite in ap-south-1."""
    os.environ["AWS_PROFILE"] = "farmwiseai"
    service = BedrockService(region="ap-south-1", inference_profile="apac.amazon.nova-lite-v1:0")
    invocation = service.invoke_nova_lite(
        "Respond with a valid JSON object containing only the keys: status, model, confidence. "
        "Do not include markdown fences. Example: {\"status\": \"ok\", \"model\": \"nova-lite\", \"confidence\": 0.99}",
        model_id="apac.amazon.nova-lite-v1:0",
    )
    assert invocation.model_id == "apac.amazon.nova-lite-v1:0"
    assert invocation.status == "ok", f"Actual Nova Lite invocation failed: {invocation.error}"
    assert invocation.success is True
    assert invocation.latency_ms >= 0
    assert invocation.response
    print(f"Nova Lite invocation latency_ms={invocation.latency_ms}")
