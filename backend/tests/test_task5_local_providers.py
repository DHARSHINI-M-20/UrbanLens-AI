from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
import asyncio
import httpx

from app.main import app
from app.services.discrepancy_service import detect_discrepancies
from app.config import get_settings
from app.services.observation_fusion_service import fuse_nearby_observations
from app.services.observation_pipeline import ObservationPipelineService
from app.services.ocr_service import TesseractOCRProvider
from app.services.osm_reference_service import build_overpass_query, normalize_osm_response
from app.services.positioning_service import PositioningService
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.reference_matching_service import ReferenceDataAdapter, StaticReferenceProvider, match_observation
from app.services.review_service import ReviewService
from app.services.study_area_service import STUDY_AREA_ID, contains_point, get_study_area_geojson
from app.services.vision_service import LocalYOLOWorldVisionProvider


class FixtureYOLOWorldModel:
    """Stub model output for deterministic tests of the real YOLO adapter."""

    def __init__(self):
        self.predict_calls = []

    def set_classes(self, classes):
        self.classes = list(classes)

    def predict(self, **kwargs):
        self.predict_calls.append(kwargs)
        boxes = SimpleNamespace(
            xyxy=[[40, 40, 900, 460], [940, 30, 980, 450], [10, 100, 35, 440]],
            cls=[0, 1, 2],
            conf=[0.96, 0.88, 0.91],
        )
        return [SimpleNamespace(names={0: "building", 1: "streetlight", 2: "electric pole"}, boxes=boxes)]


def _study_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76.978, 11.030], [76.986, 11.030], [76.986, 11.038],
                                 [76.978, 11.038], [76.978, 11.030]]],
            },
            "properties": {},
        }],
    }


