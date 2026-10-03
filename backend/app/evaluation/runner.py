"""Dataset-scoped evaluation runner and deterministic offline pipeline adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from app.evaluation import metrics
from app.evaluation.schema import GroundTruthDataset
from app.services.discrepancy_service import detect_discrepancies
from app.services.inference_router import InferenceRouter
from app.services.observation_fusion_service import fuse_nearby_observations
from app.services.observation_pipeline import ObservationPipelineService
from app.services.ocr_service import MockOCRProvider
from app.services.positioning_service import PositioningService
from app.services.reference_matching_service import (
    ReferenceDataAdapter,
    StaticReferenceProvider,
    match_observation,
)
from app.services.review_service import ReviewService
from app.services.vision_service import MockVisionProvider


FIXTURE_DATASET_ID = "urbanlens_synthetic_eval_v1"
FIXTURE_VERSION = "1.0.0"
CLAIM_LABEL = "SYNTHETIC EVALUATION RESULT — NOT REAL STREET VIEW PERFORMANCE"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
METRIC_CATEGORIES = {
    "detection", "assets", "ocr", "floor_count", "building_use", "positioning",
    "fusion", "matching", "discrepancy", "review", "routing", "latency", "cost",
}
_VOLATILE_KEYS = {"latency_ms", "processing_latency_ms", "processing_time_ms", "started_at", "completed_at",
                  "detector_latency_ms", "ocr_latency_ms", "positioning_latency_ms", "nova_lite_latency_ms"}


def _stable_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stable_json_value(item) for key, item in value.items() if key not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_stable_json_value(item) for item in value]
    return value


class PredictionProvider(Protocol):
    """Produce predictions from the existing pipeline for supplied view records."""

    version: str
    prediction_source: str

    def predict(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Run configured pipeline components for one ground-truth view."""


class _NoCallInferenceRouter(InferenceRouter):
    """Preserve routing decisions while suppressing every external VLM call."""

    def run_escalation(self, *, small_model_result: dict[str, object],
                       small_model_latency_ms: float = 0.0, prompt: str,
                       confidence: float, image_bytes: bytes | None = None,
                       building_use_confidence: float | None = None,
                       floor_count_confidence: float | None = None,
                       scene_complexity: float | None = None,
                       service: Any = None, region: str | None = None) -> dict[str, Any]:
        decision = self.decide(
            confidence=confidence,
            building_use_confidence=building_use_confidence,
            floor_count_confidence=floor_count_confidence,
            scene_complexity=scene_complexity,
        )
        return {
            "model_route": decision.model_route,
            "model_name": decision.model_name,
            "latency_ms": small_model_latency_ms,
            "estimated_cost": None,
            "escalation_reason": decision.reason_for_escalation,
            "confidence_before_escalation": confidence,
            "final_confidence": confidence,
            "result": small_model_result,
            "success": True,
            "vlm_success": False,
            "nova_lite_invoked": False,
            "simulated_escalation_invoked": False,
            "escalation_provider": None,
            "evaluation_vlm_suppressed": True,
        }


