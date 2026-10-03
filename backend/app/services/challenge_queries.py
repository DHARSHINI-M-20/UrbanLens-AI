"""Shared semantics and response envelope for Task 5 challenge queries."""

from __future__ import annotations

from datetime import datetime, timezone
from collections import Counter
import math
from typing import Any

FLOOR_CONFIDENCE_THRESHOLD = 0.7
STREETLIGHT_INTERVAL_METERS = 25


def envelope(query_name: str, dataset_id: str, records: list[dict[str, Any]], *,
             simulation: bool, limitations: list[str] | None = None,
             **extra: Any) -> dict[str, Any]:
    return {
        "query_name": query_name,
        "dataset_id": dataset_id,
        "simulation": simulation,
        "result_count": len(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": None,
        "records": records,
        "provenance": "SIMULATED DEMONSTRATION DATA — NOT REAL STREET VIEW DATA" if simulation else "Backend records; source-specific provenance is included per record.",
        "limitations": limitations or [],
        **extra,
    }


def routed_metrics_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize supplied routed records without inventing an all-VLM baseline."""
    routes = Counter(str(item.get("model_route") or item.get("processing_route") or "unknown") for item in records)
    latencies = [_finite_nonnegative(item.get("latency_ms")) for item in records]
    known_latencies = [value for value in latencies if value is not None]
    costs = [_finite_nonnegative(item.get("estimated_cost")) for item in records]
    known_costs = [value for value in costs if value is not None]
    return {
        "record_count": len(records),
        "processing_route_distribution": dict(sorted(routes.items())),
        "average_latency_ms": round(sum(known_latencies) / len(known_latencies), 2) if known_latencies else None,
        "total_latency_ms": round(sum(known_latencies), 2) if known_latencies else None,
        "latency_status": "available" if records and len(known_latencies) == len(records) else "partial" if known_latencies else "unavailable",
        "estimated_total_cost": round(sum(known_costs), 6) if records and len(known_costs) == len(records) else None,
        "cost_status": "available" if records and len(known_costs) == len(records) else "partial" if known_costs else "unavailable",
    }


def commercial_over_two_floors(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = [item for item in observations
            if item.get("asset_type", item.get("entity_type")) == "building"
            and (item.get("attributes") or {}).get("building_use", item.get("probable_use")) == "commercial"
            and _floor_count(item) is not None and _floor_count(item) > 2
            and _match_status(item) == "unmatched"]
    return sorted(records, key=lambda item: str(item.get("observation_id") or ""))


def low_confidence_floor_reviews(observations: list[dict[str, Any]], reviews: list[dict[str, Any]],
                                 threshold: float = FLOOR_CONFIDENCE_THRESHOLD) -> list[dict[str, Any]]:
    pending_ids = {item.get("observation_id") for item in reviews
                   if item.get("status") in {"pending", "needs_review"}}
    records = [item for item in observations
            if _floor_count(item) is not None
            and _confidence(item) is not None and _confidence(item) < threshold
            and item.get("observation_id") in pending_ids]
    return sorted(records, key=lambda item: str(item.get("observation_id") or ""))


def unmatched_buildings_by_street(observations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        if item.get("asset_type", item.get("entity_type")) == "building" and _match_status(item) == "unmatched":
            grouped.setdefault(str(item.get("street_id") or "Unassigned"), []).append(item)
    return {street: sorted(records, key=lambda item: str(item.get("observation_id") or ""))
            for street, records in sorted(grouped.items())}


def streetlight_findings(discrepancies: list[dict[str, Any]], references: list[dict[str, Any]],
                         observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = {str(item.get("reference_id")): item for item in references}
    results = []
    for item in discrepancies:
        if item.get("discrepancy_type") != "expected_streetlight_not_observed":
            continue
        ref = refs.get(str(item.get("reference_id")), {})
        source_type = str(ref.get("source_type") or "").lower()
        coverage = str(ref.get("coverage_status") or "").lower()
        complete = coverage in {"complete", "simulated_complete"}
        reference_type = str(ref.get("asset_type") or ref.get("record_type") or "streetlight").strip().lower()
        if not complete or reference_type != "streetlight":
            continue
        simulation = bool(item.get("simulation") or ref.get("simulation") or source_type == "simulated_demo")
        street_id = item.get("street_id") or ref.get("street_id")
        if not street_id and ref.get("latitude") is not None and ref.get("longitude") is not None:
            candidates = [row for row in observations if row.get("street_id") and row.get("latitude") is not None and row.get("longitude") is not None]
            if candidates:
                nearest = min(candidates, key=lambda row: _distance_m(ref, row))
                street_id = nearest.get("street_id")
        results.append({
            **item,
            "street_id": street_id or "Unassigned",
            "interval_meters": STREETLIGHT_INTERVAL_METERS,
            "observed_asset_condition": "no_observation_within_interval",
            "coverage_complete": True,
            "coverage_status": coverage,
            "expected_asset_condition": "expected_in_reference_inventory",
            "observed_asset_condition": "no_observation_within_interval",
            "simulation": simulation,
            "provenance": item.get("provenance") or ref.get("provenance") or ref.get("source"),
            "confidence": item.get("confidence", ref.get("confidence")),
        })
    return sorted(results, key=lambda item: str(item.get("discrepancy_id") or item.get("reference_id") or ""))


def _distance_m(first: dict[str, Any], second: dict[str, Any]) -> float:
    lat1, lat2 = math.radians(float(first["latitude"])), math.radians(float(second["latitude"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(second["longitude"]) - float(first["longitude"]))
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))


def _floor_count(item: dict[str, Any]) -> int | None:
    attrs = item.get("attributes") or {}
    value = attrs.get("visible_floor_count", item.get("visible_floors"))
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(numeric) if math.isfinite(numeric) and numeric.is_integer() else None


def _match_status(item: dict[str, Any]) -> str:
    """Missing/unknown match status is not evidence of an unmatched building."""
    value = item.get("match_status")
    if value is None:
        value = (item.get("match_record") or {}).get("match_status")
    return str(value).strip().lower() if value is not None else "unknown"


def _confidence(item: dict[str, Any]) -> float | None:
    value = item.get("confidence")
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and 0 <= result <= 1 else None


def _finite_nonnegative(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None
