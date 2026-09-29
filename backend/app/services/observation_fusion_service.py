"""Multi-view duplicate handling and canonical observation fusion."""

from __future__ import annotations

import hashlib
import math
from typing import Any

FUSABLE_TYPES = {"building", "streetlight", "electric_pole", "signboard"}


def _distance_meters(first: dict[str, Any], second: dict[str, Any]) -> float | None:
    if first.get("latitude") is None or first.get("longitude") is None:
        return None
    if second.get("latitude") is None or second.get("longitude") is None:
        return None
    lat1, lat2 = math.radians(float(first["latitude"])), math.radians(float(second["latitude"]))
    delta_lat = lat2 - lat1
    delta_lon = math.radians(float(second["longitude"]) - float(first["longitude"]))
    arc = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))


def _normalized(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def _attributes_compatible(first: dict[str, Any], second: dict[str, Any]) -> bool:
    keys = ("building_name", "business_name", "name", "building_use", "visible_floor_count")
    first_attrs, second_attrs = first.get("attributes") or {}, second.get("attributes") or {}
    for key in keys:
        left, right = first_attrs.get(key), second_attrs.get(key)
        if left is None or right is None:
            continue
        if key == "visible_floor_count":
            try:
                if abs(int(left) - int(right)) > 1:
                    return False
            except (TypeError, ValueError):
                return False
        elif _normalized(left) != _normalized(right):
            return False
    return True


def fuse_observations(
    observations: list[dict[str, Any]],
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    street_id: str | None = None,
) -> dict[str, Any]:
    """Combine duplicate observations while preserving original records."""
    if not observations:
        raise ValueError("No observations were provided for fusion.")

    source_ids = [str(obs.get("observation_id")) for obs in observations if obs.get("observation_id")]
    asset_type = observations[0].get("asset_type", "other")
    fused_attributes: dict[str, Any] = {}
    for obs in observations:
        for key, value in (obs.get("attributes") or {}).items():
            if value is not None:
                fused_attributes.setdefault(key, value)

    confidence_values = [float(obs.get("confidence", 0.0) or 0.0) for obs in observations]
    fused_confidence = max(confidence_values) if confidence_values else 0.0
    token = hashlib.sha1("|".join(source_ids).encode("utf-8")).hexdigest()[:12]
    source_views = list(dict.fromkeys(
        str(obs.get("source_view_id")) for obs in observations if obs.get("source_view_id")
    ))
    positioned = [
        obs["positioning"] for obs in observations
        if isinstance(obs.get("positioning"), dict)
        and obs["positioning"].get("latitude") is not None
        and obs["positioning"].get("longitude") is not None
    ]
    positioned.sort(key=lambda item: item.get("positioning_method") != "multi_view_ray_intersection")
    canonical_position = positioned[0] if positioned else None
    return {
        "canonical_observation_id": f"fused_{asset_type}_{token}",
        "source_observation_ids": source_ids,
        "latitude": canonical_position["latitude"] if canonical_position else latitude,
        "longitude": canonical_position["longitude"] if canonical_position else longitude,
        "building_reference_id": canonical_position.get("building_reference_id") if canonical_position else None,
        "positioning_method": canonical_position.get("positioning_method") if canonical_position else None,
        "positioning_confidence": canonical_position.get("positioning_confidence") if canonical_position else None,
        "positioning_confidence_status": canonical_position.get("positioning_confidence_status") if canonical_position else None,
        "positioning_review_status": canonical_position.get("review_status") if canonical_position else "needs_review",
        "street_id": street_id,
        "asset_type": asset_type,
        "observation_count": len(observations),
        "supporting_view_count": len(source_views),
        "source_view_ids": source_views,
        "fused_attributes": fused_attributes,
        "fused_confidence": fused_confidence,
        "fusion_method": "spatial_proximity_and_attribute_compatibility",
    }


def fuse_nearby_observations(
    observations: list[dict[str, Any]],
    *,
    max_distance_meters: float = 12.0,
) -> list[dict[str, Any]]:
    """Cluster repeated observations without deleting their source records."""
    if max_distance_meters <= 0:
        raise ValueError("max_distance_meters must be positive.")
    groups: list[list[dict[str, Any]]] = []
    for observation in observations:
        asset_type = str(observation.get("asset_type") or "").lower()
        if asset_type not in FUSABLE_TYPES or not observation.get("observation_id"):
            continue
        target_group = next((group for group in groups if all(
            str(member.get("asset_type") or "").lower() == asset_type
            and _attributes_compatible(member, observation)
            and (distance := _distance_meters(member, observation)) is not None
            and distance <= max_distance_meters
            for member in group
        )), None)
        if target_group is None:
            groups.append([observation])
        else:
            target_group.append(observation)

    return [fuse_observations(group) for group in groups if len(group) > 1]
