"""Reference matching for property and infrastructure datasets."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class ReferenceDataProvider(Protocol):
    """Adapter contract for any explicitly configured reference source."""

    source_name: str

    def find_candidates(self, observation: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Return reference records relevant to the supplied observation."""


class StaticReferenceProvider:
    """Fixture/provider adapter for OSM, Open Buildings, or supplied demo data."""

    def __init__(self, source_name: str, records: Sequence[Mapping[str, Any]]) -> None:
        self.source_name = source_name
        self.records = tuple(dict(record) for record in records)

    def find_candidates(self, observation: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        return self.records


class ReferenceDataAdapter:
    """Combine explicitly supplied reference providers without assuming a register."""

    def __init__(self, providers: Sequence[ReferenceDataProvider] = ()) -> None:
        self.providers = tuple(providers)

    def find_candidates(self, observation: Mapping[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for provider in self.providers:
            for record in provider.find_candidates(observation):
                candidate = dict(record)
                candidate.setdefault("reference_source", provider.source_name)
                candidates.append(candidate)
        return candidates


def match_reference_record(
    *,
    observed_asset_type: str,
    observed_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    references: list[dict[str, Any]],
    street_name: str | None = None,
    observed_attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Match a structural observation against reference records with a soft score."""
    if not references:
        return {
            "match_status": "unmatched",
            "status": "UNMATCHED",
            "match_confidence": 0.0,
            "match_score": 0.0,
            "matched_reference_id": None,
            "reference_source": None,
            "matched_attributes": {},
            "mismatch_attributes": [],
            "match_method": "no_reference_records_available",
            "match_reason": "no_reference_records_available",
        }

    best_match = None
    best_score = -1.0
    for record in references:
        if not isinstance(record, dict):
            continue
        candidate_type = str(record.get("record_type") or record.get("asset_type") or "").lower()
        if candidate_type and observed_asset_type and candidate_type != observed_asset_type.lower():
            continue
        score = 0.0
        if candidate_type:
            score += 0.1
        if observed_name and record.get("name"):
            if str(record.get("name")).lower() == str(observed_name).lower():
                score += 0.45
            elif str(observed_name).lower() in str(record.get("name")).lower():
                score += 0.25
        if latitude is not None and longitude is not None and record.get("latitude") is not None and record.get("longitude") is not None:
            latitude1, latitude2 = math.radians(float(latitude)), math.radians(float(record["latitude"]))
            delta_latitude = latitude2 - latitude1
            delta_longitude = math.radians(float(record["longitude"]) - float(longitude))
            arc = math.sin(delta_latitude / 2) ** 2 + math.cos(latitude1) * math.cos(latitude2) * math.sin(delta_longitude / 2) ** 2
            distance_meters = 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))
            score += max(0.0, 0.35 * (1 - distance_meters / 100))
        if street_name and record.get("street_name"):
            if str(record.get("street_name")).lower() == str(street_name).lower():
                score += 0.15

        if score > best_score:
            best_score = score
            best_match = record

    if best_match is None:
        return {
            "match_status": "unmatched",
            "status": "UNMATCHED",
            "match_confidence": 0.0,
            "match_score": 0.0,
            "matched_reference_id": None,
            "reference_source": None,
            "matched_attributes": {},
            "mismatch_attributes": [],
            "match_method": "attributes_do_not_overlap",
            "match_reason": "attributes_do_not_overlap",
        }

    normalized = max(0.0, min(1.0, best_score))
    if normalized >= 0.65:
        status = "matched"
    elif normalized >= 0.25:
        status = "possible_match"
    else:
        status = "unmatched"

    matched_attributes: dict[str, Any] = {}
    mismatch_attributes: list[str] = []
    for key, observed_value in (observed_attributes or {}).items():
        if observed_value is None or key not in best_match:
            continue
        reference_value = best_match[key]
        if str(observed_value).strip().casefold() == str(reference_value).strip().casefold():
            matched_attributes[key] = observed_value
        else:
            mismatch_attributes.append(key)

    if mismatch_attributes and normalized >= 0.25:
        status = "mismatch"

    return {
        "match_status": status,
        "status": status.upper(),
        "match_confidence": round(normalized, 4),
        "match_score": round(normalized, 4),
        "matched_reference_id": best_match.get("reference_id") or best_match.get("_id"),
        "reference_source": best_match.get("reference_source") or best_match.get("source_type") or best_match.get("source"),
        "matched_attributes": matched_attributes,
        "mismatch_attributes": mismatch_attributes,
        "match_method": "type_name_distance_attribute_score",
        "match_reason": "closest_reference_with_overlap_score",
    }


def match_observation(
    observation: Mapping[str, Any],
    adapter: ReferenceDataAdapter,
) -> dict[str, Any]:
    """Match one observation against the sources explicitly installed in an adapter."""
    attributes = dict(observation.get("attributes") or {})
    visible_sign_text = attributes.get("visible_sign_text") or []
    if isinstance(visible_sign_text, str):
        visible_sign_text = [visible_sign_text]
    name = (
        attributes.get("building_name") or attributes.get("business_name") or attributes.get("name")
        or (visible_sign_text[0] if visible_sign_text else None)
    )
    candidates = adapter.find_candidates(observation)
    result = match_reference_record(
        observed_asset_type=str(observation.get("asset_type") or "other"),
        observed_name=name,
        latitude=observation.get("latitude"),
        longitude=observation.get("longitude"),
        references=candidates,
        street_name=observation.get("street_name"),
        observed_attributes=attributes,
    )
    return {
        "observation_id": observation.get("observation_id"),
        "reference_coverage": sorted({str(item.get("coverage_status") or "unknown") for item in candidates})
        or ["unavailable"],
        "absence_is_evidence": any(
            str(item.get("source_type") or "").lower() in {"farmwiseai", "farmwise_internal", "internal"}
            and item.get("coverage_status") == "complete"
            for item in candidates
        ),
        **result,
    }
