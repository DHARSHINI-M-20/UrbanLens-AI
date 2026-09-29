"""Reference matching routes for stored observations and configured datasets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection
from app.services.reference_matching_service import (
	ReferenceDataAdapter,
	StaticReferenceProvider,
	match_observation,
)
from app.services.study_area_service import STUDY_AREA_ID

router = APIRouter()


class MatchRequest(BaseModel):
	observation_ids: list[str] | None = Field(default=None)


def _public(item: dict[str, Any]) -> dict[str, Any]:
	item = dict(item)
	item.pop("_id", None)
	return item


@router.post("/run")
def run_matching(payload: MatchRequest | None = None) -> dict[str, Any]:
	payload = payload or MatchRequest()
	try:
		query: dict[str, Any] = {"study_area_id": STUDY_AREA_ID}
		if payload.observation_ids:
			query["observation_id"] = {"$in": payload.observation_ids}
		observations = list(get_collection("observations").find(query))
		references = list(get_collection("reference_records").find({"study_area_id": STUDY_AREA_ID}))
		source_groups: dict[str, list[dict[str, Any]]] = {}
		for reference in references:
			source = str(reference.get("reference_source") or reference.get("source_type") or reference.get("source") or "unspecified")
			source_groups.setdefault(source, []).append(reference)
		adapter = ReferenceDataAdapter([
			StaticReferenceProvider(source, records) for source, records in source_groups.items()
		])
		matches = []
		now = datetime.now(timezone.utc).isoformat()
		for observation in observations:
			result = match_observation(observation, adapter)
			result.update({"study_area_id": STUDY_AREA_ID, "created_at": now})
			get_collection("matches").replace_one({"observation_id": observation.get("observation_id")}, result, upsert=True)
			get_collection("observations").update_one(
				{"observation_id": observation.get("observation_id"), "study_area_id": STUDY_AREA_ID},
				{"$set": {"match_status": result["match_status"], "match_record": result,
						  "reference_id": result["matched_reference_id"]}},
			)
			matches.append(result)
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
	return {"processed": len(matches), "matches": matches}


@router.get("")
def list_matches(dataset_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
	try:
		query = {"study_area_id": STUDY_AREA_ID}
		if dataset_id:
			query["dataset_id"] = dataset_id
		items = list(get_collection("matches").find(query).limit(1000))
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
	return [_public(item) for item in items]
