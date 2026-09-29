"""Explicit seed/reset/process endpoints for the isolated demo dataset."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from app.services.demo_service import demo_status, reset_demo_dataset, run_demo_dataset, seed_demo_dataset

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
def seed_demo() -> dict[str, Any]:
    return _call(seed_demo_dataset)


@router.post("/process")
def process_demo() -> dict[str, Any]:
    return _call(run_demo_dataset)


@router.delete("/reset")
def reset_demo() -> dict[str, Any]:
    return _call(reset_demo_dataset)
