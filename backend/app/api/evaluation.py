"""Dataset-scoped, offline Task 5 evaluation endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.runner import EvaluationRunner, FIXTURE_DATASET_ID

router = APIRouter()


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: Literal["urbanlens_synthetic_eval_v1"] = FIXTURE_DATASET_ID
    dataset_version: Literal["1.0.0"] = "1.0.0"
    subset: list[str] | None = Field(default=None, max_length=100)
    categories: list[Literal[
        "detection", "assets", "ocr", "floor_count", "building_use", "positioning",
        "fusion", "matching", "discrepancy", "review", "routing", "latency", "cost",
    ]] | None = None


@router.post("/run")
def run_evaluation(request: EvaluationRunRequest) -> dict:
    """Run only a registered dataset through the offline fixture pipeline adapter."""
    if request.dataset_id != FIXTURE_DATASET_ID:
        raise HTTPException(status_code=404, detail="Evaluation dataset is not registered.")
    try:
        return EvaluationRunner().run(
            dataset_id=request.dataset_id,
            dataset_version=request.dataset_version,
            subset=request.subset,
            categories=request.categories,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

