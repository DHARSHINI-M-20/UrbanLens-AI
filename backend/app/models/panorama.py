"""Panorama data model."""

from datetime import datetime

from pydantic import BaseModel, Field


class Panorama(BaseModel):
    panorama_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    captured_at: datetime | None = None
