"""Dataset-scoped dashboard aggregates derived from persisted backend records."""

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


@router.get("/summary")
def dashboard_summary(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
	query: dict[str, Any] = {"study_area_id": STUDY_AREA_ID}
	if dataset_id:
		query["dataset_id"] = dataset_id
	try:
		streets = list(get_collection("streets").find(query).limit(5000))
		observations = list(get_collection("observations").find(query).limit(5000))
		discrepancies = list(get_collection("discrepancies").find(query).limit(5000))
		reviews = list(get_collection("review_queue").find(query).limit(5000))
		metrics_documents = list(get_collection("processing_metrics").find(query).limit(5000))
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc

	counts = Counter(str(item.get("asset_type") or "other") for item in observations)
	match_counts = Counter(str(item.get("match_status") or "unmatched") for item in observations)
	use_counts = Counter(str((item.get("attributes") or {}).get("building_use") or "unknown")
						 for item in observations if item.get("asset_type") == "building")
	floor_counts = Counter(str((item.get("attributes") or {}).get("visible_floor_count")
							if (item.get("attributes") or {}).get("visible_floor_count") is not None else "unknown")
						   for item in observations if item.get("asset_type") == "building")
	low_confidence = sum(item.get("confidence") is not None and float(item["confidence"]) < 0.7 for item in observations)
	confidence_unavailable = sum(item.get("confidence") is None for item in observations)
	discrepancy_by_street = Counter(str(item.get("street_id") or "Unassigned") for item in discrepancies)

	metrics = ProcessingMetricsService()
	metrics.records = [{key: value for key, value in item.items() if key != "_id"}
					   for item in metrics_documents]
	metric_summary = metrics.summary()
	return {
		"dataset_id": dataset_id,
		"simulation": bool(dataset_id and (dataset_id == "tn_study_area_demo_v1" or any(item.get("simulation") for item in observations))),
		"label": "SIMULATED TAMIL NADU URBAN DATA — NOT REAL STREET VIEW DATA" if dataset_id else None,
		"streets_covered": len(streets),
		"buildings_analysed": counts["building"],
		"unmatched_properties": sum(match_counts[key] for key in ("unmatched", "possible_match", "mismatch")),
		"streetlights_detected": counts["streetlight"],
		"electric_poles_detected": counts["electric_pole"],
		"low_confidence_observations": low_confidence,
		"discrepancy_count": len(discrepancies),
		"reviews_pending": sum(item.get("status") in {"pending", "needs_review"} for item in reviews),
		"building_use_distribution": dict(use_counts),
		"floor_distribution": dict(floor_counts),
		"asset_type_distribution": dict(counts),
		"match_status_distribution": dict(match_counts),
		"discrepancies_by_street": dict(discrepancy_by_street),
		"low_confidence_count": low_confidence,
		"confidence_unavailable_count": confidence_unavailable,
		"processing_route_distribution": dict(Counter(str(item.get("model_route") or "unknown")
													   for item in metrics_documents)),
		"processing_metrics": metric_summary,
		"processing_cost_message": ("Cost unavailable - pricing not configured"
									if metric_summary["cost_status"] != "available" else None),
	}
