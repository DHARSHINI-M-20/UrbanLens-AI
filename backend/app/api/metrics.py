"""Processing metrics API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.processing_metrics_service import ProcessingMetricsService
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


@router.get("")
def list_metrics() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("processing_metrics").find({"study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.get("/summary")
def metrics_summary() -> dict[str, Any]:
    try:
        items = list(get_collection("processing_metrics").find({"study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    metrics = ProcessingMetricsService()
    metrics.records = [{key: value for key, value in item.items() if key != "_id"} for item in items]
    return {
        **metrics.summary(),
        "workflow_cost_comparison": metrics.hypothetical_all_vlm_comparison(),
    }
