"""Discrepancy API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.discrepancy_service import detect_discrepancies
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


class DiscrepancyInput(BaseModel):
    discrepancy_id: str = Field(min_length=1)
    observation_id: str | None = None
    reference_id: str | None = None
    street_id: str | None = None
    discrepancy_type: str = "missing_reference_record"
    description: str = ""
    confidence: float = Field(ge=0, le=1)
    review_status: str = "pending"
    evidence_source_views: list[str] = Field(default_factory=list)


@router.get("")
def list_discrepancies(dataset_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    try:
        query = {"study_area_id": STUDY_AREA_ID}
        if dataset_id:
            query["dataset_id"] = dataset_id
        items = list(get_collection("discrepancies").find(query))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.post("/")
def create_discrepancy(payload: DiscrepancyInput) -> dict[str, Any]:
    document = payload.model_dump(mode="python")
    document.setdefault("study_area_id", STUDY_AREA_ID)
    document.setdefault("created_at", __import__("datetime").datetime.utcnow().isoformat())
    try:
        get_collection("discrepancies").replace_one({"discrepancy_id": payload.discrepancy_id}, document, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return document


@router.post("/generate")
def generate_discrepancies() -> dict[str, Any]:
    try:
        observations = list(get_collection("observations").find({"study_area_id": STUDY_AREA_ID}).limit(5000))
        references = list(get_collection("reference_records").find({"study_area_id": STUDY_AREA_ID}).limit(5000))
        generated = detect_discrepancies(observations=observations, references=references)
        for item in generated:
            item["study_area_id"] = STUDY_AREA_ID
            get_collection("discrepancies").replace_one(
                {"discrepancy_id": item["discrepancy_id"]}, item, upsert=True,
            )
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {"generated": len(generated), "discrepancies": generated}
