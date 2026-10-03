from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

from app.api import queries as local_queries
from app.api import review as review_api
from app.main import app
from app.services.challenge_queries import (
    commercial_over_two_floors, low_confidence_floor_reviews,
    routed_metrics_summary, streetlight_findings, unmatched_buildings_by_street,
)

HANDLER_PATH = Path(__file__).parents[1] / "aws" / "lambda" / "process_demo_object" / "handler.py"
SPEC = importlib.util.spec_from_file_location("task5_challenge_lambda_handler", HANDLER_PATH)
assert SPEC and SPEC.loader
handler_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler_module)
sys.path.insert(0, str(HANDLER_PATH.parent))
try:
    import cloud_api
finally:
    sys.path.remove(str(HANDLER_PATH.parent))

DATASET = "tn_study_area_demo_v1"
OBSERVATIONS = [
    {"observation_id": "commercial-3f", "dataset_id": DATASET, "asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 3}, "match_status": "unmatched", "street_id": "street-a", "confidence": 0.66, "simulation": True, "provenance": "synthetic"},
    {"observation_id": "commercial-possible", "dataset_id": DATASET, "asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 4}, "match_status": "possible_match", "street_id": "street-a", "confidence": 0.8},
    {"observation_id": "commercial-2f", "dataset_id": DATASET, "asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 2}, "match_status": "unmatched", "street_id": "street-b", "confidence": 0.8},
    {"observation_id": "floor-pending", "dataset_id": DATASET, "asset_type": "building", "attributes": {"visible_floor_count": 2}, "match_status": "matched", "street_id": "street-b", "confidence": 0.4, "simulation": True},
    {"observation_id": "floor-reviewed", "dataset_id": DATASET, "asset_type": "building", "attributes": {"visible_floor_count": 3}, "match_status": "matched", "street_id": "street-b", "confidence": 0.3},
]
REVIEWS = [{"observation_id": "floor-pending", "status": "needs_review"}, {"observation_id": "floor-reviewed", "status": "approved"}]
REFERENCES = [{"reference_id": "light-expected", "asset_type": "streetlight", "coverage_status": "simulated_complete", "source_type": "simulated_demo", "simulation": True, "provenance": "synthetic"}]
DISCREPANCIES = [{"discrepancy_id": "missing-light", "reference_id": "light-expected", "discrepancy_type": "expected_streetlight_not_observed", "confidence": 0.8, "simulation": True}]
METRICS = [{"view_id": "view-1", "model_route": "small_model", "latency_ms": 12, "simulation": True, "estimated_cost": None}]


class FakeDynamoDB:
    def __init__(self):
        self.records = {"observations": OBSERVATIONS, "review_queue": REVIEWS,
                        "reference_records": REFERENCES, "discrepancies": DISCREPANCIES,
                        "processing_metrics": METRICS}

    def get_records(self, dataset_id, *, collection=None, street_id=None):
        values = self.records.get(collection, [])
        return [item for item in values if item.get("dataset_id", DATASET) == dataset_id
                and (street_id is None or item.get("street_id") == street_id)]


def _cloud(path: str) -> dict:
    result = cloud_api.handler({"version": "2.0", "rawPath": path,
        "queryStringParameters": {"dataset_id": DATASET},
        "requestContext": {"http": {"method": "GET"}}}, None, dynamodb_service=FakeDynamoDB())
    assert result["statusCode"] == 200
    return json.loads(result["body"])


def test_challenge_query_algorithms_enforce_required_semantics():
    assert [row["observation_id"] for row in commercial_over_two_floors(OBSERVATIONS)] == ["commercial-3f"]
    assert [row["observation_id"] for row in low_confidence_floor_reviews(OBSERVATIONS, REVIEWS)] == ["floor-pending"]
    assert set(unmatched_buildings_by_street(OBSERVATIONS)) == {"street-a", "street-b"}
    streetlight = streetlight_findings(DISCREPANCIES, REFERENCES, OBSERVATIONS)
    assert streetlight[0]["interval_meters"] == 25
    assert streetlight[0]["coverage_complete"] is True
    assert streetlight[0]["simulation"] is True
    assert streetlight_findings(DISCREPANCIES, [{**REFERENCES[0], "coverage_status": "incomplete"}], OBSERVATIONS) == []
    assert [row["observation_id"] for row in commercial_over_two_floors([
        {"asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 3}},
        {"asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 3.5}, "match_status": "unmatched"},
        {"asset_type": "building", "attributes": {"building_use": "commercial", "visible_floor_count": 3}, "match_status": "matched"},
    ])] == []
    unknown_status = {"observation_id": "unknown-status", "asset_type": "building",
                      "attributes": {"building_use": "commercial", "visible_floor_count": 3}, "street_id": "street-c"}
    assert commercial_over_two_floors([unknown_status]) == []
    assert unmatched_buildings_by_street([unknown_status]) == {}
    assert low_confidence_floor_reviews([{**unknown_status, "confidence": None}], REVIEWS) == []


def test_routed_query_metrics_keep_unknown_latency_and_cost_unavailable():
    result = routed_metrics_summary([
        {"model_route": "small_model", "latency_ms": 12, "estimated_cost": None},
        {"model_route": "small_model", "latency_ms": None, "estimated_cost": None},
    ])
    assert result["processing_route_distribution"] == {"small_model": 2}
    assert result["latency_status"] == "partial"
    assert result["estimated_total_cost"] is None
    assert result["cost_status"] == "unavailable"


def test_review_corrections_store_original_and_corrected_without_mutating_observation(monkeypatch):
    review = {"review_id": "review-1", "observation_id": "obs-1", "study_area_id": "challenge_study_area"}
    observation = {"observation_id": "obs-1", "study_area_id": "challenge_study_area", "asset_type": "building",
                   "ocr_text": "OLD", "attributes": {"visible_floor_count": 2, "building_use": "unknown"}}

    class Collection:
        def __init__(self, items): self.items = items
        def find_one(self, query): return next((item for item in self.items if all(item.get(k) == v for k, v in query.items())), None)
        def update_one(self, query, update):
            item = self.find_one(query)
            if item is None: return type("Result", (), {"matched_count": 0})()
            item.update(update["$set"])
            return type("Result", (), {"matched_count": 1})()

    collections = {"review_queue": Collection([review]), "observations": Collection([observation])}
    monkeypatch.setattr(review_api, "get_collection", lambda name: collections[name])
    saved = review_api.record_review_decision("review-1", review_api.ReviewDecisionInput(
        status="approved", reviewer="auditor", reviewer_decision="corrected",
        corrected_attributes={"visible_floor_count": 3, "ocr_text": "NEW"}, reviewer_note="Checked signage"))
    assert saved["corrections"] == {
        "visible_floor_count": {"original": 2, "corrected": 3},
        "ocr_text": {"original": "OLD", "corrected": "NEW"},
    }
    assert saved["reviewer_note"] == "Checked signage"
    assert observation["attributes"]["visible_floor_count"] == 2


def test_local_and_cloud_challenge_query_contracts_are_semantically_equivalent(monkeypatch):
    data = {"observations": OBSERVATIONS, "review_queue": REVIEWS,
            "reference_records": REFERENCES, "discrepancies": DISCREPANCIES,
            "processing_metrics": METRICS}
    monkeypatch.setattr(local_queries, "_records", lambda name, dataset: data.get(name, []))
    client = TestClient(app)
    paths = {
        "buildings-over-2-floors-without-match": "/queries/buildings-over-2-floors-without-match",
        "streets-without-streetlights": "/queries/streets-without-streetlights",
        "low-confidence-floor-counts": "/queries/low-confidence-floor-counts",
        "unmatched-buildings-by-street": "/queries/unmatched-buildings-by-street",
        "routed-vs-all-vlm": "/queries/routed-vs-all-vlm",
    }
    for name, path in paths.items():
        local = client.get(path, params={"dataset_id": DATASET}).json()
        cloud = _cloud(path)
        for key in ("query_name", "dataset_id", "simulation", "result_count"):
            assert local[key] == cloud[key], (name, key, local.get(key), cloud.get(key))
        assert set(local) == set(cloud)
        assert local["limitations"] == cloud["limitations"]
        if name != "unmatched-buildings-by-street" and name != "routed-vs-all-vlm":
            assert [row.get("observation_id", row.get("discrepancy_id")) for row in local["records"]] == [row.get("observation_id", row.get("discrepancy_id")) for row in cloud["records"]]
        if name == "unmatched-buildings-by-street":
            assert {key: len(value) for key, value in local["by_street"].items()} == {key: len(value) for key, value in cloud["by_street"].items()}
        if name == "routed-vs-all-vlm":
            assert local["all_vlm_run_performed"] is cloud["all_vlm_run_performed"] is False
            assert local["quality_comparison_status"] == cloud["quality_comparison_status"] == "NOT_EVALUABLE"
            assert local["all_vlm_status"] == cloud["all_vlm_status"] == "NOT_RUN"
            assert local["measured_routed_metrics"] == cloud["measured_routed_metrics"]
        assert local["provenance"] == cloud["provenance"]
        assert local["simulation"] is cloud["simulation"] is True
