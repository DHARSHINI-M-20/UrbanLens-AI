"""Geospatial association for observations within the official study area."""

from __future__ import annotations

from typing import Any

from app.services.study_area_service import STUDY_AREA_ID, contains_point


class GeospatialService:
    """Associate observations with the study area and nearby context."""

    def associate_observation(
        self,
        *,
        latitude: float,
        longitude: float,
        street_id: str | None = None,
        study_area_id: str = STUDY_AREA_ID,
        building_reference_id: str | None = None,
    ) -> dict[str, Any]:
        inside_study_area = contains_point(latitude, longitude)
        association_confidence = 0.95 if inside_study_area else 0.0

        return {
            "latitude": latitude,
            "longitude": longitude,
            "street_id": street_id,
            "study_area_id": study_area_id,
            "building_reference_id": building_reference_id,
            "inside_study_area": inside_study_area,
            "association_confidence": association_confidence,
        }
