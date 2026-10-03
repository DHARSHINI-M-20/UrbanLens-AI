"""Versioned, explicit ground-truth schema used by evaluation datasets."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class EvaluationMetadata(BaseModel):
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    synthetic: bool
    purpose: str
    limitations: list[str] = Field(default_factory=list)
    exhaustive_classes: list[str] = Field(default_factory=list)


class BuildingGroundTruth(BaseModel):
    building_id: str
    presence: bool = True
    bounding_box: EvaluationBox | None = None
    floor_count: int | None = Field(default=None, ge=0)
    building_use: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    matched: bool | None = None
    reference_id: str | None = None
    discrepancy_types: list[str] | None = None
    review_required: bool | None = None
    expected_route: Literal["local", "vlm", "unavailable", "error"] | None = None


class AssetGroundTruth(BaseModel):
    asset_id: str | None = None
    asset_type: str
    presence: bool = True
    bounding_box: EvaluationBox | None = None


class OCRGroundTruth(BaseModel):
    region_id: str
    ground_truth_text: str | None = None
    text_region: EvaluationBox | None = None


class PositionGroundTruth(BaseModel):
    entity_id: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    reference_geometry: dict[str, Any] | None = None


class ReferenceMatchGroundTruth(BaseModel):
    entity_id: str
    reference_id: str | None = None
    matched: bool | None = None


class DiscrepancyGroundTruth(BaseModel):
    entity_id: str
    discrepancy_type: str
    expected_present: bool | None = None


class ReviewRoutingGroundTruth(BaseModel):
    entity_id: str
    review_required: bool | None = None
    expected_route: Literal["local", "vlm", "unavailable", "error"] | None = None


class GroundTruthSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    image_id: str = Field(min_length=1)
    panorama_id: str | None = None
    source: str | None = None
    provenance: str | None = None
    labeled_classes: list[str] = Field(default_factory=list)
    buildings: list[BuildingGroundTruth] = Field(default_factory=list)
    assets: list[AssetGroundTruth] = Field(default_factory=list)
    ocr: list[OCRGroundTruth] = Field(default_factory=list)
    positioning: list[PositionGroundTruth] = Field(default_factory=list)
    reference_matches: list[ReferenceMatchGroundTruth] = Field(default_factory=list)
    discrepancies: list[DiscrepancyGroundTruth] = Field(default_factory=list)
    review_routing: list[ReviewRoutingGroundTruth] = Field(default_factory=list)


class GroundTruthDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: EvaluationMetadata
    samples: list[GroundTruthSample]

    @model_validator(mode="after")
    def validate_scope(self) -> "GroundTruthDataset":
        ids = [sample.image_id for sample in self.samples]
        if len(ids) != len(set(ids)):
            raise ValueError("image_id values must be unique within an evaluation dataset.")
        wrong_scope = [sample.image_id for sample in self.samples
                       if sample.dataset_id != self.metadata.dataset_id]
        if wrong_scope:
            raise ValueError("Every ground-truth sample must use the metadata dataset_id.")
        return self
