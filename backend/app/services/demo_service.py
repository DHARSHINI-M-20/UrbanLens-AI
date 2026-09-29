"""Dataset-scoped deterministic Task 5 demonstration workflow."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw
from shapely.geometry import LineString, box, mapping, shape

from app.api import observations as observation_api, panoramas as panorama_api, views as view_api
from app.config import get_settings
from app.database.mongodb import get_collection
from app.models.panorama import Panorama
from app.services.observation_pipeline import ObservationPipelineService
from app.services.ocr_service import MockOCRProvider
from app.services.reference_matching_service import ReferenceDataAdapter
from app.services.simulated_streetview_provider import SIMULATION_LABEL, SimulatedStreetViewProvider
from app.services.streetview_service import normalize_panorama_metadata
from app.services.study_area_service import STUDY_AREA_ID, get_study_area_geojson, get_study_area_geometry
from app.services.vision_service import MockVisionProvider
from app.services.view_selection_service import select_useful_views

DEMO_DATASET_ID = "urbanlens-task5-sim-v1"
DEMO_SOURCE = "SIMULATED_DEMONSTRATION"
REFERENCE_SOURCE = "SIMULATED_REFERENCE_REGISTER"

BASE_COLLECTIONS = (
    "study_areas", "streets", "sampling_points", "panoramas", "views", "reference_records",
)
OUTPUT_COLLECTIONS = (
    "observations", "unified_entities", "matches", "discrepancies", "review_queue",
    "processing_metrics", "ocr_observations",
)
ALL_DEMO_COLLECTIONS = BASE_COLLECTIONS + OUTPUT_COLLECTIONS + ("processing_runs", "demo_datasets")

BUILDING_NAMES = (
    ("GREEN MART", "ABC MEDICALS", "TECH PARK", "STAR RESTAURANT", "LOTUS RESIDENCE", "CENTRAL BANK"),
    ("NORTH CLINIC", "RIVER CAFE", "CITY LIBRARY", "CORNER SHOP", "METRO OFFICE", "EAST HOMES"),
    ("PARK VIEW", "SUNRISE STORES", "HILL SCHOOL", "MARKET HOUSE", "LAKE CLINIC", "SOUTH TOWER"),
)
OCR_TEXT = BUILDING_NAMES


class SimulatedVisionProvider:
    """Explicit deterministic detector fixture; never claims model inference."""

    name = "simulated_fixture"
    detector_type = "simulated_fixture"
    invocation_count = 0
    last_latency_ms = 3.0

    def __init__(self, view_id: str) -> None:
        self.view_id = view_id
        self.invocation_count = 0

    def detect(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        self.invocation_count += 1
        group_index = int(self.view_id.split("_")[-1][:2])
        side = self.view_id[-1]
        detections: list[dict[str, Any]] = []
        for index, name in enumerate(BUILDING_NAMES[group_index - 1]):
            confidence = 0.43 if group_index == 2 and side == "b" and index == 3 else 0.84 + index * 0.03
            building_use = ("commercial", "commercial", "mixed_use", "restaurant", "residential", "institutional")[index % 6]
            visible_floors = (3, 4, 2, 3, 1, 5)[index % 6]
            detections.append({
                "observation_id": f"{self.view_id}_building_{index + 1}",
                "asset_type": "building",
                "confidence": confidence,
                "building_name": name,
                "building_use": building_use,
                "visible_floor_count": visible_floors,
                "frontage": ("wide", "narrow", "corner", "street-facing", "setback", "wide")[index % 6],
                "condition": ("good", "fair", "good", "unknown", "fair", "good")[index % 6],
                "bounding_region": {"x": 20 + index * 145, "y": 40, "width": 125, "height": 360},
                "model_name": self.name,
                "source": DEMO_SOURCE,
                "detector_type": self.detector_type,
                "processing_time_ms": self.last_latency_ms,
            })

        if group_index != 1 or side != "a":
            for index in range(3):
                detections.append({
                    "observation_id": f"{self.view_id}_streetlight_{index + 1}",
                    "asset_type": "streetlight",
                    "confidence": 0.78 + index * 0.04,
                    "attributes": {"fixture_index": index + 1, "operational_status": "unknown"},
                    "bounding_region": {"x": 40 + index * 180, "y": 8, "width": 28, "height": 420},
                    "model_name": self.name,
                    "source": DEMO_SOURCE,
                    "detector_type": self.detector_type,
                    "processing_time_ms": self.last_latency_ms,
                })
            for index in range(2):
                detections.append({
                    "observation_id": f"{self.view_id}_electric_pole_{index + 1}",
                    "asset_type": "electric_pole",
                    "confidence": 0.75 + index * 0.08,
                    "attributes": {"fixture_index": index + 1, "condition": "not_assessed"},
                    "bounding_region": {"x": 620 + index * 80, "y": 50, "width": 36, "height": 370},
                    "model_name": self.name,
                    "source": DEMO_SOURCE,
                    "detector_type": self.detector_type,
                    "processing_time_ms": self.last_latency_ms,
                })
            detections.append({
                "observation_id": f"{self.view_id}_signboard_1",
                "asset_type": "signboard",
                "confidence": 0.71,
                "attributes": {"text_role": "business_sign"},
                "bounding_region": {"x": 32, "y": 70, "width": 100, "height": 38},
                "model_name": self.name,
                "source": DEMO_SOURCE,
                "detector_type": self.detector_type,
                "processing_time_ms": self.last_latency_ms,
            })
        return detections


class SimulatedOCRProvider(MockOCRProvider):
    name = "simulated_ocr_fixture"

    def __init__(self, view_id: str) -> None:
        group_index = int(view_id.split("_")[-1][:2])
        self.results = tuple({
            "ocr_id": f"{view_id}_ocr_{index + 1}",
            "text": text,
            "confidence": 0.91 - index * 0.03,
            "bounding_region": {"x": 28 + index * 145, "y": 62, "width": 110, "height": 32},
            "source": self.name,
            "processing_time_ms": 2.0,
        } for index, text in enumerate(OCR_TEXT[group_index - 1][:3]))
        self.invocation_count = 0
        self.last_latency_ms = 2.0

    def recognize(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        self.invocation_count += 1
        return self.results


class SimulatedNovaLiteService:
    """Mock response using the existing router/schema without AWS access."""

    is_simulated = True

    def invoke_nova_lite(self, prompt: str, *, image_bytes: bytes | None = None):
        from app.services.bedrock_service import BedrockInvocationResult

        return BedrockInvocationResult(
            status="ok",
            model_id="simulated_nova_lite_mock",
            response={"text": json.dumps({
                "building_use": "commercial",
                "visible_floor_count": 3,
                "frontage": "street-facing",
                "condition": "visual assessment required",
                "building_name": None,
                "confidence": 0.68,
                "uncertainty_indicators": ["simulated_response_not_model_output"],
                "reasoning_summary": "Deterministic mock escalation for demonstration only.",
            })},
            latency_ms=12.0,
            success=True,
        )

    @staticmethod
    def parse_structured_response(payload: dict[str, Any]):
        from app.services.bedrock_service import NovaLiteStructuredResponse

        return NovaLiteStructuredResponse.model_validate(json.loads(payload["text"]))


def _scoped_delete(collection: str) -> None:
    get_collection(collection).delete_many({"dataset_id": DEMO_DATASET_ID})


def reset_demo_dataset() -> dict[str, Any]:
    """Delete only records owned by this fixed demo dataset identifier."""
    deleted: dict[str, int] = {}
    for name in ALL_DEMO_COLLECTIONS:
        result = get_collection(name).delete_many({"dataset_id": DEMO_DATASET_ID})
        deleted[name] = result.deleted_count
    return {"dataset_id": DEMO_DATASET_ID, "deleted_by_collection": deleted}


def _build_reference_records(provider: SimulatedStreetViewProvider) -> list[dict[str, Any]]:
    targets = provider.group_targets()
    references: list[dict[str, Any]] = []
    for group_number, (group_id, (latitude, longitude)) in enumerate(targets.items(), start=1):
        if group_number <= 2:
            for index, name in enumerate(BUILDING_NAMES[group_number - 1][:3]):
                expected_use = ("commercial", "commercial", "commercial")[index]
                expected_floors = (3, 2, 4)[index]
                reference: dict[str, Any] = {
                    "reference_id": f"sim_ref_{group_number:02d}_building_{index + 1}",
                    "record_type": "building",
                    "asset_type": "building",
                    "name": name,
                    "building_name": name,
                    "building_use": expected_use,
                    "visible_floor_count": expected_floors,
                    "latitude": latitude,
                    "longitude": longitude,
                }
                if group_number == 1 and index == 0:
                    delta_lat = 2.0 / 111_320
                    delta_lon = 2.0 / (111_320 * __import__("math").cos(__import__("math").radians(latitude)))
                    reference["geometry"] = mapping(box(
                        longitude - delta_lon, latitude - delta_lat,
                        longitude + delta_lon, latitude + delta_lat,
                    ))
                references.append(reference)

            for asset_type, count in (("streetlight", 2), ("electric_pole", 2)):
                for index in range(count):
                    references.append({
                        "reference_id": f"sim_ref_{group_number:02d}_{asset_type}_{index + 1}",
                        "record_type": asset_type,
                        "asset_type": asset_type,
                        "name": f"{group_id}_{asset_type}_{index + 1}",
                        "latitude": latitude,
                        "longitude": longitude,
                    })
        # This expected fixture exists only inside the synthetic register.
        if group_number == 1:
            references.append({
                "reference_id": "sim_ref_expected_missing_streetlight",
                "record_type": "streetlight",
                "asset_type": "streetlight",
                "name": "simulated_expected_streetlight_not_observed",
                "latitude": latitude + 0.00035,
                "longitude": longitude + 0.00035,
            })

    for reference in references:
        reference.update({
            "source": REFERENCE_SOURCE,
            "reference_source": REFERENCE_SOURCE,
            "source_type": "simulated_demo",
            "coverage_status": "simulated_complete",
            "study_area_id": STUDY_AREA_ID,
            "dataset_id": DEMO_DATASET_ID,
            "simulation": True,
            "provenance": SIMULATION_LABEL,
            "attribution": "Synthetic fixture; not FarmwiseAI data.",
        })
    return references


def _synthetic_png(view_id: str) -> bytes:
    image = Image.new("RGB", (1000, 500), "#d9e2e8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 310, 1000, 500), fill="#89989f")
    for index, name in enumerate(BUILDING_NAMES[int(view_id.split("_")[-1][:2]) - 1]):
        left = 20 + index * 145
        draw.rectangle((left, 90, left + 125, 400), fill="#bdc7c9", outline="#59656a", width=3)
        draw.rectangle((left + 14, 70, left + 111, 100), fill="#f7f2d9", outline="#59656a", width=2)
        draw.text((left + 18, 79), name[:12], fill="#17252a")
    draw.text((15, 15), "SIMULATED DEMONSTRATION - NOT GOOGLE STREET VIEW", fill="#102027")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _insert_base_dataset() -> dict[str, Any]:
    geojson = get_study_area_geojson()
    area = shape(get_study_area_geometry())
    provider = SimulatedStreetViewProvider(dataset_id=DEMO_DATASET_ID)
    targets = provider.group_targets()

    get_collection("study_areas").replace_one(
        {"dataset_id": DEMO_DATASET_ID},
        {
            "study_area_id": STUDY_AREA_ID,
            "dataset_id": DEMO_DATASET_ID,
            "source": SIMULATION_LABEL,
            "status": "demo_only",
            "simulation": True,
            "boundary_source": "official challenge GeoJSON; boundary only",
            "geometry": geojson["features"][0]["geometry"],
        },
        upsert=True,
    )

    streets: list[dict[str, Any]] = []
    for group_number, (group_id, _) in enumerate(targets.items(), start=1):
        pair = [item for item in provider.all_metadata() if item["group_id"] == group_id]
        geometry = LineString([(item["longitude"], item["latitude"]) for item in pair])
        streets.append({
            "street_id": f"{DEMO_DATASET_ID}:street_{group_number:02d}",
            "name": ("Green Market Road", "North Clinic Street", "Park View Avenue")[group_number - 1],
            "geometry": mapping(geometry.intersection(area)),
            "study_area_id": STUDY_AREA_ID,
            "dataset_id": DEMO_DATASET_ID,
            "source": DEMO_SOURCE,
            "source_type": "participant_generated",
            "simulation": True,
            "provenance": SIMULATION_LABEL,
            "status": "ready",
        })
    get_collection("streets").insert_many(streets)

    from app.services.sampling_service import generate_sampling_points

    samples, _ = generate_sampling_points(250)
    sample_count = min(8, len(samples))
    if sample_count:
        indexes = sorted({round(index * (len(samples) - 1) / max(1, sample_count - 1)) for index in range(sample_count)})
        selected = [samples[index] for index in indexes]
        for index, sample in enumerate(selected, start=1):
            sample.update({
                "sample_id": f"{DEMO_DATASET_ID}:sample_{index:02d}",
                "dataset_id": DEMO_DATASET_ID,
                "source": DEMO_SOURCE,
                "simulation": True,
                "provenance": SIMULATION_LABEL,
            })
        get_collection("sampling_points").insert_many(selected)

    previous_provider = panorama_api._provider
    panorama_api.configure_provider(provider)
    panorama_ids: list[str] = []
    group_by_panorama: dict[str, str] = {}
    try:
        for metadata in provider.all_metadata():
            registered = panorama_api.discover_panorama(panorama_api.PanoramaDiscoveryInput(
                latitude=metadata["latitude"],
                longitude=metadata["longitude"],
                radius_meters=2,
            ))
            panorama_ids.append(registered["panorama_id"])
            group_by_panorama[registered["panorama_id"]] = metadata["group_id"]
    finally:
        panorama_api.configure_provider(previous_provider)

    selection = view_api.select_views(view_api.ViewSelectionInput(
        panorama_ids=panorama_ids,
        duplicate_distance_meters=12,
    ))
    view_documents = selection["views"]
    streets_by_group = {
        group_id: f"{DEMO_DATASET_ID}:street_{index:02d}"
        for index, group_id in enumerate(targets, start=1)
    }
    for document in view_documents:
        group_id = group_by_panorama.get(document["panorama_reference"])
        document.update({
            "street_id": streets_by_group[group_id],
            "dataset_id": DEMO_DATASET_ID,
            "simulation": True,
            "provider": "simulated",
            "provenance": SIMULATION_LABEL,
        })
        get_collection("views").replace_one({"view_id": document["view_id"]}, document, upsert=True)

    references = _build_reference_records(provider)
    for reference in references:
        reference["reference_id"] = f"{DEMO_DATASET_ID}:{reference['reference_id']}"
    if references:
        get_collection("reference_records").insert_many(references)
    get_collection("demo_datasets").replace_one(
        {"dataset_id": DEMO_DATASET_ID},
        {
            "dataset_id": DEMO_DATASET_ID,
            "label": SIMULATION_LABEL,
            "source": DEMO_SOURCE,
            "simulation": True,
            "study_area_id": STUDY_AREA_ID,
            "status": "seeded",
            "streets": len(streets),
            "panoramas": len(panorama_ids),
            "views": len(view_documents),
            "references": len(references),
        },
        upsert=True,
    )
    return {
        "dataset_id": DEMO_DATASET_ID,
        "label": SIMULATION_LABEL,
        "streets": len(streets),
        "sampling_points": sample_count,
        "panoramas": len(panorama_ids),
        "views": len(view_documents),
        "references": len(references),
        "provider": "simulated",
        "simulation": True,
    }


def _make_pipeline(view_id: str) -> ObservationPipelineService:
    return ObservationPipelineService(
        vision_provider=SimulatedVisionProvider(view_id),
        ocr_provider=SimulatedOCRProvider(view_id),
        bedrock_service=SimulatedNovaLiteService(),
    )


def run_demo_dataset() -> dict[str, Any]:
    """Replay every selected simulated view through the production API pipeline."""
    dataset = get_collection("demo_datasets").find_one({"dataset_id": DEMO_DATASET_ID})
    if dataset is None:
        raise ValueError("Simulated dataset is not seeded; call POST /demo/seed first.")
    for name in OUTPUT_COLLECTIONS:
        _scoped_delete(name)

    previous_pipeline = observation_api._pipeline
    results: list[dict[str, Any]] = []
    try:
        views = list(get_collection("views").find({
            "dataset_id": DEMO_DATASET_ID,
            "study_area_id": STUDY_AREA_ID,
        }).sort("view_id", 1))
        for view in views:
            observation_api.configure_pipeline(_make_pipeline(view["view_id"]))
            image_bytes = _synthetic_png(view["view_id"])
            request = observation_api.ProcessViewInput(
                view_id=view["view_id"],
                image_base64=base64.b64encode(image_bytes).decode("ascii"),
                image_context={
                    "dataset_id": DEMO_DATASET_ID,
                    "simulation": True,
                    "source": DEMO_SOURCE,
                    "provenance": SIMULATION_LABEL,
                },
            )
            results.append(observation_api.process_selected_view(request))
    finally:
        observation_api.configure_pipeline(previous_pipeline)

    get_collection("demo_datasets").update_one(
        {"dataset_id": DEMO_DATASET_ID},
        {"$set": {"status": "processed", "processed_views": len(results)}},
    )
    return {
        "dataset_id": DEMO_DATASET_ID,
        "label": SIMULATION_LABEL,
        "processed_views": len(results),
        "observations": sum(len(item["observations"]) for item in results),
        "ocr_observations": sum(len(item["ocr_results"]) for item in results),
        "matches": sum(len(item["matches"]) for item in results),
        "discrepancies": sum(len(item["discrepancies"]) for item in results),
        "review_queue_entries": sum(len(item["review_queue_entries"]) for item in results),
        "routing": [item["routing"]["model_route"] for item in results],
        "simulation": True,
    }


def seed_demo_dataset() -> dict[str, Any]:
    reset_demo_dataset()
    base = _insert_base_dataset()
    processed = run_demo_dataset()
    return {**base, "processing": processed}


def demo_status() -> dict[str, Any]:
    dataset = get_collection("demo_datasets").find_one({"dataset_id": DEMO_DATASET_ID})
    if dataset is None:
        return {"seeded": False, "dataset_id": DEMO_DATASET_ID, "label": SIMULATION_LABEL, "simulation": True}
    counts = {name: get_collection(name).count_documents({"dataset_id": DEMO_DATASET_ID}) for name in ALL_DEMO_COLLECTIONS}
    dataset.pop("_id", None)
    return {"seeded": True, "dataset": dataset, "counts": counts, "simulation": True}
