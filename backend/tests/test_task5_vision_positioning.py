from __future__ import annotations

import asyncio

import httpx

from app.main import app
from app.services.ocr_service import MockOCRProvider, process_view_ocr
from app.services.discrepancy_service import detect_discrepancies
from app.services.observation_pipeline import ObservationPipelineService
from app.services.observation_fusion_service import fuse_nearby_observations
from app.services.positioning_service import PositioningService
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.reference_matching_service import (
    ReferenceDataAdapter,
    StaticReferenceProvider,
    match_observation,
)
from app.services.review_service import ReviewService
from app.services.vision_service import MockVisionProvider, UnconfiguredVisionProvider, detect_view_observations


class MockBedrock:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls = 0
        self.received_images = []
        self.received_prompts = []

    def invoke_nova_lite(self, prompt, *, image_bytes=None):
        self.calls += 1
        self.received_images.append(image_bytes)
        self.received_prompts.append(prompt)
        if self.failure:
            raise self.failure
        return type("Invocation", (), {
            "status": "ok", "response": {"text": '{"building_use":"commercial","confidence":0.94}'},
            "latency_ms": 12.0, "error": None,
        })()

    @staticmethod
    def parse_structured_response(payload):
        from app.services.bedrock_service import NovaLiteStructuredResponse
        import json
        return NovaLiteStructuredResponse.model_validate(json.loads(payload["text"]))


