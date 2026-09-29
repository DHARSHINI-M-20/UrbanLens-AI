"""View management route for selected panorama coverage metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.study_area_service import STUDY_AREA_ID, contains_point

router = APIRouter()


class ViewDocument(BaseModel):
    view_id: str = Field(min_length=1)
    panorama_reference: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    heading: float | None = Field(default=None, ge=0, le=360)
    pitch: float | None = Field(default=None, ge=-90, le=90)
    field_of_view: float | None = Field(default=None, gt=0, le=180)
    selection_reason: str | None = None
    priority: int = 0
    status: str = "ready"
    study_area_id: str = STUDY_AREA_ID
    source_mode: str = "unknown"


class ViewSelectionInput(BaseModel):
    panorama_ids: list[str] = Field(min_length=1)
    duplicate_distance_meters: float = Field(default=12, gt=0, le=500)


@router.get("")
def list_views() -> list[dict[str, Any]]:
    try:
        items = list(get_collection("views").find({"study_area_id": STUDY_AREA_ID}))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.post("/register")
def register_view(payload: ViewDocument) -> dict[str, Any]:
    if not contains_point(payload.latitude, payload.longitude):
        raise HTTPException(status_code=422, detail="View is outside the official study area.")
    document = payload.model_dump(mode="python")
    document["study_area_id"] = STUDY_AREA_ID
    try:
        get_collection("views").replace_one({"view_id": payload.view_id}, document, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return document


@router.post("/select")
def select_views(payload: ViewSelectionInput) -> dict[str, Any]:
    from app.services.view_selection_service import select_useful_views

    try:
        panoramas = list(get_collection("panoramas").find({
            "panorama_id": {"$in": payload.panorama_ids},
            "study_area_id": STUDY_AREA_ID,
        }))
        if not panoramas:
            raise HTTPException(status_code=404, detail="No requested in-area panoramas were found.")
        candidates = []
        for panorama in panoramas:
            metadata = panorama.get("available_view_metadata") or {}
            candidates.append({
                "panorama_id": panorama["panorama_id"],
                "panorama_reference": panorama.get("panorama_reference") or panorama["panorama_id"],
                "latitude": panorama["latitude"],
                "longitude": panorama["longitude"],
                "available_headings": panorama.get("available_headings") or [],
                "pitch": metadata.get("pitch"),
                "field_of_view": metadata.get("field_of_view"),
                "quality": metadata.get("quality"),
                "source": panorama.get("source", "unknown"),
                "source_mode": "synthetic_fixture" if "mock" in str(panorama.get("source", "")).lower() or "synthetic" in str(panorama.get("source", "")).lower() else "provider",
                "status": "ready",
            })
        selected = select_useful_views(
            candidates,
            duplicate_distance_meters=payload.duplicate_distance_meters,
        )
        collection = get_collection("views")
        for document in selected:
            document["study_area_id"] = STUDY_AREA_ID
            document["panorama_id"] = document["panorama_reference"]
            collection.replace_one({"view_id": document["view_id"]}, document, upsert=True)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {"selected_count": len(selected), "views": selected}
