"""Import supplied road GeoJSON and constrain it to the official study area."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import geopandas as gpd
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.services.study_area_service import STUDY_AREA_ID, get_study_area_geometry

SUPPORTED_ROAD_GEOMETRIES = {"LineString", "MultiLineString"}


def load_road_geojson_file(path: str | Path) -> dict[str, Any]:
    """Load a challenge-provided local GeoJSON file; no network access is used."""
    road_file = Path(path)
    if not road_file.is_file():
        raise ValueError("Road GeoJSON file was not found.")
    try:
        with road_file.open(encoding="utf-8") as source_file:
            return json.load(source_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Road file is not valid JSON/GeoJSON.") from exc


def _road_frame(geojson: dict[str, Any]) -> tuple[gpd.GeoDataFrame, str]:
    """Validate a supplied GeoJSON FeatureCollection and create a GeoDataFrame."""
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Road data must be a GeoJSON FeatureCollection.")
    features = geojson.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Road GeoJSON must contain at least one feature.")
    for feature in features:
        if not isinstance(feature, dict) or not feature.get("geometry"):
            raise ValueError("Every road feature must include a geometry.")
    declared_crs = geojson.get("crs", {}).get("properties", {}).get("name", "EPSG:4326")
    try:
        roads = gpd.GeoDataFrame.from_features(features, crs=declared_crs)
    except Exception as exc:
        raise ValueError("Road GeoJSON has an invalid or unsupported CRS.") from exc
    if roads.crs is None:
        roads = roads.set_crs("EPSG:4326", allow_override=True)
    try:
        # GeoJSON roads with another declared CRS are reprojected only in memory.
        roads = roads.to_crs("EPSG:4326")
    except Exception as exc:
        raise ValueError("Road GeoJSON CRS cannot be converted to WGS84.") from exc
    return roads, str(declared_crs)


def _road_name(properties: dict[str, Any], fallback_number: int) -> str | None:
    """Use common road-name fields when they exist; otherwise keep the name empty."""
    for key in ("name", "street_name", "road_name"):
        if properties.get(key):
            return str(properties[key])
    return None


def prepare_streets(geojson: dict[str, Any], source: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter/clip supplied roads to the official boundary and prepare MongoDB documents."""
    roads, source_crs = _road_frame(geojson)
    study_area: BaseGeometry = shape(get_study_area_geometry())
    documents: list[dict[str, Any]] = []
    rejected = 0

    for index, row in roads.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty or geometry.geom_type not in SUPPORTED_ROAD_GEOMETRIES:
            rejected += 1
            continue
        if not geometry.intersects(study_area):
            rejected += 1
            continue
        clipped = geometry.intersection(study_area)
        if clipped.is_empty or clipped.geom_type not in SUPPORTED_ROAD_GEOMETRIES:
            rejected += 1
            continue
        properties = {key: value for key, value in row.drop(labels="geometry").to_dict().items()
                      if value is not None}
        documents.append({
            "street_id": f"street_{uuid4().hex}",
            "name": _road_name(properties, index),
            "geometry": clipped.__geo_interface__,
            "study_area_id": STUDY_AREA_ID,
            "source": source,
            "status": "ready",
            "attributes": properties,
        })

    return documents, {
        "roads_found": len(roads),
        "roads_inside_or_intersecting": len(documents),
        "roads_rejected": rejected,
        "crs": source_crs,
        "source": source,
    }
