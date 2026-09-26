"""Street/corridor import routes constrained to the official study area."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.street_service import prepare_streets
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


class RoadImportInput(BaseModel):
    geojson: dict[str, Any]
    source: str = Field(min_length=1, max_length=200)


def _public(document: dict[str, Any]) -> dict[str, Any]:
    document.pop("_id", None)
    return document


@router.get("")
def list_streets() -> list[dict[str, Any]]:
    """List imported roads that belong to the official challenge study area."""
    try:
        return [_public(item) for item in get_collection("streets").find(
            {"study_area_id": STUDY_AREA_ID}
        )]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc


@router.post("/import")
def import_streets(payload: RoadImportInput) -> dict[str, Any]:
    """Import a challenge-provided or manually supplied GeoJSON road dataset."""
    try:
        documents, summary = prepare_streets(payload.geojson, payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        if documents:
            get_collection("streets").insert_many(documents)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return summary


@router.get("/{street_id}")
def get_street(street_id: str) -> dict[str, Any]:
    """Get one imported street/corridor in the official study area."""
    try:
        street = get_collection("streets").find_one(
            {"street_id": street_id, "study_area_id": STUDY_AREA_ID}
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    if street is None:
        raise HTTPException(status_code=404, detail="Street not found in the official study area.")
    return _public(street)
