"""Metadata-only panorama discovery through an injected approved provider."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.database.mongodb import get_collection, with_location
from app.services.streetview_service import (
	PanoramaNormalizationError,
	StreetViewProvider,
	StreetViewProviderError,
	normalize_panorama_metadata,
)
from app.services.study_area_service import STUDY_AREA_ID, contains_point

router = APIRouter()
_provider: StreetViewProvider | None = None


def configure_provider(provider: StreetViewProvider | None) -> None:
	"""Install an approved provider adapter at application startup or in tests."""
	global _provider
	_provider = provider


class PanoramaDiscoveryInput(BaseModel):
	latitude: float = Field(ge=-90, le=90)
	longitude: float = Field(ge=-180, le=180)
	radius_meters: int = Field(default=50, ge=1, le=5000)


def _public(item: dict[str, Any]) -> dict[str, Any]:
	item = dict(item)
	item.pop("_id", None)
	item.pop("location", None)
	return item


@router.post("/discover")
def discover_panorama(payload: PanoramaDiscoveryInput) -> dict[str, Any]:
	"""Request provider metadata only; imagery is never scraped or downloaded here."""
	if not contains_point(payload.latitude, payload.longitude):
		raise HTTPException(status_code=422, detail="Discovery point is outside the official study area.")
	if _provider is None:
		raise HTTPException(status_code=503, detail="No authorized Street View provider is configured.")
	try:
		response = _provider.discover_metadata(
			latitude=payload.latitude,
			longitude=payload.longitude,
			radius_meters=payload.radius_meters,
		)
		source = getattr(_provider, "source_name", None) or getattr(_provider, "name", None)
		if source is None:
			source = "mock_fixture" if _provider.__class__.__name__ == "MockStreetViewProvider" else _provider.__class__.__name__
		panorama = normalize_panorama_metadata(response, source=str(source), study_area_id=STUDY_AREA_ID)
	except PanoramaNormalizationError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	except StreetViewProviderError as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc
	try:
		document = with_location(panorama.model_dump(mode="python"))
		get_collection("panoramas").replace_one({"panorama_id": panorama.panorama_id}, document, upsert=True)
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
	return panorama.model_dump(mode="json")


@router.get("")
def list_panoramas() -> list[dict[str, Any]]:
	try:
		items = list(get_collection("panoramas").find({"study_area_id": STUDY_AREA_ID}).limit(500))
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
	return [_public(item) for item in items]


@router.get("/{panorama_id}")
def get_panorama(panorama_id: str) -> dict[str, Any]:
	try:
		item = get_collection("panoramas").find_one({"panorama_id": panorama_id, "study_area_id": STUDY_AREA_ID})
	except PyMongoError as exc:
		raise HTTPException(status_code=503, detail="MongoDB is not reachable.") from exc
	if item is None:
		raise HTTPException(status_code=404, detail="Panorama not found.")
	return _public(item)
