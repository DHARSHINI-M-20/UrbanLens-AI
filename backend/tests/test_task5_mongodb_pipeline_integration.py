from __future__ import annotations

import asyncio
import base64
import io
import math
import uuid

import httpx
import pytest

from app.api import observations as observation_api
from app.database.mongodb import check_connection, get_collection
from app.main import app
from app.services.observation_pipeline import ObservationPipelineService
from app.services.study_area_service import STUDY_AREA_ID, contains_point


class MongoRegressionDetector:
    name = "mongo_regression_fixture_detector"

    def __init__(self) -> None:
        self.invocation_count = 0
        self.last_latency_ms = 1.0

    def detect(self, view_context):
        view_id = view_context["view_id"]
        assert view_context["image_bytes"].startswith(b"\x89PNG\r\n\x1a\n")
        self.invocation_count += 1
        return [
            {
                "observation_id": f"{view_id}-building",
                "asset_type": "building",
                "confidence": 0.94,
                "bounding_region": {"x": 5, "y": 5, "width": 500, "height": 400},
            },
            {
                "observation_id": f"{view_id}-electric-pole",
                "asset_type": "electric_pole",
                "confidence": 0.91,
                "bounding_region": {"x": 550, "y": 5, "width": 40, "height": 400},
            },
        ]


class MongoRegressionOCR:
    name = "mongo_regression_fixture_ocr"

    def __init__(self) -> None:
        self.invocation_count = 0
        self.last_latency_ms = 1.0

    def recognize(self, view_context):
        self.invocation_count += 1
        return [{
            "text": "Mongo Test Cafe",
            "confidence": 0.96,
            "bounding_region": {"x": 20, "y": 40, "width": 210, "height": 32},
        }]


def test_selected_image_pipeline_persists_all_outputs_in_mongodb():
    pytest.importorskip("PIL.Image")
    if not check_connection():
        pytest.skip("Configured MongoDB is unavailable for the isolated persistence regression test.")

    from PIL import Image

    suffix = uuid.uuid4().hex
    view_ids = [f"task5-regression-{suffix}-west", f"task5-regression-{suffix}-south"]
    observation_ids = [f"{view_id}-{asset}" for view_id in view_ids for asset in ("building", "electric-pole")]
    reference_id = f"osm:task5-regression-{suffix}"
    image = Image.new("RGB", (640, 480), "white")
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_base64 = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    target_latitude, target_longitude = 11.032, 76.98
    meters_per_longitude = 111_320 * math.cos(math.radians(target_latitude))
    view_specs = [
        (view_ids[0], target_latitude, target_longitude - 4 / meters_per_longitude, 90.0),
        (view_ids[1], target_latitude - 4 / 111_320, target_longitude, 0.0),
    ]
    assert all(contains_point(latitude, longitude) for _, latitude, longitude, _ in view_specs)

    half_lat = 0.5 / 111_320
    half_lon = 0.5 / meters_per_longitude
    reference = {
        "reference_id": reference_id,
        "record_type": "building",
        "asset_type": "building",
        "name": "Mongo Test Cafe",
        "latitude": target_latitude,
        "longitude": target_longitude,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [target_longitude - half_lon, target_latitude - half_lat],
                [target_longitude + half_lon, target_latitude - half_lat],
                [target_longitude + half_lon, target_latitude + half_lat],
                [target_longitude - half_lon, target_latitude + half_lat],
                [target_longitude - half_lon, target_latitude - half_lat],
            ]],
        },
        "reference_source": "OpenStreetMap",
        "source": "OpenStreetMap",
        "source_type": "public_osm",
        "coverage_status": "incomplete_public_coverage",
        "study_area_id": STUDY_AREA_ID,
    }
    previous_pipeline = observation_api._pipeline
    try:
        get_collection("reference_records").insert_one(reference)
        for view_id, latitude, longitude, heading in view_specs:
            get_collection("views").insert_one({
                "view_id": view_id,
                "panorama_reference": f"authorized-source-fixture-{view_id}",
                "latitude": latitude,
                "longitude": longitude,
                "heading": heading,
                "pitch": None,
                "field_of_view": None,
                "study_area_id": STUDY_AREA_ID,
                "source_mode": "synthetic_fixture",
            })

        ocr_provider = MongoRegressionOCR()
        observation_api.configure_pipeline(ObservationPipelineService(
            vision_provider=MongoRegressionDetector(),
            ocr_provider=ocr_provider,
        ))

        async def process_view(view_id: str):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post("/observations/process", json={
                    "view_id": view_id,
                    "image_base64": image_base64,
                })

        responses = [asyncio.run(process_view(view_id)) for view_id, *_ in view_specs]
        assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
        second_result = responses[1].json()
        building_result = next(item for item in second_result["observations"] if item["asset_type"] == "building")
        assert building_result["positioning"]["positioning_method"] == "multi_view_ray_intersection"
        assert abs(building_result["positioning"]["latitude"] - target_latitude) < 1e-8
        assert abs(building_result["positioning"]["longitude"] - target_longitude) < 1e-8
        assert building_result["match_status"] == "matched"
        assert second_result["ocr_results"]
        assert any(item["discrepancy_type"] == "unmatched_reference_coverage_limited"
                   for item in second_result["discrepancies"])
        assert second_result["review_queue_entries"]
        assert second_result["metrics"]["actual_invocation_count"] >= 2

        stored_building = get_collection("observations").find_one({"observation_id": f"{view_ids[1]}-building"})
        assert stored_building["positioning"]["positioning_method"] == "multi_view_ray_intersection"
        stored_fused = list(get_collection("unified_entities").find({
            "source_observation_ids": {"$all": [f"{view_ids[0]}-building", f"{view_ids[1]}-building"]},
        }))
        assert len(stored_fused) == 1
        assert abs(stored_fused[0]["latitude"] - target_latitude) < 1e-8
        assert abs(stored_fused[0]["longitude"] - target_longitude) < 1e-8
        assert get_collection("ocr_observations").count_documents({"source_view_id": {"$in": view_ids}}) == 2
        assert get_collection("matches").count_documents({"observation_id": {"$in": observation_ids}}) == 4
        assert get_collection("discrepancies").count_documents({"observation_id": {"$in": observation_ids}}) >= 1
        assert get_collection("review_queue").count_documents({"observation_id": {"$in": observation_ids}}) >= 1
        assert get_collection("processing_metrics").count_documents({"view_id": {"$in": view_ids}}) == 2
    finally:
        observation_api._pipeline = previous_pipeline
        get_collection("observations").delete_many({"observation_id": {"$in": observation_ids}})
        get_collection("matches").delete_many({"observation_id": {"$in": observation_ids}})
        get_collection("ocr_observations").delete_many({"source_view_id": {"$in": view_ids}})
        get_collection("discrepancies").delete_many({"observation_id": {"$in": observation_ids}})
        get_collection("review_queue").delete_many({"observation_id": {"$in": observation_ids}})
        get_collection("unified_entities").delete_many({
            "source_observation_ids": {"$in": observation_ids},
        })
        get_collection("processing_metrics").delete_many({"view_id": {"$in": view_ids}})
        get_collection("views").delete_many({"view_id": {"$in": view_ids}})
        get_collection("reference_records").delete_many({"reference_id": reference_id})
