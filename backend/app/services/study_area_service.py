"""Read the official challenge study-area file as the immutable source of truth."""

from copy import deepcopy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Point

STUDY_AREA_ID = "challenge_study_area"
STUDY_AREA_FILE = Path(__file__).resolve().parents[3] / "data" / "Study_Area" / "Study_area.geojson"


@lru_cache
def _load_study_area() -> tuple[gpd.GeoDataFrame, dict[str, Any], str]:
    """Load and validate the organizer-provided GeoJSON without altering it."""
    if not STUDY_AREA_FILE.exists():
        raise FileNotFoundError(f"Official study-area file was not found: {STUDY_AREA_FILE}")
    with STUDY_AREA_FILE.open(encoding="utf-8") as source_file:
        geojson: dict[str, Any] = json.load(source_file)
    if geojson.get("type") != "FeatureCollection" or not geojson.get("features"):
        raise ValueError("Study_area.geojson must be a non-empty GeoJSON FeatureCollection.")

    source_crs = geojson.get("crs", {}).get("properties", {}).get("name", "EPSG:4326")
    frame = gpd.read_file(STUDY_AREA_FILE)
    # A missing CRS is interpreted as standard GeoJSON WGS84; coordinates are not transformed.
    if frame.crs is None:
        frame = frame.set_crs("EPSG:4326", allow_override=True)
    elif "4326" not in str(frame.crs).upper() and "CRS84" not in str(frame.crs).upper():
        # Reproject only the in-memory analysis copy; the official source file remains untouched.
        frame = frame.to_crs("EPSG:4326")
    if frame.empty or not frame.geometry.is_valid.all():
        raise ValueError("The official study-area geometry is invalid.")
    if not frame.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Study-area geometry must be Polygon or MultiPolygon.")
    return frame, geojson, source_crs


def get_study_area_geojson() -> dict[str, Any]:
    """Return the original GeoJSON content for the frontend, unchanged."""
    _, geojson, _ = _load_study_area()
    return deepcopy(geojson)


def get_study_area_geometry() -> dict[str, Any]:
    """Return the official feature geometry for boundary checks."""
    return deepcopy(get_study_area_geojson()["features"][0]["geometry"])


def get_study_area_bounds() -> dict[str, float]:
    """Return WGS84 bounds in GeoJSON axis order: longitude, then latitude."""
    frame, _, _ = _load_study_area()
    min_longitude, min_latitude, max_longitude, max_latitude = frame.total_bounds
    return {"min_longitude": float(min_longitude), "min_latitude": float(min_latitude),
            "max_longitude": float(max_longitude), "max_latitude": float(max_latitude)}


def contains_point(latitude: float, longitude: float) -> bool:
    """Test whether a latitude/longitude point is inside or on the study boundary."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude or longitude is outside its valid range.")
    frame, _, _ = _load_study_area()
    return bool(frame.geometry.covers(Point(longitude, latitude)).any())


def get_study_area_metadata() -> dict[str, Any]:
    """Describe the organizer-provided source file without copying its geometry."""
    frame, geojson, source_crs = _load_study_area()
    return {"study_area_id": STUDY_AREA_ID, "source": "data/Study_Area/Study_area.geojson",
            "geojson_type": geojson["type"], "crs": source_crs,
            "geometry_type": frame.geom_type.iloc[0], "properties": geojson["features"][0].get("properties", {}),
            "bounds": get_study_area_bounds()}