def test_local_yolo_world_provider_maps_supported_classes_and_measures(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", lambda lat, lon: True)
    model = FixtureYOLOWorldModel()
    detector = LocalYOLOWorldVisionProvider(model=model, confidence_threshold=0.2)
    observations = ObservationPipelineService(vision_provider=detector).process({
        "view_id": "fixture-view", "latitude": 11.032, "longitude": 76.98,
        "image": object(), "source_mode": "synthetic_fixture",
    })
    detections = observations["observations"]
    assert [item["asset_type"] for item in detections] == ["building", "streetlight", "electric_pole"]
    assert detections[0]["bounding_region"] == {"x": 40.0, "y": 40.0, "width": 860.0, "height": 420.0}
    assert detections[0]["model_name"] == detector.name
    assert detections[0]["source_view_id"] == "fixture-view"
    assert detections[0]["processing_time_ms"] is not None
    assert model.predict_calls[0]["device"] == "cpu"
    assert detector.invocation_count == 1


def test_osm_ingestion_keeps_provenance_filters_boundary_and_marks_coverage():
    study_area = _study_geojson()
    response = {"elements": [
        {"type": "way", "id": 101, "tags": {"building": "yes", "name": "Library", "building:levels": "2"},
         "geometry": [
             {"lat": 11.032, "lon": 76.980}, {"lat": 11.032, "lon": 76.981},
             {"lat": 11.033, "lon": 76.981}, {"lat": 11.033, "lon": 76.980},
             {"lat": 11.032, "lon": 76.980},
         ]},
        {"type": "node", "id": 202, "lat": 11.034, "lon": 76.982,
         "tags": {"highway": "street_lamp"}},
        {"type": "node", "id": 303, "lat": 12.0, "lon": 77.0,
         "tags": {"power": "pole"}},
    ]}
    records, coverage = normalize_osm_response(
        response, study_geojson=study_area,
        ingested_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )
    assert [record["reference_id"] for record in records] == ["osm:way/101", "osm:node/202"]
    assert records[0]["source_type"] == "public_osm"
    assert records[0]["geometry"]["type"] == "Polygon"
    assert records[0]["source_geometry"]["type"] == "Polygon"
    assert records[0]["visible_floor_count"] == 2
    assert records[1]["record_type"] == "streetlight"
    assert coverage["coverage_status"] == "incomplete_public_coverage"
    assert coverage["absence_is_evidence"] is False
    assert coverage["records_rejected_outside_or_invalid"] == 1


def test_osm_query_is_bounded_and_covers_supported_asset_classes():
    query = build_overpass_query(_study_geojson())
    assert "way[\"building\"]" in query
    assert "highway\"=\"street_lamp" in query
    assert "power\"=\"pole" in query
    assert "11.03" in query and "76.978" in query


def test_osm_unmatched_is_coverage_limited_not_proof_of_absence():
    osm_reference = {
        "reference_id": "osm:way/1", "record_type": "building", "asset_type": "building",
        "latitude": 11.032, "longitude": 76.98, "reference_source": "OpenStreetMap",
        "source_type": "public_osm", "coverage_status": "incomplete_public_coverage",
    }
    adapter = ReferenceDataAdapter([StaticReferenceProvider("OpenStreetMap", [osm_reference])])
    unmatched = match_observation({
        "observation_id": "pole-1", "asset_type": "electric_pole", "latitude": 11.032,
        "longitude": 76.98, "attributes": {},
    }, adapter)
    discrepancies = detect_discrepancies(observations=[{
        "observation_id": "pole-1", "asset_type": "electric_pole", "latitude": 11.032,
        "longitude": 76.98, "source_view_id": "view-1", "confidence": 0.9,
    }], references=[osm_reference])
    assert unmatched["status"] == "UNMATCHED"
    assert unmatched["reference_coverage"] == ["incomplete_public_coverage"]
    assert unmatched["absence_is_evidence"] is False
    assert any(item["discrepancy_type"] == "unmatched_reference_coverage_limited" for item in discrepancies)
    assert not any(item["discrepancy_type"] == "missing_reference_record" for item in discrepancies)


def test_reference_matching_exposes_matched_possible_unmatched_and_missing_coverage():
    observed = {
        "observation_id": "b-1", "asset_type": "building", "latitude": 11.032,
        "longitude": 76.98, "attributes": {"building_name": "Market Hall"},
    }
    matched = match_observation(observed, ReferenceDataAdapter([StaticReferenceProvider("OSM", [{
        "reference_id": "osm:way/match", "record_type": "building", "name": "Market Hall",
        "latitude": 11.032, "longitude": 76.98, "source_type": "public_osm",
        "coverage_status": "incomplete_public_coverage",
    }])]))
    possible = match_observation({**observed, "attributes": {}}, ReferenceDataAdapter([
        StaticReferenceProvider("OSM", [{
            "reference_id": "osm:way/possible", "record_type": "building",
            "latitude": 11.03212, "longitude": 76.98, "source_type": "public_osm",
            "coverage_status": "incomplete_public_coverage",
        }])
    ]))
    unmatched = match_observation({**observed, "latitude": 11.04}, ReferenceDataAdapter([
        StaticReferenceProvider("OSM", [{
            "reference_id": "osm:way/far", "record_type": "building", "name": "Elsewhere",
            "latitude": 11.032, "longitude": 76.98, "source_type": "public_osm",
            "coverage_status": "incomplete_public_coverage",
        }])
    ]))
    unavailable = match_observation(observed, ReferenceDataAdapter())
    assert matched["status"] == "MATCHED"
    assert possible["status"] == "POSSIBLE_MATCH"
    assert unmatched["status"] == "UNMATCHED"
    assert unavailable["reference_coverage"] == ["unavailable"]
    assert unavailable["absence_is_evidence"] is False


def test_model_prices_are_optional_and_read_from_configuration(monkeypatch):
    monkeypatch.setenv("LOCAL_DETECTOR_COST_PER_INVOCATION", "0.0125")
    monkeypatch.setenv("OCR_COST_PER_INVOCATION", "")
    monkeypatch.setenv("NOVA_LITE_COST_PER_INVOCATION", "0.003")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.local_detector_cost_per_invocation == 0.0125
    assert settings.ocr_cost_per_invocation is None
    assert settings.nova_lite_cost_per_invocation == 0.003
    get_settings.cache_clear()


def test_observation_api_rejects_invalid_base64_before_database_access():
    async def make_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/observations/process", json={
                "view_id": "sample-view", "image_base64": "%%%not-base64%%%",
            })

    response = asyncio.run(make_request())
    assert response.status_code == 422
    assert "valid base64" in response.json()["detail"]


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract executable is not installed locally.")
def test_tesseract_provider_extracts_supplied_local_image():
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    ImageFont = pytest.importorskip("PIL.ImageFont")
    image = Image.new("RGB", (1000, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    draw.rectangle((20, 20, 980, 480), outline="black", width=8)
    draw.text((90, 180), "CAFE NORTH", fill="black", font=font)

    provider = TesseractOCRProvider()
    result = ObservationPipelineService(
        vision_provider=LocalYOLOWorldVisionProvider(model=FixtureYOLOWorldModel()),
        ocr_provider=provider,
    ).process({
        "view_id": "tesseract-view", "latitude": 11.032, "longitude": 76.98,
        "image": image, "source_mode": "synthetic_fixture",
    })
    texts = " ".join(item["normalized_text"] for item in result["ocr_results"]).upper()
    assert "CAFE" in texts and "NORTH" in texts
    assert result["ocr_results"][0]["raw_text"]
    assert result["ocr_results"][0]["source_view_id"] == "tesseract-view"
    assert result["ocr_results"][0]["processing_time_ms"] >= 0
    assert provider.invocation_count == 1


def test_end_to_end_offline_local_vision_ocr_positioning_fusion_matching_review_metrics(monkeypatch):
    monkeypatch.setattr("app.services.vision_service.contains_point", contains_point)
    monkeypatch.setattr("app.services.positioning_service.contains_point", contains_point, raising=False)
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    ImageFont = pytest.importorskip("PIL.ImageFont")
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract executable is not installed locally.")

    sample = {"latitude": 11.032, "longitude": 76.98}
    assert contains_point(sample["latitude"], sample["longitude"])
    image = Image.new("RGB", (1000, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 980, 480), outline="black", width=8)
    draw.text((90, 180), "CAFE NORTH", fill="black", font=ImageFont.load_default(size=64))

    footprint = {
        "reference_id": "osm:way/101", "record_type": "building", "asset_type": "building",
        "name": "CAFE NORTH", "latitude": 11.0325, "longitude": 76.9805,
        "geometry": {"type": "Polygon", "coordinates":[[
            [76.979, 11.033], [76.981, 11.033], [76.981, 11.034],
            [76.979, 11.034], [76.979, 11.033],
        ]]},
        "reference_source": "OpenStreetMap", "source_type": "public_osm",
        "coverage_status": "incomplete_public_coverage",
    }
    adapter = ReferenceDataAdapter([StaticReferenceProvider("OpenStreetMap", [footprint])])
    runs = []
    for view_id, offset in (("sample-view-a", 0.0), ("sample-view-b", 0.00002)):
        model = FixtureYOLOWorldModel()
        pipeline = ObservationPipelineService(
            vision_provider=LocalYOLOWorldVisionProvider(model=model),
            ocr_provider=TesseractOCRProvider(),
        )
        run = pipeline.process({
            "view_id": view_id,
            "latitude": sample["latitude"] + offset,
            "longitude": sample["longitude"],
            "heading": 0,
            "image": image,
            "source_mode": "synthetic_fixture",
        })
        assert run["observations"]
        assert run["ocr_results"]
        building = next(item for item in run["observations"] if item["asset_type"] == "building")
        assert building["attributes"].get("visible_sign_text")
        building["positioning"] = PositioningService().position_building(
            [{**building, "camera_latitude": building["latitude"],
              "camera_longitude": building["longitude"], "heading": 0}],
            footprints=[footprint],
        )
        run["matches"] = [match_observation(item, adapter) for item in run["observations"]]
        runs.append(run)

    observations = [item for run in runs for item in run["observations"]]
    assert all(run["routing"]["model_route"] == "small_model" for run in runs)
    assert all(run["provider_execution"]["detector_invocations"] == 1 for run in runs)
    assert all(run["provider_execution"]["ocr_invocations"] == 1 for run in runs)
    building_observation = next(item for item in observations if item["asset_type"] == "building")
    assert building_observation["positioning"]["building_reference_id"] == "osm:way/101"
    assert building_observation["positioning"]["positioning_method"] == "line_of_sight_footprint_intersection"
    building_match = next(match for run in runs for match in run["matches"]
                          if match["observation_id"] == building_observation["observation_id"])
    assert building_match["status"] in {"MATCHED", "POSSIBLE_MATCH"}
    assert building_match["reference_source"] == "OpenStreetMap"

    fused = fuse_nearby_observations(observations)
    assert any(item["supporting_view_count"] == 2 for item in fused)
    discrepancies = detect_discrepancies(observations=observations, references=[footprint])
    assert any(item["discrepancy_type"] == "unmatched_reference_coverage_limited" for item in discrepancies)

    review = ReviewService()
    pole_observation = next(item for item in observations if item["asset_type"] == "electric_pole")
    queue_entry = review.create_review_entry(
        observation_id=pole_observation["observation_id"], reason="unmatched public reference", status="needs_review",
    )
    assert queue_entry["status"] == "needs_review"
    assert review.record_decision(queue_entry["review_id"], status="approved", reviewer="local-e2e")["reviewed_at"]

    metrics = ProcessingMetricsService()
    for run in runs:
        execution = run["provider_execution"]
        metrics.record_view(
            view_id=run["view_id"], small_model_used=True, vlm_used=False,
            model_route=run["routing"]["model_route"], latency_ms=run["processing_latency_ms"],
            estimated_cost=None, detector_invocations=execution["detector_invocations"],
            ocr_invocations=execution["ocr_invocations"], detector_latency_ms=execution["detector_latency_ms"],
            ocr_latency_ms=execution["ocr_latency_ms"], buildings_detected=1,
            streetlights_detected=1, electric_poles_detected=1, ocr_observations=len(run["ocr_results"]),
            matched_observations=sum(match["status"] == "MATCHED" for match in run["matches"]),
            unmatched_observations=sum(match["status"] == "UNMATCHED" for match in run["matches"]),
            cost_status="unavailable", cost_unavailable_reason="No verified local model price configured.",
        )
    summary = metrics.summary()
    assert summary["total_views"] == 2
    assert summary["actual_invocation_count"] == 4
    assert summary["buildings_detected"] == 2
    assert summary["ocr_observations"] >= 2
    assert summary["estimated_total_cost"] is None
    assert summary["cost_status"] == "unavailable"
