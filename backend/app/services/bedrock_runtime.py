"""Small Bedrock Runtime operations shared by FastAPI and the Lambda bundle."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import boto3
from botocore.config import Config


def normalize_single_result(payload: Any) -> dict[str, Any]:
    """Normalize Nova output while retaining every returned object and unknowns."""
    if isinstance(payload, list):
        payload = {"objects": payload}
    if not isinstance(payload, dict):
        raise ValueError("Nova Lite structured result must be an object.")

    result = dict(payload)
    uncertainty_value = result.get("uncertainty_indicators")
    uncertainty = list(uncertainty_value) if isinstance(uncertainty_value, list) else []
    fields = ("building_use", "visible_floor_count", "frontage", "condition", "building_name", "confidence", "reasoning_summary")
    raw_objects = next((result.get(key) for key in ("objects", "buildings", "observations", "results")
                        if isinstance(result.get(key), list)), None)
    if raw_objects is None:
        array_lengths = [len(result[field]) for field in fields if isinstance(result.get(field), list)]
        if array_lengths:
            count = max(array_lengths)
            raw_objects = [{field: result[field][index] for field in fields
                            if isinstance(result.get(field), list) and index < len(result[field])}
                           for index in range(count)]
    if isinstance(raw_objects, list):
        result["objects"] = [_normalize_object(item) for item in raw_objects if isinstance(item, dict)]
        for item in result["objects"]:
            for indicator in item.get("uncertainty_indicators", []):
                if indicator not in uncertainty:
                    uncertainty.append(indicator)
    for field in fields:
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

    result["confidence"] = _normalize_confidence(result.get("confidence"), uncertainty)
    result["uncertainty_indicators"] = list(dict.fromkeys(uncertainty))
    return result


def _normalize_confidence(value: Any, uncertainty: list[str]) -> float | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            value = None
            uncertainty.append("confidence_not_numeric")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if value is not None:
            uncertainty.append("confidence_not_numeric")
        return None
    confidence = float(value)
    if not 0 <= confidence <= 1:
        uncertainty.append("confidence_out_of_range")
        return None
    return confidence


def _normalize_object(value: dict[str, Any]) -> dict[str, Any]:
    item = dict(value)
    uncertainty_value = item.get("uncertainty_indicators")
    uncertainty = list(uncertainty_value) if isinstance(uncertainty_value, list) else []
    for field in ("building_use", "visible_floor_count", "frontage", "condition", "building_name", "confidence", "reasoning_summary"):
        field_value = item.get(field)
        if isinstance(field_value, list):
            field_value = field_value[0] if field_value else None
        item[field] = field_value
    floor_count = item.get("visible_floor_count")
    if isinstance(floor_count, str) and re.fullmatch(r"\d+", floor_count.strip()):
        item["visible_floor_count"] = int(floor_count)
    elif floor_count is not None and (isinstance(floor_count, bool) or not isinstance(floor_count, int)):
        item["visible_floor_count"] = None
        uncertainty.append("floor_count_not_numeric")
    item["confidence"] = _normalize_confidence(item.get("confidence"), uncertainty)
    if uncertainty:
        item["uncertainty_indicators"] = uncertainty
    return item


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
