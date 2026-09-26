"""Sampling-point routes; these do not contact Google or create panoramas."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.sampling_service import generate_sampling_points
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


class SamplingRequest(BaseModel):
    spacing_meters: float = Field(gt=0, le=5000)


def _public(document: dict[str, Any]) -> dict[str, Any]:
    document.pop("_id", None)
    document.pop("location", None)
    return document


@router.post("/generate")
def generate_samples(payload: SamplingRequest) -> dict[str, int | float | str]:
    """Generate and store a fresh official-boundary sampling grid."""
    try:
        points, total_points = generate_sampling_points(payload.spacing_meters)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        collection = get_collection("sampling_points")
        # One active grid per study area avoids duplicate samples on repeated requests.
        collection.delete_many({"study_area_id": STUDY_AREA_ID})
        if points:
            collection.insert_many(points)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {"study_area_id": STUDY_AREA_ID, "spacing_meters": payload.spacing_meters,
            "total_points": total_points, "points_inside": len(points)}


@router.get("/points")
def list_sampling_points() -> list[dict[str, Any]]:
    """List currently stored sample coordinates for the official study area."""
    try:
        return [_public(item) for item in get_collection("sampling_points").find(
            {"study_area_id": STUDY_AREA_ID}
        )]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc


@router.delete("/points")
def delete_sampling_points() -> dict[str, int]:
    """Remove generated sample points; this does not alter the official boundary."""
    try:
        result = get_collection("sampling_points").delete_many({"study_area_id": STUDY_AREA_ID})
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {"deleted_points": result.deleted_count}
