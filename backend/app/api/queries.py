"""Dataset-scoped Task 5 challenge queries over persisted MongoDB records."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.config import get_settings
from app.services.challenge_queries import (
    commercial_over_two_floors, envelope, low_confidence_floor_reviews,
    routed_metrics_summary, streetlight_findings, unmatched_buildings_by_street,
)
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


def _records(collection: str, dataset_id: str) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key != "_id"}
            for item in get_collection(collection).find({"study_area_id": STUDY_AREA_ID, "dataset_id": dataset_id}).limit(5000)]


def _dataset(dataset_id: str | None) -> str:
    value = dataset_id or "tn_study_area_demo_v1"
    if not value or len(value) > 128 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-:" for char in value):
        raise HTTPException(status_code=422, detail="Invalid dataset_id.")
    return value


def _simulation(dataset_id: str, records: list[dict[str, Any]]) -> bool:
    if dataset_id == "tn_study_area_demo_v1":
        return True
    return any(bool(item.get("simulation")) for item in records)


def _run(dataset_id: str | None, operation):
    selected = _dataset(dataset_id)
    try:
        return operation(selected)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc


@router.get("/commercial-buildings-without-match")
def commercial_buildings_without_match(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    def query(selected: str):
        observations = _records("observations", selected)
        result = commercial_over_two_floors(observations)
        return envelope("commercial_buildings_over_two_floors_without_match", selected, result,
                        simulation=_simulation(selected, observations),
                        limitations=["No match means no match in supplied references, not evidence that no official property record exists."])
    return _run(dataset_id, query)


@router.get("/buildings-over-2-floors-without-match")
def buildings_over_two_floors_without_match(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    return commercial_buildings_without_match(dataset_id)


@router.get("/streets-without-streetlights")
def streets_without_streetlights(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    def query(selected: str):
        discrepancies = _records("discrepancies", selected)
        references = _records("reference_records", selected)
        observations = _records("observations", selected)
        result = streetlight_findings(discrepancies, references, observations)
        return envelope("streets_without_streetlight_within_interval", selected, result,
                        simulation=_simulation(selected, discrepancies + references + observations),
                        interval_meters=25,
                        limitations=["Only records declaring complete coverage are eligible. Expected/observed labels come from stored discrepancies; no complete real inventory is available."])
    return _run(dataset_id, query)


@router.get("/low-confidence-floor-counts")
def low_confidence_floor_counts(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    def query(selected: str):
        observations = _records("observations", selected)
        reviews = _records("review_queue", selected)
        threshold = get_settings().floor_count_confidence_threshold
        result = low_confidence_floor_reviews(observations, reviews, threshold)
        return envelope("low_confidence_floor_counts_requiring_review", selected, result,
                        simulation=_simulation(selected, observations + reviews),
                        confidence_threshold=threshold,
                        limitations=["Confidence is not a calibrated accuracy probability."])
    return _run(dataset_id, query)


@router.get("/unmatched-buildings-assets")
def unmatched_buildings_assets(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    return unmatched_buildings_by_street_endpoint(dataset_id)


@router.get("/unmatched-buildings-by-street")
def unmatched_buildings_by_street_endpoint(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    def query(selected: str):
        observations = _records("observations", selected)
        grouped = unmatched_buildings_by_street(observations)
        records = [item for group in grouped.values() for item in group]
        return envelope("unmatched_buildings_grouped_by_street", selected, records,
                        simulation=_simulation(selected, observations),
                        by_street=grouped,
                        limitations=["Unmatched status is relative to the synchronized references."])
    return _run(dataset_id, query)


@router.get("/routed-vs-all-vlm")
def routed_vs_all_vlm(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> dict[str, Any]:
    def query(selected: str):
        metrics = sorted(_records("processing_metrics", selected),
                         key=lambda item: str(item.get("view_id") or item.get("metric_id") or ""))
        summary = routed_metrics_summary(metrics)
        comparison = {"cost_status": "unavailable", "estimated_cost": None}
        payload = envelope("routed_vs_all_vlm", selected, metrics,
                           simulation=_simulation(selected, metrics),
                           limitations=["No all-VLM baseline was executed.", "Verified provider pricing is unavailable; no cost or quality savings are claimed."],
                           measured_routed_metrics=summary,
                           hypothetical_all_vlm_estimate={"status": "NOT_RUN", **comparison},
                           all_vlm_run_performed=False,
                           all_vlm_status="NOT_RUN",
                           quality_comparison_status="NOT_EVALUABLE",
                           cost_status="unavailable")
        return payload
    return _run(dataset_id, query)


@router.get("/observations-by-street/{street_id}")
def observations_by_street(street_id: str, dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> list[dict[str, Any]]:
    selected = _dataset(dataset_id)
    try:
        return [item for item in _records("observations", selected) if item.get("street_id") == street_id]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc


@router.get("/observations-by-asset-type/{asset_type}")
def observations_by_asset_type(asset_type: str, dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> list[dict[str, Any]]:
    selected = _dataset(dataset_id)
    try:
        return [item for item in _records("observations", selected)
                if item.get("asset_type", item.get("entity_type")) == asset_type]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc


@router.get("/review-queue")
def review_queue(dataset_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_:-]{1,128}$")) -> list[dict[str, Any]]:
    selected = _dataset(dataset_id)
    try:
        return _records("review_queue", selected)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
