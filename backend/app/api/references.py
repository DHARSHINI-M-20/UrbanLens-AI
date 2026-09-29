"""Reference-data import and listing APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
import httpx
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.osm_reference_service import OSMReferenceIngestor
from app.services.reference_import_service import normalize_manual_reference_records
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()
_osm_ingestor: OSMReferenceIngestor | None = None


def configure_osm_ingestor(ingestor: OSMReferenceIngestor | None) -> None:
    """Inject a deterministic or explicitly configured Overpass adapter."""
    global _osm_ingestor
    _osm_ingestor = ingestor


class ReferenceImportInput(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    source: str = Field(default="participant_generated_demo")
    source_type: str = Field(default="participant_generated_demo")


@router.get("")
def list_references(dataset_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    try:
        query = {"study_area_id": STUDY_AREA_ID}
        if dataset_id:
            query["dataset_id"] = dataset_id
        items = list(get_collection("reference_records").find(query))
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return [{k: v for k, v in item.items() if k != "_id"} for item in items]


@router.post("/import")
def import_references(payload: ReferenceImportInput) -> dict[str, Any]:
    records, excluded = normalize_manual_reference_records(
        payload.records,
        source=payload.source,
        source_type=payload.source_type,
    )
    try:
        if records:
            get_collection("reference_records").insert_many(records)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {
        "imported": len(records),
        "excluded_outside_or_invalid": excluded,
        "source": payload.source,
        "source_type": payload.source_type,
    }


@router.post("/ingest/osm")
def ingest_osm_references() -> dict[str, Any]:
    """Fetch public OSM context and persist it separately with incomplete coverage metadata."""
    ingestor = _osm_ingestor or OSMReferenceIngestor()
    try:
        records, coverage = ingestor.ingest()
        collection = get_collection("reference_records")
        for record in records:
            collection.replace_one({"reference_id": record["reference_id"]}, record, upsert=True)
        get_collection("reference_ingestion_runs").insert_one(coverage)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Public Overpass request failed: {exc}") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"OSM response could not be normalized: {exc}") from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
    return {
        "imported": len(records),
        "source": "OpenStreetMap",
        "source_type": "public_osm",
        "coverage": coverage,
        "absence_is_evidence": False,
    }
