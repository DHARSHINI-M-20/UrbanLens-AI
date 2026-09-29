"""Bedrock integration for selective Amazon Nova Lite escalation.

This project relies on AWS role-based credentials and never stores secret keys in
source control. If AWS credentials or boto3 are unavailable, the service returns a
clean configuration error instead of fabricating a VLM result.
"""

from __future__ import annotations

import json
import time
from typing import Any

from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings


class NovaLiteStructuredResponse(BaseModel):
    """Structured output contract expected from the Nova Lite escalation."""

    building_use: str | None = None
    visible_floor_count: int | None = None
    frontage: str | None = None
    condition: str | None = None
    building_name: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    uncertainty_indicators: list[str] = Field(default_factory=list)
    reasoning_summary: str | None = None


class BedrockInvocationResult(BaseModel):
    status: str
    model_id: str
    response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: float = Field(default=0.0, ge=0)
    success: bool = False


class BedrockService:
    """Minimal Bedrock wrapper intended for confirmed AWS role-based access."""

    def __init__(self, *, region: str | None = None, inference_profile: str | None = None) -> None:
        settings = get_settings()
        self.region = region or settings.aws_region or "ap-south-1"
        self.inference_profile = inference_profile or settings.bedrock_inference_profile or "apac.amazon.nova-lite-v1:0"
        self.client = None

    def _make_client(self):
        try:
            import boto3  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("boto3 is not installed. Add it to backend requirements to enable Bedrock access.") from exc

        try:
            self.client = boto3.client("bedrock-runtime", region_name=self.region)
            return self.client
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError("AWS credentials are not available through the standard provider chain.") from exc
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("AWS Bedrock access is not configured for this environment.") from exc

    @staticmethod
    def _extract_text_response(payload: Any) -> str | None:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            for item in payload:
                extracted = BedrockService._extract_text_response(item)
                if extracted:
                    return extracted
            return None
        if isinstance(payload, dict):
            for key in ("text", "completion", "outputText", "answer"):
                value = payload.get(key)
                if value:
                    return str(value)
            if "output" in payload:
                return BedrockService._extract_text_response(payload["output"])
            if "message" in payload:
                return BedrockService._extract_text_response(payload["message"])
            if "content" in payload:
                return BedrockService._extract_text_response(payload["content"])
            if "parts" in payload:
                return BedrockService._extract_text_response(payload["parts"])
        return None

    def parse_structured_response(self, payload: dict[str, Any]) -> NovaLiteStructuredResponse:
        """Validate the Nova Lite JSON output against the expected structured schema."""
        text = self._extract_text_response(payload)
        if not text:
            raise ValidationError("No structured text content was returned from Amazon Nova Lite.")
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`\n ")
        if "{" not in cleaned:
            raise ValidationError("Nova Lite response did not contain a JSON object.")
        parsed = json.loads(cleaned[cleaned.find("{") : cleaned.rfind("}") + 1])
        return NovaLiteStructuredResponse.model_validate(parsed)

    def invoke_nova_lite(
        self,
        prompt: str,
        *,
        model_id: str | None = None,
        image_bytes: bytes | None = None,
    ) -> BedrockInvocationResult:
        """Call Nova Lite for text or multimodal escalation using the configured profile."""
        started = time.perf_counter()
        client = self._make_client()
        target_model = model_id or self.inference_profile
        try:
            if image_bytes is not None:
                image_format = self._image_format(image_bytes)
                response = client.converse(
                    modelId=target_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"text": prompt},
                            {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
                        ],
                    }],
                    inferenceConfig={"maxTokens": 512, "temperature": 0.2},
                )
                data = response
            else:
                payload = {
                    "modelId": target_model,
                    "contentType": "application/json",
                    "accept": "application/json",
                    "body": json.dumps({
                        "messages": [{"role": "user", "content": [{"text": prompt}]}],
                        "inferenceConfig": {"maxTokens": 512, "temperature": 0.2},
                    }).encode("utf-8"),
                }
                response = client.invoke_model(**payload)
                body = response.get("body").read()
                data = json.loads(body)
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return BedrockInvocationResult(
                status="ok",
                model_id=target_model,
                response=data,
                latency_ms=latency_ms,
                success=True,
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "ClientError")
            message = exc.response.get("Error", {}).get("Message", str(exc))
            return BedrockInvocationResult(
                status="escalation_failed",
                model_id=target_model,
                error=f"{error_code}: {message}",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                success=False,
            )

        except (NoCredentialsError, PartialCredentialsError) as exc:
            return BedrockInvocationResult(
                status="escalation_failed",
                model_id=target_model,
                error=f"credentials_error: {type(exc).__name__}: {exc}",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                success=False,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            return BedrockInvocationResult(
                status="escalation_failed",
                model_id=target_model,
                error=str(exc),
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                success=False,
            )

    @staticmethod
    def _image_format(image_bytes: bytes) -> str:
        """Identify a supported image encoding from its signature, not client claims."""
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "gif"
        if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "webp"
        raise ValueError("Nova image escalation requires valid PNG, JPEG, GIF, or WebP bytes.")

    def structured_building_prompt(self, *, panorama_reference: str, context: str | None = None) -> str:
        """Construct a structured prompt for building-use and floor-count analysis."""
        return (
            "You are evaluating an authorized Street View scene for an urban asset. "
            f"Panorama reference: {panorama_reference}. "
            "Return valid JSON with fields: building_use, visible_floor_count, "
            "frontage, condition, building_name, confidence, uncertainty_indicators, reasoning_summary. "
            "Only describe visible floors. If floor count is uncertain, label it as estimated/uncertain or not_visible. "
            + (context or "")
        )

    def refresh_configuration(self) -> dict[str, str]:
        """Return the configured AWS/Bedrock settings without exposing secret keys."""
        return {"AWS_REGION": self.region, "BEDROCK_INFERENCE_PROFILE": self.inference_profile}
