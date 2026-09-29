"""Configurable selection of useful Street View panoramas/views."""

from __future__ import annotations

import math
from typing import Any

from app.services.study_area_service import contains_point


def _distance_meters(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Calculate great-circle distance between two latitude/longitude pairs."""
    latitude1, latitude2 = math.radians(first["latitude"]), math.radians(second["latitude"])
    delta_latitude = latitude2 - latitude1
    delta_longitude = math.radians(second["longitude"] - first["longitude"])
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude1) * math.cos(latitude2) * math.sin(delta_longitude / 2) ** 2
    )
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, haversine)))


def _heading_distance(first: float, second: float) -> float:
    return abs((first - second + 180) % 360 - 180)

def select_useful_views(
    panorama_metadata: list[dict[str, Any]],
    *,
    street: dict[str, Any] | None = None,
    previous_observations: list[dict[str, Any]] | None = None,
    coverage: dict[str, Any] | None = None,
    duplicate_distance_meters: float = 12.0,
    duplicate_heading_degrees: float = 35.0,
) -> list[dict[str, Any]]:
    """Score candidate panorama views and keep only those worth processing.

    The system should avoid processing every possible panorama while preserving
    enough coverage for later observation and fusion.
    """
    candidates: list[dict[str, Any]] = []
    previous_observations = previous_observations or []

    for index, view in enumerate(panorama_metadata):
        if not isinstance(view, dict):
            continue
        status = str(view.get("status") or "ready").lower()
        if status not in {"ready", "available", "confirmed", "verified"}:
            continue

        try:
            latitude = float(view["latitude"])
            longitude = float(view["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        try:
            pitch = float(view["pitch"]) if view.get("pitch") is not None else None
            fov = float(view["field_of_view"]) if view.get("field_of_view") is not None else None
        except (TypeError, ValueError):
            continue
        if pitch is not None and not -90 <= pitch <= 90:
            continue
        if fov is not None and not 0 < fov <= 180:
            continue
        if not contains_point(latitude, longitude):
            continue

        raw_headings = view.get("available_headings")
        if raw_headings is None:
            raw_headings = view.get("headings")
        if not raw_headings and view.get("heading") is not None:
            raw_headings = [view["heading"]]
        if not raw_headings:
            continue
        if isinstance(raw_headings, (str, bytes)):
            continue
        try:
            headings = [float(value) for value in raw_headings]
        except (TypeError, ValueError):
            continue

        quality = view.get("quality") or view.get("view_quality") or {}
        if not isinstance(quality, dict):
            quality = {}
        raw_quality_score = quality.get("score", view.get("quality_score"))
        try:
            quality_score = max(0.0, min(1.0, float(raw_quality_score))) if raw_quality_score is not None else None
        except (TypeError, ValueError):
            quality_score = None

        for heading_index, heading in enumerate(headings):
            if not 0 <= heading <= 360:
                continue
            view_id = str(view.get("view_id") or view.get("panorama_id") or f"view_{index}")
            if len(headings) > 1:
                view_id = f"{view_id}_{heading_index}"
            panorama_ref = str(view.get("panorama_reference") or view.get("panorama_id") or view_id)
            priority = 50
            reasons: list[str] = ["inside_study_area", "heading_available"]
            if street and street.get("street_id"):
                priority += 10
                reasons.append("street_context")
            if coverage and coverage.get("has_coverage"):
                priority += 8
                reasons.append("coverage_available")
            if previous_observations:
                priority += 5
                reasons.append("previous_observation_context")
            if pitch is not None and abs(pitch) <= 30:
                priority += 2
                reasons.append("horizontal_view")
            if quality_score is not None:
                priority += round(quality_score * 20)
                reasons.append("provider_quality")
            candidates.append({
                "view_id": view_id,
                "panorama_reference": panorama_ref,
                "latitude": latitude,
                "longitude": longitude,
                "heading": heading,
                "pitch": pitch,
                "field_of_view": fov,
                "quality": quality or None,
                "selection_reason": "; ".join(reasons),
                "priority": priority,
                "source": view.get("source", "authorized_provider"),
                "source_mode": view.get("source_mode", "unknown"),
                "status": status,
            })

    candidates.sort(key=lambda item: (item["priority"], bool(item["quality"])), reverse=True)
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        duplicate = any(
            _distance_meters(candidate, existing) < duplicate_distance_meters
            and _heading_distance(candidate["heading"], existing["heading"]) < duplicate_heading_degrees
            for existing in selected
        )
        if duplicate:
            continue
        candidate["selection_reason"] += "; coverage_novelty"
        selected.append(candidate)
    return selected