class FixturePipelineProvider:
    """Run UrbanLens pipeline services against deterministic mock-provider inputs."""

    version = FIXTURE_VERSION
    prediction_source = "synthetic_mock_provider_outputs"

    def __init__(self, prediction_data: dict[str, Any] | None = None) -> None:
        if prediction_data is None:
            prediction_data = json.loads((FIXTURE_ROOT / "predictions_v1.json").read_text(encoding="utf-8"))
        if prediction_data.get("dataset_id") != FIXTURE_DATASET_ID or prediction_data.get("version") != FIXTURE_VERSION:
            raise ValueError("Fixture predictions must match the registered dataset ID and version.")
        self._samples = {str(row["image_id"]): row for row in prediction_data.get("samples", [])}

    def predict(self, sample: dict[str, Any]) -> dict[str, Any]:
        fixture = self._samples.get(str(sample["image_id"]))
        if fixture is None:
            raise ValueError(f"No registered fixture predictions for image_id {sample['image_id']}.")

        view_context = {
            "view_id": str(sample["image_id"]),
            "panorama_reference": sample.get("panorama_id"),
            "dataset_id": sample["dataset_id"],
            "latitude": fixture["latitude"],
            "longitude": fixture["longitude"],
            "source_mode": "synthetic_evaluation_fixture",
            "simulation": True,
            "provenance": "SYNTHETIC EVALUATION GROUND TRUTH — NOT REAL STREET VIEW DATA",
        }
        vision = MockVisionProvider(fixture.get("detections", []))
        ocr = MockOCRProvider(fixture.get("ocr", []))
        pipeline = ObservationPipelineService(
            vision_provider=vision,
            ocr_provider=ocr,
            inference_router=_NoCallInferenceRouter(),
        )
        result = pipeline.process(view_context)
        observations = result["observations"]

        references = fixture.get("references", [])
        reference_adapter = ReferenceDataAdapter(
            [StaticReferenceProvider("synthetic_fixture", references)] if references else []
        )
        matches = [match_observation(item, reference_adapter) for item in observations]
        for match in matches:
            match["entity_id"] = match.get("observation_id")
            match["matched"] = match.get("match_status") in {"matched", "possible_match", "mismatch"}

        discrepancies = detect_discrepancies(observations=observations, references=references)
        for discrepancy in discrepancies:
            discrepancy["entity_id"] = discrepancy.get("observation_id") or discrepancy.get("reference_id")

        positioner = PositioningService()
        positions = []
        for item in observations:
            if item.get("asset_type") != "building":
                continue
            position = positioner.position_building([item])
            positions.append({"entity_id": item["observation_id"], **position})

        review_service = ReviewService()
        review_rows = []
        for item in observations:
            attributes = item.get("attributes") or {}
            review_required = (
                float(item.get("confidence") or 0) < 0.5
                or (item.get("asset_type") == "building"
                    and (attributes.get("visible_floor_count") is None
                         or attributes.get("building_use") in {None, "unknown"}))
            )
            if review_required:
                review_service.create_review_entry(
                    observation_id=str(item["observation_id"]),
                    reason="fixture confidence or attribute review rule",
                    status="needs_review",
                )
            review_rows.append({"entity_id": item["observation_id"], "review_required": review_required})

        route = result["routing"]["model_route"]
        route_record = {
            "route": "vlm" if route == "vlm_escalation" else "local" if route == "small_model" else "unavailable",
            "actual_vlm_invoked": bool(result["routing"].get("nova_lite_invoked")),
        }
        routing_decisions = [
            {"entity_id": item.get("entity_id"), "route": route_record["route"]}
            for item in sample.get("review_routing", [])
            if item.get("expected_route") is not None
        ]

        usage = result.get("provider_execution", {})
        return {
            "image_id": sample["image_id"],
            "observations": observations,
            "ocr": result["ocr_results"],
            "positioning": positions,
            "reference_matches": matches,
            "discrepancies": discrepancies,
            "review_routing": review_rows,
            "routing": route_record,
            "routing_decisions": routing_decisions,
            "actual_vlm_invocations": int(result["provider_execution"]["nova_lite_invocations"]),
            "fixture_provider_invocations": {
                "vision": len(fixture.get("detections", [])) > 0,
                "ocr": len(fixture.get("ocr", [])) > 0,
            },
            "usage": {"invocations": {
                "local_detector": int(usage.get("detector_invocations", 0))
                                  + int(usage.get("simulated_detector_invocations", 0)),
                "ocr": int(usage.get("ocr_invocations", 0))
                       + int(usage.get("simulated_ocr_invocations", 0)),
                "vlm": int(usage.get("nova_lite_invocations", 0)),
            }},
            # Wall time from mock providers is evaluation overhead, not model latency.
            "latency_ms": None,
        }


def load_fixture_dataset(dataset_id: str = FIXTURE_DATASET_ID,
                         version: str | None = None) -> GroundTruthDataset:
    """Load only the registered immutable fixture; never accepts filesystem paths."""
    if dataset_id != FIXTURE_DATASET_ID:
        raise KeyError(f"Unknown evaluation dataset: {dataset_id}")
    if version not in (None, FIXTURE_VERSION):
        raise KeyError(f"Unknown version {version} for evaluation dataset {dataset_id}")
    raw = json.loads((FIXTURE_ROOT / "ground_truth_v1.json").read_text(encoding="utf-8"))
    return GroundTruthDataset.model_validate(raw)


