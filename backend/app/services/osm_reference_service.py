"""Public OpenStreetMap reference ingestion with study-area filtering and provenance."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from shapely.geometry import LineString, Point, Polygon, shape, mapping

from app.services.study_area_service import STUDY_AREA_ID, get_study_area_geojson

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"


class OverpassFetcher(Protocol):
    def fetch(self, query: str) -> Mapping[str, Any]:
        """Execute an Overpass query and return its JSON response."""


class HTTPOverpassFetcher:
    """HTTP client for the public Overpass API; no credentials are required."""

    def __init__(self, endpoint: str = OVERPASS_ENDPOINT, *, timeout_seconds: float = 45.0) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def fetch(self, query: str) -> Mapping[str, Any]:
        response = httpx.post(
            self.endpoint,
            data={"data": query},
            timeout=self.timeout_seconds,
            headers={"User-Agent": "UrbanLensAI-prototype/1.0 (public OSM reference import)"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("Overpass returned a non-object JSON response.")
        return payload


def build_overpass_query(study_geojson: Mapping[str, Any]) -> str:
    """Query buildings and essential infrastructure inside the study-area bbox."""
    geometry = shape(study_geojson["features"][0]["geometry"])
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    bounds = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    return (
        "[out:json][timeout:40];("
        f'way["building"]({bounds});'
        f'node["highway"="street_lamp"]({bounds});'
        f'way["highway"="street_lamp"]({bounds});'
        f'node["power"="pole"]({bounds});'
        f'way["power"="pole"]({bounds});'
        ");out body geom;"
    )


def normalize_osm_response(
    response: Mapping[str, Any],
    *,
    study_geojson: Mapping[str, Any] | None = None,
    ingested_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert Overpass elements into validated, provenance-rich references.

    OSM coverage is inherently incomplete. The returned coverage object must be
    consulted before interpreting an unmatched observation.
    """
    study_geojson = study_geojson or get_study_area_geojson()
    feature_geometry = shape(study_geojson["features"][0]["geometry"])
    timestamp = (ingested_at or datetime.now(timezone.utc)).isoformat()
    elements = response.get("elements", [])
    if not isinstance(elements, Sequence) or isinstance(elements, (str, bytes)):
        raise ValueError("Overpass response elements must be a list.")

    references: list[dict[str, Any]] = []
    rejected = 0
    for element in elements:
        if not isinstance(element, Mapping):
            rejected += 1
            continue
        osm_type, osm_id = element.get("type"), element.get("id")
        if osm_type not in {"node", "way"} or osm_id is None:
            rejected += 1
            continue
        tags = dict(element.get("tags") or {})
        if tags.get("building"):
            asset_type = "building"
        elif tags.get("highway") == "street_lamp":
            asset_type = "streetlight"
        elif tags.get("power") == "pole":
            asset_type = "electric_pole"
        else:
            continue

        try:
            if osm_type == "node":
                source_geometry = Point(float(element["lon"]), float(element["lat"]))
            else:
                coords = [(float(point["lon"]), float(point["lat"])) for point in element.get("geometry", [])]
                if len(coords) < 2:
                    rejected += 1
                    continue
                if asset_type == "building":
                    if coords[0] != coords[-1] or len(coords) < 4:
                        rejected += 1
                        continue
                    source_geometry = Polygon(coords)
                else:
                    source_geometry = Point(coords[0]) if len(coords) == 1 else LineString(coords)
            if source_geometry.is_empty or not source_geometry.is_valid or not source_geometry.intersects(feature_geometry):
                rejected += 1
                continue
            geometry = source_geometry.intersection(feature_geometry)
            if geometry.is_empty or not geometry.is_valid:
                rejected += 1
                continue
            point = geometry.representative_point()
            geojson_geometry = mapping(geometry)
        except (KeyError, TypeError, ValueError):
            rejected += 1
            continue

        references.append({
            "reference_id": f"osm:{osm_type}/{osm_id}",
            "osm_type": osm_type,
            "osm_id": int(osm_id),
            "record_type": asset_type,
            "asset_type": asset_type,
            "name": tags.get("name"),
            "building_use": tags.get("building:use") or tags.get("shop") or tags.get("amenity"),
            "visible_floor_count": _optional_int(tags.get("building:levels")),
            "tags": tags,
            "latitude": float(point.y),
            "longitude": float(point.x),
            "geometry": geojson_geometry,
            "source_geometry": mapping(source_geometry),
            "reference_source": "OpenStreetMap",
            "source": "OpenStreetMap",
            "source_type": "public_osm",
            "attribution": "© OpenStreetMap contributors",
            "study_area_id": STUDY_AREA_ID,
            "coverage_status": "incomplete_public_coverage",
            "ingested_at": timestamp,
        })

    coverage = {
        "reference_source": "OpenStreetMap",
        "source_type": "public_osm",
        "study_area_id": STUDY_AREA_ID,
        "coverage_status": "incomplete_public_coverage",
        "records_received": len(elements),
        "records_imported": len(references),
        "records_rejected_outside_or_invalid": rejected,
        "absence_is_evidence": False,
        "attribution": "© OpenStreetMap contributors",
        "ingested_at": timestamp,
    }
    return references, coverage


def _optional_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


class OSMReferenceIngestor:
    """Fetch and normalize OSM records with an injectable deterministic fetcher."""

    def __init__(
        self,
        fetcher: OverpassFetcher | None = None,
        *,
        study_geojson_loader: Callable[[], Mapping[str, Any]] = get_study_area_geojson,
    ) -> None:
        self.fetcher = fetcher or HTTPOverpassFetcher()
        self.study_geojson_loader = study_geojson_loader

    def ingest(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        study_geojson = self.study_geojson_loader()
        response = self.fetcher.fetch(build_overpass_query(study_geojson))
        return normalize_osm_response(response, study_geojson=study_geojson)
