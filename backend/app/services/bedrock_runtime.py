"""Small Bedrock Runtime operations shared by FastAPI and the Lambda bundle."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import boto3
from botocore.config import Config


def normalize_single_result(payload: Any) -> dict[str, Any]:
    """Normalize a single structured result from scalar or parallel-array model output."""
    if isinstance(payload, list):
        payload = next((item for item in payload if isinstance(item, dict)), {})
    if not isinstance(payload, dict):
        raise ValueError("Nova Lite structured result must be an object.")

    result = dict(payload)
    uncertainty = list(result.get("uncertainty_indicators") or [])
    for field in ("building_use", "visible_floor_count", "frontage", "condition", "building_name", "confidence", "reasoning_summary"):
        value = result.get(field)
        if isinstance(value, list):
            value = value[0] if value else None
        result[field] = value

    floor_count = result.get("visible_floor_count")
    if isinstance(floor_count, str) and re.fullmatch(r"\d+", floor_count.strip()):
        result["visible_floor_count"] = int(floor_count)
    elif floor_count is not None and (isinstance(floor_count, bool) or not isinstance(floor_count, int)):
        result["visible_floor_count"] = None
        uncertainty.append("floor_count_not_numeric")

    confidence = result.get("confidence")
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = 0.0
        uncertainty.append("qualitative_confidence_not_numeric")
    result["confidence"] = max(0.0, min(1.0, float(confidence)))
    result["uncertainty_indicators"] = uncertainty
    return result


def make_bedrock_runtime_client(*, region: str, profile: str | None = None) -> Any:
    session = boto3.Session(profile_name=profile or None, region_name=region)
    return session.client(
        "bedrock-runtime",
        config=Config(
            retries={"total_max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


def invoke_text(
    client: Any,
    *,
    model_id: str,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }).encode("utf-8"),
    )
    body = response["body"]
    try:
        result = json.loads(body.read())
    finally:
        body.close()
    return result, round((time.perf_counter() - started) * 1000, 2)


def invoke_image(
    client: Any,
    *,
    model_id: str,
    prompt: str,
    image_bytes: bytes,
    image_format: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = client.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"text": prompt},
                {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
            ],
        }],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return response, round((time.perf_counter() - started) * 1000, 2)