class EvaluationRunner:
    """Run registered ground truth through a prediction provider and score its outputs."""

    def __init__(self, prediction_provider: PredictionProvider | None = None) -> None:
        self.prediction_provider = prediction_provider or FixturePipelineProvider()

    def run(self, *, dataset_id: str = FIXTURE_DATASET_ID,
            dataset_version: str | None = None,
            subset: list[str] | None = None,
            categories: list[str] | None = None,
            pricing: dict[str, float] | None = None) -> dict[str, Any]:
        dataset = load_fixture_dataset(dataset_id, dataset_version)
        return self.run_dataset(dataset, subset=subset, categories=categories, pricing=pricing)

    def run_dataset(self, dataset: GroundTruthDataset, *,
                    subset: list[str] | None = None,
                    categories: list[str] | None = None,
                    pricing: dict[str, float] | None = None) -> dict[str, Any]:
        """Evaluate a caller-supplied, already validated dataset with this provider.

        Filesystem loading and provider selection are deliberately outside the
        HTTP API. Trusted local integrations may load authorized labels and inject
        their existing pipeline adapter here.
        """
        dataset_id = dataset.metadata.dataset_id
        samples = [row.model_dump(mode="json") for row in dataset.samples]
        if subset is not None:
            requested = set(subset)
            known = {row["image_id"] for row in samples}
            unknown = requested - known
            if unknown:
                raise KeyError(f"Unknown image_id values for dataset {dataset_id}: {sorted(unknown)}")
            samples = [row for row in samples if row["image_id"] in requested]
        selected_categories = set(categories or METRIC_CATEGORIES)
        invalid_categories = selected_categories - METRIC_CATEGORIES
        if invalid_categories:
            raise ValueError(f"Unsupported evaluation categories: {sorted(invalid_categories)}")

        started_at = datetime.now(timezone.utc).isoformat()
        predictions = [self.prediction_provider.predict(row) for row in samples]
        expected_image_ids = {str(row["image_id"]) for row in samples}
        prediction_image_ids = [str(row.get("image_id", "")) for row in predictions]
        if set(prediction_image_ids) != expected_image_ids or len(prediction_image_ids) != len(expected_image_ids):
            raise ValueError("Prediction provider must return exactly one prediction record per selected image_id.")
        for prediction in predictions:
            if prediction.get("dataset_id") not in (None, dataset_id):
                raise ValueError("Prediction provider returned a record from a different dataset_id.")
        by_image = {str(row["image_id"]): row for row in predictions}
        labeled_samples = [row for row in samples if row["dataset_id"] == dataset_id]
        if len(labeled_samples) != len(samples):
            raise ValueError("Evaluation runner rejected cross-dataset samples.")

        computed: dict[str, Any] = {}
        if "detection" in selected_categories or "assets" in selected_categories:
            detection = metrics.detection_metrics(
                samples, by_image,
                asset_types=[name for name in dataset.metadata.exhaustive_classes if name != "building"],
            )
            if "detection" in selected_categories:
                computed["detection"] = detection["buildings"]
            if "assets" in selected_categories:
                computed["assets"] = detection["assets"]
        if "ocr" in selected_categories:
            computed["ocr"] = metrics.ocr_metrics(samples, by_image)
        if "floor_count" in selected_categories:
            computed["floor_count"] = metrics.floor_count_metrics(samples, by_image)
        if "building_use" in selected_categories:
            computed["building_use"] = metrics.building_use_metrics(samples, by_image)
        if "positioning" in selected_categories:
            computed["positioning"] = metrics.positioning_metrics(samples, by_image)
        if "fusion" in selected_categories:
            all_observations = [
                observation
                for prediction in predictions
                for observation in prediction.get("observations", [])
            ]
            fused_candidates = fuse_nearby_observations(all_observations) if all_observations else []
            computed["fusion"] = {
                "status": "not_evaluable",
                "reason": "The fixture has repeated-view labels but no independently adjudicated canonical fused-entity outcomes.",
                "fused_candidates_exercised": len(fused_candidates),
                "accuracy_claimed": False,
            }
        if "matching" in selected_categories:
            computed["matching"] = metrics.reference_matching_metrics(samples, by_image)
        if "discrepancy" in selected_categories:
            computed["discrepancy"] = metrics.discrepancy_metrics(samples, by_image)
        if "review" in selected_categories:
            computed["review"] = metrics.review_metrics(samples, by_image)
        if "routing" in selected_categories:
            computed["routing"] = metrics.routing_metrics([row.get("routing", {}) for row in predictions])
            computed["routing"]["decision_quality"] = metrics.routing_decision_metrics(samples, by_image)
            computed["routing"]["actual_vlm_invocations"] = sum(
                int(row.get("actual_vlm_invocations", 0)) for row in predictions
            )
        if "latency" in selected_categories:
            computed["latency"] = metrics.latency_metrics(predictions)
            if self.prediction_provider.prediction_source == "synthetic_mock_provider_outputs":
                computed["latency"].update({
                    "status": "not_evaluable",
                    "mean_latency_ms": None,
                    "median_latency_ms": None,
                    "p95_latency_ms": None,
                    "reason": "Fixture-provider wall time is evaluation overhead, not UrbanLens model latency.",
                })
        if "cost" in selected_categories:
            computed["cost"] = metrics.cost_metrics(
                [row.get("usage", {}) for row in predictions], pricing
            )
        computed["all_vlm_comparison"] = metrics.all_vlm_comparison(all_vlm_run=False)

        stable_predictions = _stable_json_value(predictions)
        digest_input = json.dumps({
            "dataset_id": dataset_id,
            "version": dataset.metadata.version,
            "ground_truth": dataset.model_dump(mode="json"),
            "subset": sorted(row["image_id"] for row in samples),
            "categories": sorted(selected_categories),
            "prediction_source": self.prediction_provider.prediction_source,
            "prediction_version": self.prediction_provider.version,
            "predictions": stable_predictions,
        }, sort_keys=True, separators=(",", ":"))
        evaluation_id = "eval_" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:20]
        return {
            "evaluation_id": evaluation_id,
            "dataset_id": dataset_id,
            "dataset_version": dataset.metadata.version,
            "synthetic": dataset.metadata.synthetic,
            "claim_label": CLAIM_LABEL if dataset.metadata.synthetic else None,
            "prediction_source": self.prediction_provider.prediction_source,
            "external_model_calls_performed": False if self.prediction_provider.prediction_source == "synthetic_mock_provider_outputs" else None,
            "sample_count": len(samples),
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": computed,
            "limitations": list(dataset.metadata.limitations),
        }
