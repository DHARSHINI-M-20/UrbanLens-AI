"""Read-only API for the official FarmwiseAI challenge study area."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.study_area_service import (
    contains_point,
    get_study_area_bounds,
    get_study_area_geojson,
    get_study_area_metadata,
)

router = APIRouter()


class CoordinateInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@router.get("")
def get_study_area() -> dict[str, Any]:
    """Return official source metadata and GeoJSON for frontend map rendering."""
    try:
        return {"metadata": get_study_area_metadata(), "geojson": get_study_area_geojson()}
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/bounds")
def get_bounds() -> dict[str, float]:
    """Return the official study area's longitude/latitude bounding box."""
    try:
        return get_study_area_bounds()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/contains")
def study_area_contains(payload: CoordinateInput) -> dict[str, bool]:
    """Return whether a coordinate lies inside or on the official boundary."""
    try:
        return {"inside_study_area": contains_point(payload.latitude, payload.longitude)}
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