def test_building_and_infrastructure_detections_are_normalized(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    provider = MockVisionProvider([
        {"asset_type": "building", "confidence": 0.91, "visible_floor_count": 3,
         "building_use": "commercial", "business_name": "Cafe North"},
        {"asset_type": "streetlight", "confidence": 0.82},
        {"asset_type": "electric pole", "confidence": 0.76},
        {"asset_type": "made_up_object", "confidence": 0.99},
        {"asset_type": "building", "confidence": 1.2},
    ])
    observations = detect_view_observations(
        {"view_id": "view-1", "panorama_reference": "fixture-pano", "latitude": 11.032,
         "longitude": 76.98, "source_mode": "synthetic_fixture"},
        provider,
    )
    assert [item["asset_type"] for item in observations] == ["building", "streetlight", "electric_pole"]
    assert observations[0]["attributes"] == {
        "visible_floor_count": 3, "building_use": "commercial", "business_name": "Cafe North"
    }
    assert observations[0]["source_mode"] == "synthetic_fixture"
    assert observations[1]["source_view_id"] == "view-1"


def test_vision_rejects_view_outside_study_area(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: False)
    try:
        detect_view_observations(
            {"view_id": "view-out", "latitude": 11.032, "longitude": 76.98},
            MockVisionProvider([]),
        )
    except ValueError as error:
        assert "outside the official study area" in str(error)
    else:
        raise AssertionError("Out-of-area view was accepted")


def test_ocr_preserves_raw_text_and_normalizes_for_matching():
    results = process_view_ocr(
        {"view_id": "view-ocr"},
        MockOCRProvider([{
            "text": "  Cafe\u00a0  North  ", "confidence": 0.87,
            "bounding_region": {"x": 10, "y": 20, "width": 30, "height": 15},
        }]),
    )
    assert results[0]["raw_text"] == "  Cafe\u00a0  North  "
    assert results[0]["normalized_text"] == "Cafe North"
    assert results[0]["source_view_id"] == "view-ocr"
    assert results[0]["review_status"] == "pending"


def test_positioning_triangulates_two_forward_camera_rays():
    target_latitude, target_longitude = 11.032, 76.98
    meters_per_longitude = 111_320 * __import__("math").cos(__import__("math").radians(target_latitude))
    views = [
        {"source_view_id": "west", "latitude": target_latitude,
         "longitude": target_longitude - 10 / meters_per_longitude, "heading": 90},
        {"source_view_id": "south", "latitude": target_latitude - 10 / 111_320,
         "longitude": target_longitude, "heading": 0},
    ]
    positioned = PositioningService().position_building(views)
    assert positioned["positioning_method"] == "multi_view_ray_intersection"
    assert positioned["source_views"] == ["west", "south"]
    assert abs(positioned["latitude"] - target_latitude) < 1e-8
    assert abs(positioned["longitude"] - target_longitude) < 1e-8
    assert positioned["positioning_confidence"] is None
    assert positioned["positioning_confidence_status"] == "unvalidated_low"
    assert positioned["review_status"] == "needs_review"


def test_positioning_triangulation_reports_insufficient_views():
    result = PositioningService().triangulate_views([
        {"source_view_id": "only", "latitude": 11.032, "longitude": 76.98, "heading": 0},
    ])
    assert result["positioning_method"] == "unavailable_insufficient_views"
    assert result["latitude"] is None and result["longitude"] is None


def test_positioning_triangulation_rejects_invalid_geometry():
    result = PositioningService().triangulate_views([
        {"source_view_id": "valid", "latitude": 11.032, "longitude": 76.98, "heading": 90},
        {"source_view_id": "invalid", "latitude": 91, "longitude": 76.98, "heading": 0},
    ])
    assert result["positioning_method"] == "unavailable_invalid_view_geometry"
    assert result["latitude"] is None and result["longitude"] is None


def test_positioning_triangulation_rejects_inconsistent_observations():
    target_latitude, target_longitude = 11.032, 76.98
    meters_per_longitude = 111_320 * __import__("math").cos(__import__("math").radians(target_latitude))
    result = PositioningService(max_ray_residual_meters=2.0).triangulate_views([
        {"source_view_id": "west", "latitude": target_latitude,
         "longitude": target_longitude - 10 / meters_per_longitude, "heading": 90},
        {"source_view_id": "south", "latitude": target_latitude - 10 / 111_320,
         "longitude": target_longitude, "heading": 0},
        {"source_view_id": "east-inconsistent", "latitude": target_latitude,
         "longitude": target_longitude + 10 / meters_per_longitude, "heading": 0},
    ])
    assert result["positioning_method"] == "unavailable_inconsistent_view_geometry"
    assert result["max_ray_residual_meters"] > 2.0
    assert result["latitude"] is None and result["longitude"] is None


def test_positioning_intersects_osm_footprint_without_inventing_confidence():
    footprint = {
        "reference_id": "osm-building-1",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[76.979, 11.033], [76.981, 11.033], [76.981, 11.034],
                             [76.979, 11.034], [76.979, 11.033]]],
        },
    }
    positioned = PositioningService().position_building([
        {"source_view_id": "v1", "latitude": 11.032, "longitude": 76.98, "heading": 0},
    ], footprints=[footprint])
    assert positioned["positioning_method"] == "line_of_sight_footprint_intersection"
    assert positioned["building_reference_id"] == "osm-building-1"
    assert positioned["latitude"] > 11.032
    assert positioned["positioning_confidence"] is None
    assert positioned["review_status"] == "needs_review"


def test_positioning_without_footprint_retains_camera_location_for_review():
    positioned = PositioningService().position_building([
        {"source_view_id": "v1", "latitude": 11.032, "longitude": 76.98},
    ])
    assert positioned["positioning_method"] == "camera_location_approximation"
    assert positioned["latitude"] == 11.032
    assert positioned["longitude"] == 76.98
    assert positioned["positioning_confidence"] is None
    assert positioned["review_status"] == "needs_review"


