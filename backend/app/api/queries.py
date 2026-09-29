"""Challenge query endpoints for observations, discrepancies, and review queue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


def _public(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        item = dict(item)
        item.pop("_id", None)
        result.append(item)
    return result


@router.get("/commercial-buildings-without-match")
def commercial_buildings_without_match() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("observations").find({
            "study_area_id": STUDY_AREA_ID,
            "asset_type": "building",
            "attributes.building_use": "commercial",
            "match_status": {"$in": ["unmatched", "possible_match"]},
        }))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/streets-without-streetlights")
def streets_without_streetlights() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("discrepancies").find({
            "study_area_id": STUDY_AREA_ID,
            "discrepancy_type": "expected_streetlight_not_observed",
        }))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/low-confidence-floor-counts")
def low_confidence_floor_counts() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("observations").find({
            "study_area_id": STUDY_AREA_ID,
            "attributes.visible_floor_count": {"$exists": True},
            "confidence": {"$lt": 0.7},
        }))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/unmatched-buildings-assets")
def unmatched_buildings_assets() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("matches").find({
            "study_area_id": STUDY_AREA_ID,
            "match_status": {"$in": ["unmatched", "possible_match"]},
        }))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/observations-by-street/{street_id}")
def observations_by_street(street_id: str) -> list[dict[str, Any]]:
    try:
        items = list(get_collection("observations").find({"street_id": street_id, "study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/observations-by-asset-type/{asset_type}")
def observations_by_asset_type(asset_type: str) -> list[dict[str, Any]]:
    try:
        items = list(get_collection("observations").find({"asset_type": asset_type, "study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)


@router.get("/review-queue")
def review_queue() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("review_queue").find({"study_area_id": STUDY_AREA_ID}).sort("created_at", -1))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return _public(items)
