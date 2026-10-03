"""Explicit seed/reset/process endpoints for the isolated demo dataset."""

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import Query
from pymongo.errors import PyMongoError

from app.services.demo_service import demo_status, reset_demo_dataset, run_demo_dataset, seed_demo_dataset
from app.database.mongodb import get_collection
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


def _call(operation):
    try:
        return operation()
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    except (RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/status")
def get_demo_status() -> dict[str, Any]:
    return _call(demo_status)


@router.post("/seed")
def seed_demo(confirm: bool = Query(default=False)) -> dict[str, Any]:
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to replace the fixed simulated demo dataset.")
    return _call(seed_demo_dataset)


@router.post("/process")
def process_demo() -> dict[str, Any]:
    return _call(run_demo_dataset)


@router.delete("/reset")
def reset_demo(confirm: bool = Query(default=False)) -> dict[str, Any]:
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to delete the fixed simulated demo dataset.")
    return _call(reset_demo_dataset)


@router.get("/runs")
def demo_runs(dataset_id: str = Query(default="tn_study_area_demo_v1")) -> list[dict[str, Any]]:
    if dataset_id != "tn_study_area_demo_v1":
        raise HTTPException(status_code=422, detail="Unsupported demo dataset.")
    try:
        runs = list(get_collection("processing_runs").find({
            "dataset_id": dataset_id, "study_area_id": STUDY_AREA_ID,
        }).sort("started_at", -1).limit(100))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{key: value for key, value in item.items() if key != "_id"} for item in runs]
