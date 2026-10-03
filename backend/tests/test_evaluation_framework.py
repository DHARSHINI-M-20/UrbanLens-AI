from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.evaluation.metrics import (
    all_vlm_comparison,
    bounding_box_iou,
    building_use_metrics,
    confusion_metrics,
    cost_metrics,
    detection_metrics,
    discrepancy_metrics,
    floor_count_metrics,
    haversine_meters,
    latency_metrics,
    ocr_metrics,
    positioning_metrics,
    reference_matching_metrics,
    review_metrics,
    routing_decision_metrics,
)
from app.evaluation.runner import (
    CLAIM_LABEL,
    EvaluationRunner,
    FIXTURE_DATASET_ID,
    load_fixture_dataset,
)
from app.evaluation.schema import GroundTruthDataset
from app.main import app


def test_precision_recall_f1_perfect_predictions():
    result = confusion_metrics(4, 0, 0, evaluated=4)
    assert result["precision"] == result["recall"] == result["f1"] == 1


def test_all_false_positives():
    result = confusion_metrics(0, 3, 0, evaluated=3)
    assert result["precision"] == 0
    assert result["recall"] is None
    assert result["f1"] == 0


def test_all_false_negatives():
    result = confusion_metrics(0, 0, 4, evaluated=4)
    assert result["precision"] is None
    assert result["recall"] == 0
    assert result["f1"] == 0


def test_mixed_true_false_positive_and_false_negative_counts():
    result = confusion_metrics(2, 1, 3, evaluated=6)
    assert (result["true_positives"], result["false_positives"], result["false_negatives"]) == (2, 1, 3)
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(0.4)


def test_unknown_detection_ground_truth_is_excluded_not_counted_as_negative():
    samples = [{"image_id": "unknown", "labeled_classes": [], "buildings": [], "assets": []}]
    predictions = {"unknown": {"observations": [{"asset_type": "building"}]}}
    result = detection_metrics(samples, predictions, asset_types=[])["buildings"]
    assert result["excluded_unknown_ground_truth"] == 1
    assert result["false_positives"] == 0
    assert result["status"] == "not_evaluable"


def test_explicit_negative_detection_labels_count_false_positives():
    samples = [{"image_id": "negative", "labeled_classes": ["building"], "buildings": [], "assets": []}]
    predictions = {"negative": {"observations": [{"asset_type": "building"}]}}
    result = detection_metrics(samples, predictions, asset_types=[])["buildings"]
    assert result["labeled_images"] == 1
    assert result["false_positives"] == 1


def test_asset_detection_reports_metrics_per_class():
    samples = [{"image_id": "a", "labeled_classes": ["streetlight", "electric_pole"],
                "buildings": [], "assets": [{"asset_id": "l1", "asset_type": "streetlight"}] }]
    predictions = {"a": {"observations": [{"asset_type": "streetlight", "observation_id": "l1"},
                                          {"asset_type": "electric_pole", "observation_id": "fp"}]}}
    result = detection_metrics(samples, predictions, asset_types=["streetlight", "electric_pole"])["assets"]
    assert result["by_class"]["streetlight"]["true_positives"] == 1
    assert result["by_class"]["electric_pole"]["false_positives"] == 1


def test_bbox_iou_is_used_when_geometry_is_available():
    assert bounding_box_iou({"x": 0, "y": 0, "width": 10, "height": 10},
                            {"x": 0, "y": 0, "width": 10, "height": 10}) == 1


def test_unknown_floor_count_is_excluded_and_never_coerced_to_zero():
    samples = [{"image_id": "a", "buildings": [{"building_id": "unknown", "floor_count": None}]}]
    result = floor_count_metrics(samples, {"a": {"observations": []}})
    assert result["evaluated"] == 0
    assert result["excluded_unknown_ground_truth"] == 1
    assert result["exact_accuracy"] is None


def test_floor_count_exact_accuracy_and_mae():
    samples = [{"image_id": "a", "buildings": [
        {"building_id": "b1", "floor_count": 3}, {"building_id": "b2", "floor_count": 2},
    ]}]
    predictions = {"a": {"observations": [
        {"asset_type": "building", "observation_id": "b1", "attributes": {"visible_floor_count": 3}},
        {"asset_type": "building", "observation_id": "b2", "attributes": {"visible_floor_count": 4}},
    ]}}
    result = floor_count_metrics(samples, predictions)
    assert result["evaluated"] == 2
    assert result["exact_accuracy"] == 0.5
    assert result["mean_absolute_error"] == 1


def test_missing_floor_prediction_is_wrong_not_zero_and_is_reported():
    samples = [{"image_id": "a", "buildings": [{"building_id": "b1", "floor_count": 3}]}]
    result = floor_count_metrics(samples, {"a": {"observations": []}})
    assert result["exact_accuracy"] == 0
    assert result["missing_prediction"] == 1
    assert result["mean_absolute_error"] is None


