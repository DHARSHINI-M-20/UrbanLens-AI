"""Human-review API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


class ReviewInput(BaseModel):
    review_id: str = Field(min_length=1)
    observation_id: str | None = None
    reason: str = "inspection_required"
    priority: str = "medium"
    status: Literal["pending", "approved", "rejected", "needs_review"] = "pending"
    reviewer_result: str | None = None
    reviewer: str | None = None
    reviewer_decision: str | None = None


class ReviewDecisionInput(BaseModel):
    status: Literal["pending", "approved", "rejected", "needs_review"]
    reviewer: str = Field(min_length=1)
    reviewer_decision: str | None = None


@router.get("")
def list_reviews(dataset_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    try:
        query = {"study_area_id": STUDY_AREA_ID}
        if dataset_id:
            query["dataset_id"] = dataset_id
        items = list(get_collection("review_queue").find(query))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.post("/")
def create_review(payload: ReviewInput) -> dict[str, Any]:
    document = payload.model_dump(mode="python")
    document.setdefault("study_area_id", STUDY_AREA_ID)
    document.setdefault("created_at", __import__("datetime").datetime.utcnow().isoformat())
    try:
        get_collection("review_queue").replace_one({"review_id": payload.review_id}, document, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return document


@router.patch("/{review_id}/decision")
def record_review_decision(review_id: str, payload: ReviewDecisionInput) -> dict[str, Any]:
    reviewed_at = datetime.now(timezone.utc).isoformat()
    updates = {
        "status": payload.status,
        "reviewer": payload.reviewer.strip(),
        "reviewer_decision": payload.reviewer_decision,
        "reviewed_at": reviewed_at,
    }
    if not updates["reviewer"]:
        raise HTTPException(status_code=422, detail="Reviewer identity is required.")
    try:
        collection = get_collection("review_queue")
        result = collection.update_one(
            {"review_id": review_id, "study_area_id": STUDY_AREA_ID}, {"$set": updates}
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=404, detail="Review queue entry not found.")
        item = collection.find_one({"review_id": review_id, "study_area_id": STUDY_AREA_ID})
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    item.pop("_id", None)
    return item
