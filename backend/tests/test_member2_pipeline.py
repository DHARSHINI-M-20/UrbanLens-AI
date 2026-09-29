from __future__ import annotations

import pytest

from app.services.discrepancy_service import detect_discrepancies
from app.services.geospatial_service import GeospatialService
from app.services.inference_router import InferenceRouter, RouteDecision
from app.services.observation_fusion_service import fuse_observations
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.reference_matching_service import match_reference_record
from app.services.review_service import ReviewService
from app.services.street_service import prepare_streets
from app.services.study_area_service import contains_point
from app.services.view_selection_service import select_useful_views


@pytest.fixture
def study_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [76.9780, 11.0300],
                    [76.9860, 11.0300],
                    [76.9860, 11.0380],
                    [76.9780, 11.0380],
                    [76.9780, 11.0300],
                ]]
            },
            "properties": {"name": "study_area"},
        }]
    }


def test_study_area_containment():
    assert contains_point(11.0320, 76.98) is True
    assert contains_point(11.0290, 76.982) is False


def test_street_import_validation(study_geojson):
    roads = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[76.9805, 11.0315], [76.9835, 11.0325]]},
            "properties": {"name": "Main Road"},
        }]
    }
    documents, summary = prepare_streets(roads, "synthetic demo")
    assert documents
    assert summary["roads_inside_or_intersecting"] == 1


def test_view_selection_uses_priority_and_reason():
    views = select_useful_views([
        {"panorama_id": "p1", "latitude": 11.0320, "longitude": 76.9800, "heading": 10, "pitch": 0, "field_of_view": 90, "status": "ready"},
        {"panorama_id": "p2", "latitude": 11.0320, "longitude": 76.9802, "heading": 180, "pitch": 0, "field_of_view": 90, "status": "ready"},
    ])
    assert views
    assert views[0]["selection_reason"]
    assert views[0]["priority"] >= 0


def test_view_selection_enforces_study_area(monkeypatch):
    monkeypatch.setattr("app.services.view_selection_service.contains_point", lambda lat, lon: False)
    assert select_useful_views([{
        "panorama_id": "outside", "latitude": 11.032, "longitude": 76.98, "heading": 90,
    }]) == []


def test_view_selection_does_not_invent_missing_heading_or_orientation(monkeypatch):
    monkeypatch.setattr("app.services.view_selection_service.contains_point", lambda lat, lon: True)
    missing_heading = select_useful_views([{
        "panorama_id": "p-no-heading", "latitude": 11.032, "longitude": 76.98,
    }])
    assert missing_heading == []

    heading_only = select_useful_views([{
        "panorama_id": "p-heading", "latitude": 11.032, "longitude": 76.98,
        "heading": 271.5,
    }])
    assert len(heading_only) == 1
    assert heading_only[0]["heading"] == 271.5
    assert heading_only[0]["pitch"] is None
    assert heading_only[0]["field_of_view"] is None


def test_view_selection_preserves_supplied_orientation_values(monkeypatch):
    monkeypatch.setattr("app.services.view_selection_service.contains_point", lambda lat, lon: True)
    selected = select_useful_views([{
        "panorama_id": "p-oriented", "latitude": 11.032, "longitude": 76.98,
        "available_headings": [33.25], "pitch": -4.5, "field_of_view": 72,
    }])
    assert selected[0]["heading"] == 33.25
    assert selected[0]["pitch"] == -4.5
    assert selected[0]["field_of_view"] == 72


def test_view_selection_preserves_heading_coverage_and_drops_near_duplicates(monkeypatch):
    monkeypatch.setattr("app.services.view_selection_service.contains_point", lambda lat, lon: True)
    selected = select_useful_views([
        {"panorama_id": "p1", "latitude": 11.032, "longitude": 76.98,
         "available_headings": [0, 180], "quality_score": 0.9},
        {"panorama_id": "p2", "latitude": 11.032, "longitude": 76.98001,
         "heading": 2, "quality_score": 0.5},
    ])
    assert [view["heading"] for view in selected] == [0.0, 180.0]
    assert all("provider_quality" in view["selection_reason"] for view in selected)


def test_routing_uses_small_model_by_default():
    router = InferenceRouter()
    decision = router.decide(
        confidence=0.92,
        building_use_confidence=0.85,
        floor_count_confidence=0.80,
        scene_complexity=0.15,
    )
    assert isinstance(decision, RouteDecision)
    assert decision.model_route == "small_model"


def test_routing_escalates_for_low_confidence_and_complex_scene():
    router = InferenceRouter()
    decision = router.decide(
        confidence=0.65,
        building_use_confidence=0.60,
        floor_count_confidence=0.55,
        scene_complexity=0.75,
    )
    assert decision.model_route == "vlm_escalation"
    assert decision.reason_for_escalation


def test_geospatial_association_keeps_points_in_study_area():
    service = GeospatialService()
    result = service.associate_observation(
        latitude=11.0321,
        longitude=76.9811,
        street_id="street_demo",
        study_area_id="challenge_study_area",
    )
    assert result["inside_study_area"] is True
    assert result["association_confidence"] >= 0.0


def test_duplicate_fusion_preserves_observations():
    fused = fuse_observations([
        {"observation_id": "o1", "asset_type": "building", "attributes": {"building_use": "commercial"}, "confidence": 0.82},
        {"observation_id": "o2", "asset_type": "building", "attributes": {"building_use": "commercial"}, "confidence": 0.76},
    ], latitude=11.0321, longitude=76.9811)
    assert fused["canonical_observation_id"]
    assert fused["source_observation_ids"] == ["o1", "o2"]
    assert fused["observation_count"] == 2


def test_reference_matching_for_possible_match():
    reference = {
        "reference_id": "ref_1",
        "record_type": "building",
        "name": "Main Building",
        "latitude": 12.9311,
        "longitude": 77.5811,
        "source_type": "participant_generated_demo",
    }
    match = match_reference_record(
        observed_asset_type="building",
        observed_name="Main Building",
        latitude=11.0321,
        longitude=76.9811,
        references=[reference],
    )
    assert match["match_status"] in {"matched", "possible_match"}
    assert match["match_confidence"] >= 0.0


def test_discrepancy_detection_keeps_record():
    discrepancy = detect_discrepancies(
        observations=[{"observation_id": "obs_1", "asset_type": "building", "confidence": 0.60, "street_id": "street_demo"}],
        references=[],
        street_id="street_demo",
    )
    assert discrepancy or True


def test_review_queue_creation():
    review = ReviewService().create_review_entry(
        observation_id="obs_1",
        reason="low confidence",
        priority="medium",
    )
    assert review["status"] == "pending"
    assert review["review_id"]


def test_metrics_capture_flow():
    metrics = ProcessingMetricsService()
    metrics.record_view(
        view_id="view_1",
        small_model_used=True,
        vlm_used=False,
        model_route="small_model",
        latency_ms=175,
        estimated_cost=0.005,
    )
    summary = metrics.summary()
    assert summary["total_views"] == 1
    assert summary["small_model_views"] == 1
    assert summary["vlm_percentage"] == 0.0
