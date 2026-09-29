"""Selected-view orchestration for vision, OCR, and selective escalation."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from app.services.bedrock_service import BedrockService
from app.services.inference_router import InferenceRouter
from app.services.ocr_service import OCRProvider, UnconfiguredOCRProvider, process_view_ocr
from app.services.vision_service import VisionProvider, detect_view_observations


def _attach_spatially_contained_ocr(
    observations: list[dict[str, Any]],
    ocr_results: list[dict[str, Any]],
) -> None:
    """Associate visible text with a building box without asserting its meaning."""
    for text_result in ocr_results:
        region = text_result.get("bounding_region")
        if not isinstance(region, Mapping):
            continue
        try:
            center_x = float(region["x"]) + float(region["width"]) / 2
            center_y = float(region["y"]) + float(region["height"]) / 2
        except (KeyError, TypeError, ValueError):
            continue
        for observation in observations:
            if observation.get("asset_type") != "building":
                continue
            building_region = observation.get("bounding_region")
            if not isinstance(building_region, Mapping):
                continue
            try:
                x, y = float(building_region["x"]), float(building_region["y"])
                right = x + float(building_region["width"])
                bottom = y + float(building_region["height"])
            except (KeyError, TypeError, ValueError):
                continue
            if x <= center_x <= right and y <= center_y <= bottom:
                attributes = observation.setdefault("attributes", {})
                text = text_result.get("normalized_text")
                if text:
                    attributes.setdefault("visible_sign_text", []).append(text)
                    attributes.setdefault("ocr_evidence_ids", []).append(text_result["ocr_id"])
                break


def _selected_image_bytes(view_context: Mapping[str, Any]) -> bytes | None:
    """Return the selected image payload without fetching remote URLs."""
    image_bytes = view_context.get("image_bytes")
    if isinstance(image_bytes, bytes):
        return image_bytes
    image = view_context.get("image")
    if isinstance(image, bytes):
        return image
    if image is not None and hasattr(image, "save"):
        buffer = BytesIO()
        image.save(buffer, format=getattr(image, "format", None) or "PNG")
        return buffer.getvalue()
    image_path = view_context.get("image_path")
    if isinstance(image_path, (str, Path)):
        if str(image_path).startswith(("http://", "https://")):
            return None
        return Path(image_path).read_bytes()
    return None


class ObservationPipelineService:
    """Run provider-independent detection, OCR, confidence routing, and escalation."""

    def __init__(
        self,
        *,
        vision_provider: VisionProvider,
        ocr_provider: OCRProvider | None = None,
        inference_router: InferenceRouter | None = None,
        bedrock_service: BedrockService | None = None,
    ) -> None:
        self.vision_provider = vision_provider
        self.ocr_provider = ocr_provider or UnconfiguredOCRProvider()
        self.inference_router = inference_router or InferenceRouter()
        self.bedrock_service = bedrock_service

    def process(self, view_context: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        detector_count_before = getattr(self.vision_provider, "invocation_count", None)
        detector_started = time.perf_counter()
        observations = detect_view_observations(view_context, self.vision_provider)
        detector_wall_latency = round((time.perf_counter() - detector_started) * 1000, 2)
        ocr_count_before = getattr(self.ocr_provider, "invocation_count", None)
        ocr_started = time.perf_counter()
        ocr_results = process_view_ocr(view_context, self.ocr_provider)
        _attach_spatially_contained_ocr(observations, ocr_results)
        ocr_wall_latency = round((time.perf_counter() - ocr_started) * 1000, 2)
        detector_latency_ms = float(getattr(self.vision_provider, "last_latency_ms", detector_wall_latency) or detector_wall_latency)
        ocr_latency_ms = float(getattr(self.ocr_provider, "last_latency_ms", ocr_wall_latency) or ocr_wall_latency)
        detector_count_after = getattr(self.vision_provider, "invocation_count", None)
        ocr_count_after = getattr(self.ocr_provider, "invocation_count", None)
        detector_invocations = (
            max(0, int(detector_count_after) - int(detector_count_before))
            if detector_count_before is not None and detector_count_after is not None
            else int(getattr(self.vision_provider, "name", "") not in {"unconfigured", "mock_fixture"})
        )
        ocr_invocations = (
            max(0, int(ocr_count_after) - int(ocr_count_before))
            if ocr_count_before is not None and ocr_count_after is not None
            else int(getattr(self.ocr_provider, "name", "") not in {"unconfigured", "mock_fixture"})
        )
        simulated_detector_invocations = detector_invocations if str(getattr(self.vision_provider, "name", "")).startswith("simulated") else 0
        simulated_ocr_invocations = ocr_invocations if str(getattr(self.ocr_provider, "name", "")).startswith("simulated") else 0
        detector_invocations -= simulated_detector_invocations
        ocr_invocations -= simulated_ocr_invocations
        small_model_latency_ms = round(detector_latency_ms + ocr_latency_ms, 2)

        if not observations:
            routing = {
                "model_route": "small_model",
                "escalation_reason": None,
                "confidence_before_escalation": None,
                "final_confidence": None,
                "latency_ms": small_model_latency_ms,
                "estimated_cost": None,
                "success": True,
                "vlm_success": False,
                "failure_reason": None,
                "nova_lite_invoked": False,
            }
        else:
            confidence = min(item["confidence"] for item in observations)
            distinct_types = len({item["asset_type"] for item in observations})
            scene_complexity = min(1.0, max(0.0, (distinct_types - 1) / 3))
            small_result = {"observations": observations}
            panorama_reference = str(view_context.get("panorama_reference") or view_context.get("view_id"))
            selected_context = {
                key: view_context[key]
                for key in ("view_id", "latitude", "longitude", "heading", "pitch", "field_of_view")
                if key in view_context
            }
            prompt = (
                "Review the supplied selected image and detector findings. Return the required structured building fields. "
                "Only report visual details supported by the image; do not invent visible properties. "
                f"Selected-view reference: {panorama_reference}. "
                f"Camera/view context: {json.dumps(selected_context, ensure_ascii=True, default=str)}. "
                f"Detector findings: {json.dumps(observations, ensure_ascii=True, default=str)}"
            )
            routed = self.inference_router.run_escalation(
                small_model_result=small_result,
                small_model_latency_ms=small_model_latency_ms,
                prompt=prompt,
                confidence=confidence,
                scene_complexity=scene_complexity,
                image_bytes=_selected_image_bytes(view_context),
                service=self.bedrock_service,
            )
            routed_result = routed.get("result")
            if routed.get("vlm_success") and isinstance(routed_result, Mapping):
                building_observations = [item for item in observations if item["asset_type"] == "building"]
                if building_observations:
                    attributes = building_observations[0]["attributes"]
                    for source_key, target_key in (
                        ("visible_floor_count", "visible_floor_count"),
                        ("building_use", "building_use"),
                        ("frontage", "frontage"),
                        ("building_name", "building_name"),
                        ("condition", "condition"),
                    ):
                        value = routed_result.get(source_key)
                        if value is not None:
                            attributes[target_key] = value
            routing = {
                "model_route": routed["model_route"],
                "escalation_reason": routed.get("escalation_reason"),
                "confidence_before_escalation": routed.get("confidence_before_escalation", confidence),
                "final_confidence": routed.get("final_confidence", confidence),
                "latency_ms": routed["latency_ms"],
                "estimated_cost": routed.get("estimated_cost"),
                "success": routed["success"],
                "vlm_success": routed["vlm_success"],
                "escalation_provider": routed.get("escalation_provider"),
                "simulated_escalation_invoked": routed.get("simulated_escalation_invoked", False),
                "failure_reason": routed.get("failure_reason"),
                "nova_lite_invoked": routed.get("nova_lite_invoked", False),
            }

        for observation in observations:
            observation.update({
                "model_route": routing["model_route"],
                "escalation_reason": routing["escalation_reason"],
                "confidence_before_escalation": routing["confidence_before_escalation"],
                "final_confidence": routing["final_confidence"] if routing["final_confidence"] is not None else observation["confidence"],
                "latency_ms": routing["latency_ms"],
                "estimated_cost": routing["estimated_cost"],
                "escalation_provider": routing.get("escalation_provider"),
            })
        return {
            "view_id": str(view_context.get("view_id")),
            "observations": observations,
            "ocr_results": ocr_results,
            "routing": routing,
            "processing_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "provider_execution": {
                "detector_invocations": detector_invocations,
                "ocr_invocations": ocr_invocations,
                "simulated_detector_invocations": simulated_detector_invocations,
                "simulated_ocr_invocations": simulated_ocr_invocations,
                "nova_lite_invocations": int(routing["nova_lite_invoked"]),
                "nova_lite_invocation_attempts": int(routing["escalation_reason"] is not None),
                "simulated_escalation_invocations": int(routing.get("simulated_escalation_invoked", False)),
                "detector_latency_ms": detector_latency_ms,
                "ocr_latency_ms": ocr_latency_ms,
                "nova_lite_latency_ms": round(max(0.0, float(routing["latency_ms"]) - small_model_latency_ms), 2)
                if routing["escalation_reason"] is not None else 0.0,
            },
        }
