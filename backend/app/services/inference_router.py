"""Small-model-first routing with selective Nova Lite escalation."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.services.bedrock_service import BedrockService, NovaLiteStructuredResponse


class RouteDecision(BaseModel):
    model_route: Literal["small_model", "vlm_escalation", "simulated_escalation"]
    model_name: str
    latency_ms: float = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    reason_for_escalation: str | None = None
    confidence: float = Field(ge=0, le=1)
    vlm_success: bool | None = None
    failure_reason: str | None = None


class InferenceRouter:
    """Decide whether a Street View observation can be accepted directly."""

    def __init__(
        self,
        *,
        building_use_threshold: float = 0.75,
        floor_count_threshold: float = 0.70,
        complex_scene_threshold: float = 0.60,
    ) -> None:
        self.building_use_threshold = building_use_threshold
        self.floor_count_threshold = floor_count_threshold
        self.complex_scene_threshold = complex_scene_threshold

    def decide(
        self,
        *,
        confidence: float,
        building_use_confidence: float | None = None,
        floor_count_confidence: float | None = None,
        scene_complexity: float | None = None,
    ) -> RouteDecision:
        """Choose between a small-model path and an Amazon Nova Lite escalation."""
        confidence = float(confidence)
        building_use_confidence = float(confidence if building_use_confidence is None else building_use_confidence)
        floor_count_confidence = float(confidence if floor_count_confidence is None else floor_count_confidence)
        scene_complexity = float(0.0 if scene_complexity is None else scene_complexity)

        reasons: list[str] = []
        if confidence < self.building_use_threshold:
            reasons.append("low_overall_confidence")
        if building_use_confidence < self.building_use_threshold:
            reasons.append("building_use_uncertain")
        if floor_count_confidence < self.floor_count_threshold:
            reasons.append("floor_count_uncertain")
        if scene_complexity >= self.complex_scene_threshold:
            reasons.append("complex_scene")

        if not reasons:
            return RouteDecision(
                model_route="small_model",
                model_name="small_detection_model",
                latency_ms=0,
                estimated_cost=None,
                reason_for_escalation=None,
                confidence=confidence,
            )

        return RouteDecision(
            model_route="vlm_escalation",
            model_name="Amazon Nova Lite",
            latency_ms=0,
            estimated_cost=None,
            reason_for_escalation="; ".join(reasons),
            confidence=confidence,
        )

    def run_escalation(
        self,
        *,
        small_model_result: dict[str, object],
        small_model_latency_ms: float = 0.0,
        prompt: str,
        confidence: float,
        image_bytes: bytes | None = None,
        building_use_confidence: float | None = None,
        floor_count_confidence: float | None = None,
        scene_complexity: float | None = None,
        service: BedrockService | None = None,
        region: str | None = None,
    ) -> dict[str, object]:
        """Only escalate to Nova Lite when configured low-confidence conditions are present.

        If the VLM call fails, preserve the small-model output and record the failure rather than crashing.
        """
        decision = self.decide(
            confidence=confidence,
            building_use_confidence=building_use_confidence,
            floor_count_confidence=floor_count_confidence,
            scene_complexity=scene_complexity,
        )

        if decision.model_route == "small_model":
            return {
                "model_route": "small_model",
                "model_name": "small_detection_model",
                "latency_ms": small_model_latency_ms,
                "estimated_cost": decision.estimated_cost,
                "escalation_reason": None,
                "confidence_before_escalation": confidence,
                "final_confidence": confidence,
                "result": small_model_result,
                "success": True,
                "vlm_success": False,
                "nova_lite_invoked": False,
                "escalation_provider": None,
            }

        started = time.perf_counter()
        bedrock = service or BedrockService(region=region)
        try:
            if image_bytes is None:
                invocation = bedrock.invoke_nova_lite(prompt)
            else:
                invocation = bedrock.invoke_nova_lite(prompt, image_bytes=image_bytes)
        except Exception as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            return {
                "model_route": "small_model",
                "model_name": "small_detection_model",
                "latency_ms": round(small_model_latency_ms + elapsed, 2),
                "estimated_cost": None,
                "escalation_reason": decision.reason_for_escalation,
                "confidence_before_escalation": confidence,
                "final_confidence": confidence,
                "result": small_model_result,
                "success": False,
                "vlm_success": False,
                "nova_lite_invoked": False,
                "failure_reason": f"bedrock_invocation_failed: {exc}",
            }
        decision.latency_ms = invocation.latency_ms or round((time.perf_counter() - started) * 1000, 2)

        if invocation.status != "ok":
            decision.model_route = "small_model"
            decision.model_name = "small_detection_model"
            decision.vlm_success = False
            decision.failure_reason = invocation.error
            return {
                "model_route": "small_model",
                "model_name": "small_detection_model",
                "latency_ms": round(small_model_latency_ms + decision.latency_ms, 2),
                "estimated_cost": decision.estimated_cost,
                "escalation_reason": decision.reason_for_escalation,
                "confidence_before_escalation": confidence,
                "final_confidence": confidence,
                "result": small_model_result,
                "success": False,
                "vlm_success": False,
                "nova_lite_invoked": True,
                "failure_reason": invocation.error,
            }

        try:
            structured = bedrock.parse_structured_response(invocation.response)
            decision.vlm_success = True
            decision.failure_reason = None
            return {
                "model_route": "simulated_escalation" if getattr(bedrock, "is_simulated", False) else "vlm_escalation",
                "model_name": "simulated_nova_lite_mock" if getattr(bedrock, "is_simulated", False) else "Amazon Nova Lite",
                "escalation_provider": "simulated_mock" if getattr(bedrock, "is_simulated", False) else "amazon_bedrock",
                "latency_ms": round(small_model_latency_ms + decision.latency_ms, 2),
                "estimated_cost": decision.estimated_cost,
                "escalation_reason": decision.reason_for_escalation,
                "confidence_before_escalation": confidence,
                "final_confidence": structured.confidence,
                "result": structured.model_dump(mode="json"),
                "success": True,
                "vlm_success": True,
                "nova_lite_invoked": not getattr(bedrock, "is_simulated", False),
                "simulated_escalation_invoked": bool(getattr(bedrock, "is_simulated", False)),
                "failure_reason": None,
            }
        except (ValidationError, TypeError, ValueError) as exc:
            decision.model_route = "small_model"
            decision.model_name = "small_detection_model"
            decision.vlm_success = False
            decision.failure_reason = f"structured_output_validation_failed: {exc}"
            return {
                "model_route": "small_model",
                "model_name": "small_detection_model",
                "latency_ms": round(small_model_latency_ms + decision.latency_ms, 2),
                "estimated_cost": decision.estimated_cost,
                "escalation_reason": decision.reason_for_escalation,
                "confidence_before_escalation": confidence,
                "final_confidence": confidence,
                "result": small_model_result,
                "success": False,
                "vlm_success": False,
                "nova_lite_invoked": True,
                "failure_reason": decision.failure_reason,
            }