def test_high_confidence_view_does_not_call_nova(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    bedrock = MockBedrock()
    result = ObservationPipelineService(
        vision_provider=MockVisionProvider([{"asset_type": "building", "confidence": 0.96}]),
        bedrock_service=bedrock,
    ).process({"view_id": "v-high", "latitude": 11.032, "longitude": 76.98})
    assert bedrock.calls == 0
    assert result["routing"]["model_route"] == "small_model"
    assert result["routing"]["estimated_cost"] is None
    assert result["observations"][0]["confidence_before_escalation"] == 0.96


def test_low_confidence_escalates_and_records_final_confidence(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    bedrock = MockBedrock()
    result = ObservationPipelineService(
        vision_provider=MockVisionProvider([{"asset_type": "building", "confidence": 0.41}]),
        bedrock_service=bedrock,
    ).process({"view_id": "v-low", "latitude": 11.032, "longitude": 76.98})
    assert bedrock.calls == 1
    assert result["routing"]["model_route"] == "vlm_escalation"
    assert result["routing"]["confidence_before_escalation"] == 0.41
    assert result["routing"]["final_confidence"] == 0.94
    assert result["routing"]["estimated_cost"] is None


def test_pipeline_forwards_selected_image_and_view_context_to_nova(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    image_bytes = b"\x89PNG\r\n\x1a\nselected-view-fixture"
    bedrock = MockBedrock()
    result = ObservationPipelineService(
        vision_provider=MockVisionProvider([{"asset_type": "building", "confidence": 0.42}]),
        bedrock_service=bedrock,
    ).process({
        "view_id": "v-image-escalation", "panorama_reference": "authorized-provider-ref",
        "latitude": 11.032, "longitude": 76.98, "heading": 121.5,
        "pitch": -2.0, "field_of_view": 70.0, "image_bytes": image_bytes,
    })
    assert result["routing"]["model_route"] == "vlm_escalation"
    assert bedrock.received_images == [image_bytes]
    assert '"heading": 121.5' in bedrock.received_prompts[0]
    assert "authorized-provider-ref" in bedrock.received_prompts[0]


def test_nova_failure_keeps_small_model_observation(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    bedrock = MockBedrock(failure=RuntimeError("credentials unavailable"))
    result = ObservationPipelineService(
        vision_provider=MockVisionProvider([{"asset_type": "electric_pole", "confidence": 0.31}]),
        bedrock_service=bedrock,
    ).process({"view_id": "v-fail", "latitude": 11.032, "longitude": 76.98})
    assert bedrock.calls == 1
    assert result["routing"]["model_route"] == "small_model"
    assert "credentials unavailable" in result["routing"]["failure_reason"]
    assert result["observations"][0]["asset_type"] == "electric_pole"
    assert result["observations"][0]["confidence"] == 0.31
    assert result["provider_execution"]["nova_lite_invocations"] == 0
    assert result["provider_execution"]["nova_lite_invocation_attempts"] == 1


def test_spatial_fusion_preserves_distinct_view_provenance():
    fused = fuse_nearby_observations([
        {"observation_id": "o1", "asset_type": "streetlight", "latitude": 11.032,
         "longitude": 76.98, "source_view_id": "v1", "confidence": 0.81},
        {"observation_id": "o2", "asset_type": "streetlight", "latitude": 11.03201,
         "longitude": 76.98001, "source_view_id": "v2", "confidence": 0.75},
        {"observation_id": "o3", "asset_type": "building", "latitude": 11.032,
         "longitude": 76.98, "source_view_id": "v3", "confidence": 0.9},
    ])
    assert len(fused) == 1
    assert fused[0]["source_observation_ids"] == ["o1", "o2"]
    assert fused[0]["supporting_view_count"] == 2
    assert fused[0]["fusion_method"] == "spatial_proximity_and_attribute_compatibility"


def test_reference_adapter_matches_explicit_synthetic_fixture():
    adapter = ReferenceDataAdapter([StaticReferenceProvider("synthetic_demo", [{
        "reference_id": "ref-cafe", "record_type": "building", "business_name": "Cafe North",
        "name": "Cafe North", "building_use": "commercial", "latitude": 11.032,
        "longitude": 76.98,
    }])])
    match = match_observation({
        "observation_id": "obs-cafe", "asset_type": "building", "latitude": 11.032,
        "longitude": 76.98, "attributes": {"business_name": "Cafe North", "building_use": "commercial"},
    }, adapter)
    assert match["status"] == "MATCHED"
    assert match["reference_source"] == "synthetic_demo"
    assert match["matched_reference_id"] == "ref-cafe"


def test_unmatched_observation_and_reference_attribute_differences_generate_discrepancies():
    observations = [{
        "observation_id": "obs-cafe", "asset_type": "building", "latitude": 11.032,
        "longitude": 76.98, "source_view_id": "view-1", "confidence": 0.42,
        "attributes": {"business_name": "Cafe North", "building_use": "commercial", "visible_floor_count": 2},
    }, {
        "observation_id": "obs-unmatched", "asset_type": "electric_pole", "latitude": 11.035,
        "longitude": 76.983, "source_view_id": "view-2", "confidence": 0.88,
    }]
    references = [{
        "reference_id": "ref-cafe", "record_type": "building", "name": "Cafe North",
        "business_name": "Cafe North", "building_use": "residential", "visible_floor_count": 4,
        "latitude": 11.032, "longitude": 76.98,
        "source_type": "farmwise_internal", "coverage_status": "complete",
    }, {
        "reference_id": "ref-light", "record_type": "streetlight", "latitude": 11.033,
        "longitude": 76.981, "source_type": "farmwise_internal", "coverage_status": "complete",
    }]
    discrepancies = detect_discrepancies(observations=observations, references=references)
    types = {item["discrepancy_type"] for item in discrepancies}
    assert {"low_confidence_observation", "building_use_mismatch", "floor_count_mismatch",
            "missing_reference_record", "expected_streetlight_not_observed"} <= types
    assert all("review_status" in item and "evidence_source_views" in item for item in discrepancies)


def test_review_queue_records_decision_and_timestamp():
    service = ReviewService()
    entry = service.create_review_entry(observation_id="obs-1", reason="unmatched")
    updated = service.record_decision(entry["review_id"], status="approved", reviewer="reviewer-7",
                                      reviewer_decision="confirmed")
    assert updated["status"] == "approved"
    assert updated["reviewer"] == "reviewer-7"
    assert updated["reviewer_decision"] == "confirmed"
    assert updated["reviewed_at"]


def test_metrics_costs_remain_unavailable_without_pricing_data():
    service = ProcessingMetricsService()
    service.record_view(view_id="view-1", small_model_used=True, vlm_used=False,
                        model_route="small_model", latency_ms=37, estimated_cost=None,
                        buildings_detected=1, low_confidence_observations=1)
    summary = service.summary()
    comparison = service.hypothetical_all_vlm_comparison()
    assert summary["buildings_detected"] == 1
    assert summary["low_confidence_observations"] == 1
    assert summary["estimated_total_cost"] is None
    assert summary["cost_status"] == "unavailable"
    assert comparison["all_selected_views_to_vlm_cost"] is None


def test_view_api_rejects_invalid_camera_metadata_and_out_of_area_views(monkeypatch):
    async def make_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/views/register", json={
                "view_id": "invalid-view", "panorama_reference": "fixture-only",
                "latitude": 120, "longitude": 76.98, "heading": 361,
            })

    response = asyncio.run(make_request())
    assert response.status_code == 422

    monkeypatch.setattr("app.api.views.contains_point", lambda latitude, longitude: False)

    async def make_out_of_area_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/views/register", json={
                "view_id": "outside-view", "panorama_reference": "fixture-only",
                "latitude": 11.032, "longitude": 76.98, "heading": 90,
            })

    out_of_area_response = asyncio.run(make_out_of_area_request())
    assert out_of_area_response.status_code == 422


def test_process_view_api_reports_missing_vision_provider(monkeypatch):
    monkeypatch.setattr(
        "app.api.observations._pipeline",
        ObservationPipelineService(vision_provider=UnconfiguredVisionProvider()),
    )

    async def make_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/observations/process", json={"view_id": "view-1", "image_base64": "eA=="})

    response = asyncio.run(make_request())
    assert response.status_code == 503
    assert "No vision detector is configured" in response.json()["detail"]
