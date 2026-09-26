"""Shared Pydantic schemas for Street View-derived urban observations."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    BUILDING = "building"
    STREETLIGHT = "streetlight"
    ELECTRIC_POLE = "electric_pole"
    TRAFFIC_SIGNAL = "traffic_signal"
    TRAFFIC_SIGN = "traffic_sign"
    WASTE_BIN = "waste_bin"
    TRANSFORMER = "transformer"
    UTILITY_ASSET = "utility_asset"
    SIGNBOARD = "signboard"


class ProbableUse(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    INSTITUTIONAL = "institutional"
    UNKNOWN = "unknown"


class ProcessingRoute(str, Enum):
    LIGHTWEIGHT = "lightweight"
    VLM = "vlm"
    HYBRID = "hybrid"
    MANUAL = "manual"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    CORRECTED = "corrected"


class BoundingBox(BaseModel):
    """Pixel-space detection box in the panorama/image frame."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class BuildingAttributes(BaseModel):
    """Optional building-specific facts inferred from a view."""

    model_config = ConfigDict(extra="allow")
    building_material: str | None = None
    roof_type: str | None = None
    condition: str | None = None


class AssetAttributes(BaseModel):
    """Flexible details for streetlights, poles, and future urban assets."""

    model_config = ConfigDict(extra="allow")
    material: str | None = None
    condition: str | None = None
    operational_status: str | None = None


class OCRResult(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    bounding_box: BoundingBox | None = None


class Observation(BaseModel):
    """One detected urban object, building, or asset from a panorama."""

    observation_id: str
    panorama_id: str
    entity_type: EntityType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    bounding_box: BoundingBox | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    visible_floors: int | None = Field(default=None, ge=0)
    probable_use: ProbableUse = ProbableUse.UNKNOWN
    ocr_text: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_name: str
    processing_route: ProcessingRoute
    latency_ms: float | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    evidence_reference: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
