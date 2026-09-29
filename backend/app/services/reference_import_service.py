"""Boundary validation for manually imported reference records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from shapely.geometry import Point, mapping, shape

from app.services.study_area_service import STUDY_AREA_ID, get_study_area_geometry


def normalize_manual_reference_records(
    records: Sequence[Mapping[str, Any]],
    *,
    source: str,
    source_type: str,
    study_area_geometry: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Keep only valid references intersecting the official boundary and clip geometry.

    Original source geometry is retained as `source_geometry` whenever clipping
    changes it. Supplied source identifiers and provenance fields are preserved.
    """
    official_geometry = shape(study_area_geometry or get_study_area_geometry())
    if official_geometry.is_empty or not official_geometry.is_valid:
        raise ValueError("The official study-area geometry is invalid.")

    accepted: list[dict[str, Any]] = []
    excluded = 0
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            excluded += 1
            continue
        record = dict(raw_record)
        try:
            source_geometry_data = record.get("geometry")
            if source_geometry_data is not None:
                source_geometry = shape(source_geometry_data)
            elif record.get("latitude") is not None and record.get("longitude") is not None:
                source_geometry = Point(float(record["longitude"]), float(record["latitude"]))
            else:
                excluded += 1
                continue
            if source_geometry.is_empty or not source_geometry.is_valid:
                excluded += 1
                continue
            if not source_geometry.intersects(official_geometry):
                excluded += 1
                continue
            clipped_geometry = source_geometry.intersection(official_geometry)
            if clipped_geometry.is_empty or not clipped_geometry.is_valid:
                excluded += 1
                continue
            representative = clipped_geometry.representative_point()
        except (AttributeError, TypeError, ValueError, KeyError):
            excluded += 1
            continue

        record["reference_id"] = str(record.get("reference_id") or f"manual:{uuid4().hex}")
        record["source"] = record.get("source") or source
        record["reference_source"] = record.get("reference_source") or record["source"]
        record["source_type"] = record.get("source_type") or source_type
        record["study_area_id"] = STUDY_AREA_ID
        if not clipped_geometry.equals(source_geometry):
            record.setdefault("source_geometry", mapping(source_geometry))
        record["geometry"] = mapping(clipped_geometry)
        record["latitude"] = float(representative.y)
        record["longitude"] = float(representative.x)
        accepted.append(record)
    return accepted, excluded
