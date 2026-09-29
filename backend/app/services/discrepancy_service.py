"""Discrepancy detection for observations versus reference data."""

from __future__ import annotations

import math
from typing import Any

from app.services.reference_matching_service import match_reference_record


def _distance_meters(first: dict[str, Any], second: dict[str, Any]) -> float | None:
    if any(item.get(key) is None for item in (first, second) for key in ("latitude", "longitude")):
        return None
    lat1, lat2 = math.radians(float(first["latitude"])), math.radians(float(second["latitude"]))
    delta_lat = lat2 - lat1
    delta_lon = math.radians(float(second["longitude"]) - float(first["longitude"]))
    arc = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))


def detect_discrepancies(
    *,
    observations: list[dict[str, Any]] | None = None,
    references: list[dict[str, Any]] | None = None,
    street_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return evidence-linked observation/reference discrepancies."""
    discrepancies: list[dict[str, Any]] = []
    observations = observations or []
    references = references or []

    def add_discrepancy(
        kind: str,
        *,
        observation: dict[str, Any] | None = None,
        reference: dict[str, Any] | None = None,
        confidence: float | None = None,
        description: str,
    ) -> None:
        observation_id = observation.get("observation_id") if observation else None
        reference_id = (reference or {}).get("reference_id") or (reference or {}).get("_id")
        evidence = observation or {}
        token = observation_id or reference_id or len(discrepancies)
        discrepancies.append({
            "discrepancy_id": f"disc_{kind}_{token}",
            "observation_id": observation_id,
            "reference_id": reference_id,
            "street_id": street_id or evidence.get("street_id"),
            "discrepancy_type": kind,
            "description": description,
            "confidence": confidence,
            "evidence_source_views": list(evidence.get("source_view_ids") or [evidence.get("source_view_id")]
                                           if evidence.get("source_view_id") or evidence.get("source_view_ids") else []),
            "review_status": "pending",
        })

    for observation in observations:
        confidence = observation.get("confidence")
        confidence = float(confidence) if confidence is not None else None
        if confidence is not None and confidence < 0.5:
            add_discrepancy("low_confidence_observation", observation=observation, confidence=confidence,
                            description="Observation confidence is below the configured review threshold.")

        attrs = observation.get("attributes") or {}
        visible_sign_text = attrs.get("visible_sign_text") or []
        if isinstance(visible_sign_text, str):
            visible_sign_text = [visible_sign_text]
        observed_name = attrs.get("building_name") or attrs.get("business_name") or attrs.get("name") or (
            visible_sign_text[0] if visible_sign_text else None
        )
        match = match_reference_record(
            observed_asset_type=str(observation.get("asset_type") or "other"),
            observed_name=observed_name,
            latitude=observation.get("latitude"),
            longitude=observation.get("longitude"),
            references=references,
            street_name=observation.get("street_name"),
            observed_attributes=attrs,
        )
        if match["match_status"] == "unmatched":
            complete_internal_reference = any(
                str(reference.get("source_type") or "").lower() in {"farmwiseai", "farmwise_internal", "internal"}
                and reference.get("coverage_status") == "complete"
                for reference in references
            )
            complete_simulated_reference = any(
                str(reference.get("source_type") or "").lower() == "simulated_demo"
                and reference.get("coverage_status") == "simulated_complete"
                for reference in references
            )
            if complete_internal_reference:
                add_discrepancy("missing_reference_record", observation=observation, confidence=confidence,
                                description="No corresponding record was found in the declared complete internal reference dataset.")
            else:
                add_discrepancy("unmatched_reference_coverage_limited", observation=observation, confidence=confidence,
                                description=("No matching record was found in the simulated register; this is a demo-only discrepancy, not evidence of real-world absence."
                                             if complete_simulated_reference else
                                             "No matching record was found in available references; public reference coverage is incomplete and absence is not evidence."))
        matching_reference = next((item for item in references if str(item.get("reference_id") or item.get("_id")) == str(match.get("matched_reference_id"))), None)
        if matching_reference:
            mismatch_map = {
                "building_use": "building_use_mismatch",
                "visible_floor_count": "floor_count_mismatch",
                "business_name": "business_name_mismatch",
                "building_name": "business_name_mismatch",
            }
            ref_attrs = dict(matching_reference)
            for attribute in match.get("mismatch_attributes", []):
                discrepancy_type = mismatch_map.get(attribute)
                if discrepancy_type:
                    add_discrepancy(discrepancy_type, observation=observation, reference=matching_reference,
                                    confidence=confidence,
                                    description=f"Observed {attribute} differs from the reference record.")

    matched_reference_ids: set[str] = set()
    for observation in observations:
        reference_match = match_reference_record(
            observed_asset_type=str(observation.get("asset_type") or "other"),
            observed_name=(observation.get("attributes") or {}).get("building_name") or (observation.get("attributes") or {}).get("business_name"),
            latitude=observation.get("latitude"),
            longitude=observation.get("longitude"),
            references=references,
        )
        if reference_match["match_status"] in {"matched", "possible_match", "mismatch"}:
            reference_id = reference_match.get("matched_reference_id")
            if reference_id is not None:
                matched_reference_ids.add(str(reference_id))
    for reference in references:
        reference_id = reference.get("reference_id") or reference.get("_id")
        if reference_id is not None and str(reference_id) in matched_reference_ids:
            continue
        record_type = str(reference.get("record_type") or reference.get("asset_type") or "building").lower()
        complete_internal_reference = (
            str(reference.get("source_type") or "").lower() in {"farmwiseai", "farmwise_internal", "internal"}
            and reference.get("coverage_status") == "complete"
        )
        complete_simulated_reference = (
            str(reference.get("source_type") or "").lower() == "simulated_demo"
            and reference.get("coverage_status") == "simulated_complete"
        )
        if record_type in {"streetlight", "electric_pole"} and (complete_internal_reference or complete_simulated_reference):
            observed = any(
                str(item.get("asset_type") or "").lower() == record_type
                and (distance := _distance_meters(reference, item)) is not None
                and distance <= 25
                for item in observations
            )
            if not observed:
                add_discrepancy(f"expected_{record_type}_not_observed", reference=reference,
                                confidence=reference.get("confidence"),
                                description=f"Reference expects a {record_type.replace('_', ' ')} with no nearby observation.")
        elif complete_internal_reference or complete_simulated_reference:
            add_discrepancy("reference_without_observation", reference=reference,
                            confidence=reference.get("confidence"),
                            description="Reference property or asset has no corresponding observation.")

    return discrepancies
