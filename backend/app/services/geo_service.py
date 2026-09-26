"""Small GeoPandas/Shapely helpers for study-area boundary checks."""

from typing import Any

import geopandas as gpd
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry


def parse_area_geometry(geometry: dict[str, Any]) -> BaseGeometry:
    """Validate a GeoJSON Polygon or MultiPolygon study-area geometry."""
    try:
        parsed = shape(geometry)
    except Exception as exc:
        raise ValueError("Study area geometry must be valid GeoJSON.") from exc
    if parsed.geom_type not in {"Polygon", "MultiPolygon"} or parsed.is_empty or not parsed.is_valid:
        raise ValueError("Study area geometry must be a valid GeoJSON Polygon or MultiPolygon.")
    return parsed


def parse_street_geometry(geometry: dict[str, Any]) -> BaseGeometry:
    """Validate a GeoJSON LineString or MultiLineString corridor geometry."""
    try:
        parsed = shape(geometry)
    except Exception as exc:
        raise ValueError("Street geometry must be valid GeoJSON.") from exc
    if parsed.geom_type not in {"LineString", "MultiLineString"} or parsed.is_empty or not parsed.is_valid:
        raise ValueError("Street geometry must be a valid GeoJSON LineString or MultiLineString.")
    return parsed


def contains_coordinate(area_geometry: dict[str, Any], latitude: float, longitude: float) -> bool:
    """Return true when a WGS84 coordinate is covered by the study boundary."""
    area = parse_area_geometry(area_geometry)
    return bool(gpd.GeoSeries([area], crs="EPSG:4326").covers(Point(longitude, latitude)).iloc[0])


def street_is_inside_area(area_geometry: dict[str, Any], street_geometry: dict[str, Any]) -> bool:
    """Return true only when the full street corridor is inside/on the boundary."""
    area = parse_area_geometry(area_geometry)
    street = parse_street_geometry(street_geometry)
    return bool(gpd.GeoSeries([area], crs="EPSG:4326").covers(street).iloc[0])