def test_ocr_exact_match_is_distinct_from_normalized_match():
    samples = [{"image_id": "a", "ocr": [{"region_id": "r1", "ground_truth_text": "PARK VIEW"}]}]
    result = ocr_metrics(samples, {"a": {"ocr": [{"ocr_id": "r1", "raw_text": "PARK  VIEW"}]}})
    assert result["exact_match_rate"] == 0
    assert result["normalized_match_rate"] == 1


def test_ocr_exact_string_match():
    samples = [{"image_id": "a", "ocr": [{"region_id": "r1", "ground_truth_text": "Market Road"}]}]
    result = ocr_metrics(samples, {"a": {"ocr": [{"ocr_id": "r1", "raw_text": "Market Road"}]}})
    assert result["exact_match_rate"] == result["normalized_match_rate"] == 1
    assert result["mean_character_error_rate"] == 0


def test_ocr_mismatch_and_unknown_label_handling():
    samples = [{"image_id": "a", "ocr": [
        {"region_id": "known", "ground_truth_text": "SHOP"},
        {"region_id": "unknown", "ground_truth_text": None},
    ]}]
    result = ocr_metrics(samples, {"a": {"ocr": [{"ocr_id": "known", "raw_text": "STORE"}]}})
    assert result["evaluated"] == 1
    assert result["excluded_unknown_ground_truth"] == 1
    assert result["exact_match_rate"] == 0
    assert result["mean_character_error_rate"] > 0


def test_building_use_accuracy_and_confusion_matrix():
    samples = [{"image_id": "a", "buildings": [
        {"building_id": "b1", "building_use": "commercial"},
        {"building_id": "b2", "building_use": None},
    ]}]
    predictions = {"a": {"observations": [
        {"asset_type": "building", "observation_id": "b1", "attributes": {"building_use": "commercial"}}
    ]}}
    result = building_use_metrics(samples, predictions)
    assert result["accuracy"] == 1
    assert result["evaluated"] == 1
    assert result["excluded_unknown_ground_truth"] == 1
    assert result["confusion_matrix"]["commercial"]["commercial"] == 1


def test_positioning_distance_error_uses_haversine_meters():
    error = haversine_meters({"latitude": 0, "longitude": 0}, {"latitude": 0, "longitude": 0.001})
    assert error == pytest.approx(111.195, rel=0.002)


def test_positioning_excludes_missing_ground_truth_coordinates():
    samples = [{"image_id": "a", "positioning": [
        {"entity_id": "known", "latitude": 0, "longitude": 0},
        {"entity_id": "unknown", "latitude": None, "longitude": None},
    ]}]
    result = positioning_metrics(samples, {"a": {"positioning": [{"entity_id": "known", "latitude": 0, "longitude": 0}]}})
    assert result["mean_error_meters"] == 0
    assert result["excluded_unknown_ground_truth"] == 1


def test_reference_matching_precision_recall_and_matched_counts():
    samples = [{"image_id": "a", "reference_matches": [
        {"entity_id": "1", "matched": True}, {"entity_id": "2", "matched": False},
    ]}]
    predictions = {"a": {"reference_matches": [
        {"entity_id": "1", "matched": True}, {"entity_id": "2", "matched": True},
    ]}}
    result = reference_matching_metrics(samples, predictions)
    assert result["matched_count"] == result["unmatched_count"] == 1
    assert result["true_positives"] == 1 and result["false_positives"] == 1


def test_discrepancy_metrics_are_by_type_and_exclude_unknown_truth():
    samples = [{"image_id": "a", "discrepancies": [
        {"entity_id": "b1", "discrepancy_type": "floor_count_mismatch", "expected_present": True},
        {"entity_id": "b2", "discrepancy_type": "floor_count_mismatch", "expected_present": None},
    ]}]
    predictions = {"a": {"discrepancies": [{"entity_id": "b1", "discrepancy_type": "floor_count_mismatch"}]}}
    result = discrepancy_metrics(samples, predictions)["floor_count_mismatch"]
    assert result["true_positives"] == 1
    assert result["excluded_unknown_ground_truth"] == 1


def test_review_routing_metrics_report_false_and_missed_reviews():
    samples = [{"image_id": "a", "review_routing": [
        {"entity_id": "1", "review_required": True}, {"entity_id": "2", "review_required": False},
    ]}]
    predictions = {"a": {"review_routing": [
        {"entity_id": "1", "review_required": False}, {"entity_id": "2", "review_required": True},
    ]}}
    result = review_metrics(samples, predictions)
    assert result["false_review_count"] == 1
    assert result["missed_review_count"] == 1


def test_expected_routing_decision_metrics():
    samples = [{"image_id": "a", "review_routing": [{"entity_id": "b", "expected_route": "vlm"}]}]
    predictions = {"a": {"routing_decisions": [{"entity_id": "b", "route": "local"}]}}
    result = routing_decision_metrics(samples, predictions)
    assert result["accuracy"] == 0


