"""Shared models for entity fusion, matching, review, and processing."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.observation import EntityType, ProcessingRoute, ReviewStatus


class UnifiedEntity(BaseModel):
    entity_id: str
    entity_type: EntityType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    attributes: dict[str, Any] = Field(default_factory=dict)
    observation_ids: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MatchResult(BaseModel):
    match_id: str
    observation_id: str
    reference_id: str | None = None
    unified_entity_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    match_method: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Discrepancy(BaseModel):
    discrepancy_id: str
    entity_id: str
    discrepancy_type: str
    observed_value: Any | None = None
    reference_value: Any | None = None
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewItem(BaseModel):
    review_id: str
    entity_id: str
    observation_id: str | None = None
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingRun(BaseModel):
    run_id: str
    route: ProcessingRoute
    status: str
    model_name: str | None = None
    input_reference: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
