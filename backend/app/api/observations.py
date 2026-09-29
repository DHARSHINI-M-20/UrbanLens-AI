"""Observation API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection, with_location
from app.config import get_settings
from app.services.discrepancy_service import detect_discrepancies
from app.services.observation_fusion_service import fuse_nearby_observations
from app.services.observation_pipeline import ObservationPipelineService
from app.services.ocr_service import TesseractOCRProvider
from app.services.positioning_service import PositioningService
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.reference_matching_service import (
    ReferenceDataAdapter,
    StaticReferenceProvider,
    match_observation,
)
from app.services.study_area_service import STUDY_AREA_ID, contains_point
from app.services.vision_service import LocalYOLOWorldVisionProvider, UnconfiguredVisionProvider

router = APIRouter()


def _local_pipeline() -> ObservationPipelineService:
    settings = get_settings()
    return ObservationPipelineService(
        vision_provider=LocalYOLOWorldVisionProvider(),
        ocr_provider=TesseractOCRProvider(executable_path=settings.tesseract_cmd),
    )


_pipeline = _local_pipeline()


def configure_pipeline(pipeline: ObservationPipelineService | None) -> None:
    """Inject the configured detector/OCR/Nova adapters at startup or in tests."""
    global _pipeline
    _pipeline = pipeline or _local_pipeline()


class ObservationInput(BaseModel):
    observation_id: str = Field(min_length=1)
    street_id: str | None = None
    panorama_reference: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    asset_type: str = Field(default="other")
    attributes: dict[str, Any] = Field(default_factory=dict)
    ocr_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    model_route: str = "small_model"
    source: str = "small_model"
    human_review_status: str = "pending"
    study_area_id: str = STUDY_AREA_ID


class ProcessViewInput(BaseModel):
    view_id: str = Field(min_length=1)
    image_base64: str = Field(min_length=1, max_length=24_000_000)
    image_context: dict[str, Any] = Field(default_factory=dict)


def _public(item: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    item.pop("_id", None)
    item.pop("location", None)
    return item


def _building_identity(observation: dict[str, Any]) -> str | None:
    attributes = observation.get("attributes") or {}
    value = attributes.get("building_name") or attributes.get("business_name") or attributes.get("name")
    if value is None:
        sign_text = attributes.get("visible_sign_text") or []
        if isinstance(sign_text, str):
            sign_text = [sign_text]
        value = sign_text[0] if sign_text else None
    return " ".join(str(value).casefold().split()) if value else None


@router.get("")
def list_observations() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("observations").find({"study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.post("/")
def create_observation(payload: ObservationInput) -> dict[str, Any]:
    if not contains_point(payload.latitude, payload.longitude):
        raise HTTPException(status_code=422, detail="Observation is outside the official study area.")
    document = payload.model_dump(mode="python")
    document["study_area_id"] = STUDY_AREA_ID
    document.setdefault("created_at", __import__("datetime").datetime.utcnow().isoformat())
    try:
        get_collection("observations").replace_one({"observation_id": payload.observation_id}, document, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return document


@router.get("/ocr")
def list_ocr_observations() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("ocr_observations").find({"study_area_id": STUDY_AREA_ID}).limit(1000))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [_public(item) for item in items]


@router.post("/process")
def process_selected_view(payload: ProcessViewInput) -> dict[str, Any]:
    """Process one selected view and persist outputs without storing image bytes."""
    if getattr(_pipeline.vision_provider, "name", None) == "unconfigured":
        raise HTTPException(status_code=503, detail="No vision detector is configured for observation processing.")
    try:
        import base64

        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="image_base64 must contain valid base64 image data.") from exc
        if not image_bytes or len(image_bytes) > 18_000_000:
            raise HTTPException(status_code=413, detail="Decoded image must be between 1 byte and 18 MB.")
        view = get_collection("views").find_one({"view_id": payload.view_id, "study_area_id": STUDY_AREA_ID})
        if view is None:
            raise HTTPException(status_code=404, detail="Selected view not found.")
        context = {
                **{key: value for key, value in payload.image_context.items()
                    if key not in {"image", "image_bytes", "image_path", "image_url"}},
                "image_bytes": image_bytes,
            "view_id": view["view_id"],
            "panorama_reference": view.get("panorama_reference"),
            "latitude": view["latitude"],
            "longitude": view["longitude"],
            "heading": view.get("heading"),
            "pitch": view.get("pitch"),
            "field_of_view": view.get("field_of_view"),
            "source_mode": view.get("source_mode", "unknown"),
            "study_area_id": STUDY_AREA_ID,
        }
        result = _pipeline.process(context)
        observations = result["observations"]
        references = list(get_collection("reference_records").find({"study_area_id": STUDY_AREA_ID}))
        grouped_references: dict[str, list[dict[str, Any]]] = {}
        for reference in references:
            source = str(reference.get("reference_source") or reference.get("source_type") or reference.get("source") or "unspecified")
            grouped_references.setdefault(source, []).append(reference)
        reference_adapter = ReferenceDataAdapter([
            StaticReferenceProvider(source, records) for source, records in grouped_references.items()
        ])
        now = datetime.now(timezone.utc).isoformat()
        match_results: list[dict[str, Any]] = []
        reviews: list[dict[str, Any]] = []
        footprints = [reference for reference in references if reference.get("geometry")]
        for observation in observations:
            observation["created_at"] = now
            observation["positioning"] = None
            match = match_observation(observation, reference_adapter)
            match.update({"study_area_id": STUDY_AREA_ID, "created_at": now})
            observation["match_status"] = match["match_status"]
            observation["match_record"] = match
            observation["reference_id"] = match["matched_reference_id"]
            if observation["asset_type"] == "building":
                prior_buildings = list(get_collection("observations").find({
                    "study_area_id": STUDY_AREA_ID,
                    "asset_type": "building",
                    "source_view_id": {"$ne": payload.view_id},
                }).limit(2000))
                identity = _building_identity(observation)
                compatible_prior = [item for item in prior_buildings if (
                    match["match_status"] == "matched"
                    and match["matched_reference_id"] is not None
                    and str(item.get("reference_id")) == str(match["matched_reference_id"])
                ) or (identity is not None and _building_identity(item) == identity)]
                position_input = {
                    **observation,
                    "camera_latitude": view["latitude"],
                    "camera_longitude": view["longitude"],
                    "heading": view.get("heading"),
                    "reference_id": match["matched_reference_id"],
                }
                view_inputs = [{
                    **item,
                    "camera_latitude": item.get("latitude"),
                    "camera_longitude": item.get("longitude"),
                    "heading": item.get("heading"),
                } for item in compatible_prior]
                view_inputs.append(position_input)
                observation["positioning"] = PositioningService().position_building(
                    view_inputs, footprints=footprints
                )
                if observation["positioning"]["positioning_method"] == "multi_view_ray_intersection":
                    prior_ids = [item["observation_id"] for item in compatible_prior]
                    if prior_ids:
                        get_collection("observations").update_many(
                            {"observation_id": {"$in": prior_ids}, "study_area_id": STUDY_AREA_ID},
                            {"$set": {"positioning": observation["positioning"]}},
                        )
            get_collection("observations").replace_one(
                {"observation_id": observation["observation_id"]},
                with_location(observation), upsert=True,
            )
            get_collection("matches").replace_one(
                {"observation_id": observation["observation_id"]}, match, upsert=True,
            )
            match_results.append(match)
            needs_review = (
                observation["confidence"] < 0.7
                or match["match_status"] in {"unmatched", "possible_match"}
                or (observation.get("positioning") or {}).get("review_status") == "needs_review"
            )
            if needs_review:
                review = {
                    "review_id": f"review_{observation['observation_id']}",
                    "observation_id": observation["observation_id"],
                    "reason": "low_confidence_or_unmatched" if observation["confidence"] < 0.7 or match["match_status"] != "matched" else "positioning_requires_review",
                    "priority": "high" if observation["confidence"] < 0.5 else "medium",
                    "status": "needs_review" if observation["confidence"] < 0.5 else "pending",
                    "reviewer": None,
                    "reviewer_decision": None,
                    "created_at": now,
                    "reviewed_at": None,
                    "study_area_id": STUDY_AREA_ID,
                }
                get_collection("review_queue").replace_one({"review_id": review["review_id"]}, review, upsert=True)
                reviews.append(review)

        for ocr_result in result["ocr_results"]:
            ocr_result.update({"study_area_id": STUDY_AREA_ID, "created_at": now})
            get_collection("ocr_observations").replace_one({"ocr_id": ocr_result["ocr_id"]}, ocr_result, upsert=True)

        discrepancies = detect_discrepancies(observations=observations, references=references)
        for discrepancy in discrepancies:
            discrepancy.update({"study_area_id": STUDY_AREA_ID, "created_at": now})
            get_collection("discrepancies").replace_one(
                {"discrepancy_id": discrepancy["discrepancy_id"]}, discrepancy, upsert=True,
            )

        all_observations = list(get_collection("observations").find({"study_area_id": STUDY_AREA_ID}).limit(5000))
        for fused in fuse_nearby_observations(all_observations):
            fused["study_area_id"] = STUDY_AREA_ID
            get_collection("unified_entities").replace_one(
                {"canonical_observation_id": fused["canonical_observation_id"]}, with_location(fused), upsert=True,
            )

        routing = result["routing"]
        execution = result["provider_execution"]
        settings = get_settings()
        invocation_prices = {
            "detector": settings.local_detector_cost_per_invocation,
            "ocr": settings.ocr_cost_per_invocation,
            "nova_lite": settings.nova_lite_cost_per_invocation,
        }
        invocation_counts = {
            "detector": execution["detector_invocations"],
            "ocr": execution["ocr_invocations"],
            "nova_lite": execution["nova_lite_invocations"],
        }
        required_price_keys = [key for key, count in invocation_counts.items() if count]
        missing_price_keys = [key for key in required_price_keys if invocation_prices[key] is None]
        estimated_cost = None if missing_price_keys else sum(
            invocation_counts[key] * float(invocation_prices[key] or 0.0) for key in required_price_keys
        )
        cost_unavailable_reason = (
            "Configure per-invocation prices for: " + ", ".join(missing_price_keys)
            if missing_price_keys else None
        )
        all_vlm_cost = (
            settings.nova_lite_cost_per_invocation
            if settings.nova_lite_cost_per_invocation is not None else None
        )
        all_vlm_cost_reason = None if all_vlm_cost is not None else "NOVA_LITE_COST_PER_INVOCATION is not configured."
        routing["estimated_cost"] = estimated_cost
        routing["cost_status"] = "available" if estimated_cost is not None else "unavailable"
        routing["cost_unavailable_reason"] = cost_unavailable_reason
        metrics_service = ProcessingMetricsService()
        metrics = metrics_service.record_view(
            view_id=payload.view_id,
            small_model_used=True,
            vlm_used=routing.get("escalation_reason") is not None,
            model_route=routing["model_route"],
            latency_ms=result["processing_latency_ms"],
            estimated_cost=estimated_cost,
            all_vlm_cost=all_vlm_cost,
            all_vlm_cost_unavailable_reason=all_vlm_cost_reason,
            buildings_detected=sum(item["asset_type"] == "building" for item in observations),
            streetlights_detected=sum(item["asset_type"] == "streetlight" for item in observations),
            electric_poles_detected=sum(item["asset_type"] == "electric_pole" for item in observations),
            ocr_observations=len(result["ocr_results"]),
            matched_observations=sum(item["match_status"] == "matched" for item in match_results),
            unmatched_observations=sum(item["match_status"] == "unmatched" for item in match_results),
            low_confidence_observations=sum(item["confidence"] < 0.7 for item in observations),
            detector_invocations=execution["detector_invocations"],
            ocr_invocations=execution["ocr_invocations"],
            nova_lite_invocations=execution["nova_lite_invocations"],
            nova_lite_invocation_attempts=execution["nova_lite_invocation_attempts"],
            detector_latency_ms=execution["detector_latency_ms"],
            ocr_latency_ms=execution["ocr_latency_ms"],
            nova_lite_latency_ms=execution["nova_lite_latency_ms"],
            cost_status="available" if estimated_cost is not None else "unavailable",
            cost_unavailable_reason=cost_unavailable_reason,
        )
        metrics.update({"study_area_id": STUDY_AREA_ID, "created_at": now,
                        "vlm_failure": not routing.get("success", True)})
        get_collection("processing_metrics").replace_one({"view_id": payload.view_id}, metrics, upsert=True)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Local vision/OCR provider is unavailable: {exc}") from exc
    except (PyMongoError, ValueError, OSError) as exc:
        if isinstance(exc, PyMongoError):
            raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "view_id": payload.view_id,
        "observations": observations,
        "ocr_results": result["ocr_results"],
        "matches": match_results,
        "discrepancies": discrepancies,
        "review_queue_entries": reviews,
        "routing": routing,
        "metrics": metrics,
    }


@router.get("/{observation_id}")
def get_observation(observation_id: str) -> dict[str, Any]:
    try:
        item = get_collection("observations").find_one({"observation_id": observation_id, "study_area_id": STUDY_AREA_ID})
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Observation not found.")
    item.pop("_id", None)
    return item