def test_latency_aggregation_only_reports_p95_with_enough_samples():
    small = latency_metrics([{"latency_ms": value} for value in (10, 20, 30)])
    assert small["mean_latency_ms"] == 20
    assert small["median_latency_ms"] == 20
    assert small["p95_latency_ms"] is None
    enough = latency_metrics([{"latency_ms": value} for value in range(1, 21)])
    assert enough["sample_count"] == 20
    assert enough["p95_latency_ms"] == 19


def test_cost_is_unavailable_without_explicit_pricing():
    result = cost_metrics([{"invocations": {"ocr": 3}}], None)
    assert result == {"status": "unavailable", "estimated_cost": None, "reason": "Pricing not configured."}


def test_cost_uses_explicit_prices_only():
    result = cost_metrics([{"invocations": {"ocr": 2, "local_detector": 1}}],
                          {"ocr": 0.01, "local_detector": 0.03})
    assert result["estimated_cost"] == 0.05
    assert result["pricing_source"] == "explicit evaluation input"


def test_invalid_cost_price_does_not_produce_a_metric():
    result = cost_metrics([{"invocations": {"ocr": 1}}], {"ocr": float("nan")})
    assert result["status"] == "unavailable"
    assert result["estimated_cost"] is None


def test_fixture_is_labeled_synthetic_and_not_real_street_view():
    dataset = load_fixture_dataset()
    result = EvaluationRunner().run()
    assert dataset.metadata.synthetic is True
    assert "SYNTHETIC EVALUATION GROUND TRUTH" in dataset.metadata.limitations[0]
    assert result["claim_label"] == CLAIM_LABEL
    assert "NOT REAL STREET VIEW PERFORMANCE" in result["claim_label"]
    assert result["prediction_source"] == "synthetic_mock_provider_outputs"
    assert result["external_model_calls_performed"] is False


def test_fixture_has_positive_negative_unknown_and_ambiguous_cases():
    dataset = load_fixture_dataset()
    assert any(not sample.buildings and not sample.assets for sample in dataset.samples)
    assert any(row.floor_count is None for sample in dataset.samples for row in sample.buildings)
    assert any(row.ground_truth_text == "" for sample in dataset.samples for row in sample.ocr)
    assert any(row.ground_truth_text is None for sample in dataset.samples for row in sample.ocr)
    assert {asset.asset_type for sample in dataset.samples for asset in sample.assets} >= {"streetlight", "electric_pole", "traffic_sign"}


def test_evaluation_metrics_and_id_are_deterministic():
    runner = EvaluationRunner()
    first, second = runner.run(), runner.run()
    assert first["evaluation_id"] == second["evaluation_id"]
    assert first["metrics"] == second["metrics"]


def test_evaluation_rejects_cross_dataset_scope_and_unknown_subset():
    with pytest.raises(KeyError, match="Unknown evaluation dataset"):
        EvaluationRunner().run(dataset_id="other-dataset")
    with pytest.raises(KeyError, match="Unknown image_id"):
        EvaluationRunner().run(subset=["not-in-fixture"])
    with pytest.raises(ValidationError, match="dataset_id"):
        GroundTruthDataset.model_validate({
            "metadata": {"dataset_id": "one", "version": "1", "synthetic": True,
                         "purpose": "test", "limitations": []},
            "samples": [{"dataset_id": "two", "image_id": "x"}],
        })


def test_all_vlm_is_explicitly_unmeasured_and_never_called():
    result = EvaluationRunner().run()
    comparison = result["metrics"]["all_vlm_comparison"]
    assert comparison["all_vlm_run"] is False
    assert comparison["quality_comparison"] == "unavailable"
    assert result["metrics"]["routing"]["actual_vlm_invocations"] == 0


def test_fusion_accuracy_is_not_claimed_without_adjudicated_outcomes():
    result = EvaluationRunner().run()
    assert result["metrics"]["fusion"]["status"] == "not_evaluable"
    assert result["metrics"]["fusion"]["accuracy_claimed"] is False


def test_fixture_latency_and_cost_are_not_claimed_as_measured():
    result = EvaluationRunner().run()
    assert result["metrics"]["latency"]["status"] == "not_evaluable"
    assert result["metrics"]["latency"]["mean_latency_ms"] is None
    assert result["metrics"]["cost"]["status"] == "unavailable"
    assert result["metrics"]["cost"]["estimated_cost"] is None


def test_evaluation_api_only_accepts_registered_dataset_and_is_read_only():
    client = TestClient(app)
    response = client.post("/evaluation/run", json={"dataset_id": FIXTURE_DATASET_ID})
    assert response.status_code == 200
    assert response.json()["synthetic"] is True
    assert response.json()["metrics"]["all_vlm_comparison"]["all_vlm_run"] is False
    assert client.post("/evaluation/run", json={"dataset_id": "arbitrary"}).status_code == 422
    assert client.post("/evaluation/run", json={"dataset_id": FIXTURE_DATASET_ID, "path": "C:/secret"}).status_code == 422
