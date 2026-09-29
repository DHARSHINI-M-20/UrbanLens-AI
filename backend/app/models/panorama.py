"""Panorama data model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Panorama(BaseModel):
    panorama_id: str
    panorama_reference: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    captured_at: datetime | None = None
    source: str = "authorized_provider"
    study_area_id: str = "challenge_study_area"
    available_headings: list[float] = Field(default_factory=list)
    available_view_metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_reference: str | None = None
