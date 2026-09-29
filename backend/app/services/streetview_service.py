"""Provider contract and safe metadata normalization for Street View access.

This module intentionally contains no Google client or network implementation.
The real provider must be added only after an authorized API configuration is
available and approved.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from app.models.panorama import Panorama
from app.services.study_area_service import STUDY_AREA_ID, contains_point


class StreetViewProviderError(RuntimeError):
	"""Raised when a configured Street View provider cannot return metadata."""


class PanoramaNormalizationError(ValueError):
	"""Raised when provider metadata cannot be safely normalized."""


class StreetViewProvider(Protocol):
	"""Metadata-only contract for an approved Street View provider."""

	def discover_metadata(self, *, latitude: float, longitude: float, radius_meters: int) -> Mapping[str, Any]:
		"""Return one provider metadata response without downloading imagery."""


class MockStreetViewProvider:
	"""Deterministic provider used by unit tests without network access."""

	def __init__(self, response: Mapping[str, Any] | None = None, error: Exception | None = None) -> None:
		self.response = response
		self.error = error

	def discover_metadata(self, *, latitude: float, longitude: float, radius_meters: int) -> Mapping[str, Any]:
		if self.error is not None:
			raise StreetViewProviderError(str(self.error)) from self.error
		if self.response is None:
			raise StreetViewProviderError("Mock provider has no metadata response.")
		return self.response


def _required_text(value: Any, field_name: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise PanoramaNormalizationError(f"Provider response is missing a valid {field_name}.")
	return value.strip()


def _coordinate(metadata: Mapping[str, Any], *names: str) -> float:
	for name in names:
		if name in metadata and metadata[name] is not None:
			try:
				return float(metadata[name])
			except (TypeError, ValueError) as exc:
				raise PanoramaNormalizationError(f"Provider response has an invalid {name}.") from exc
	raise PanoramaNormalizationError(f"Provider response is missing {names[0]}.")


def _validated_heading(value: Any) -> float:
	try:
		heading = float(value)
	except (TypeError, ValueError) as exc:
		raise PanoramaNormalizationError("Provider response has an invalid heading.") from exc
	if not 0 <= heading <= 360:
		raise PanoramaNormalizationError("Heading must be between 0 and 360 degrees.")
	return heading


def _validated_view_value(value: Any, field_name: str, lower: float, upper: float) -> float:
	try:
		result = float(value)
	except (TypeError, ValueError) as exc:
		raise PanoramaNormalizationError(f"Provider response has an invalid {field_name}.") from exc
	if not lower <= result <= upper:
		raise PanoramaNormalizationError(f"{field_name} must be between {lower} and {upper}.")
	return result


def normalize_panorama_metadata(
	response: Mapping[str, Any],
	*,
	source: str,
	study_area_id: str = STUDY_AREA_ID,
) -> Panorama:
	"""Normalize one provider response and reject unsafe or incomplete data."""
	if not isinstance(response, Mapping):
		raise PanoramaNormalizationError("Provider response must be an object.")

	metadata = response.get("panorama", response)
	if not isinstance(metadata, Mapping):
		raise PanoramaNormalizationError("Provider panorama metadata must be an object.")

	panorama_id = _required_text(
		metadata.get("panorama_id") or metadata.get("pano_id") or metadata.get("panorama_reference"),
		"panorama reference",
	)
	latitude = _coordinate(metadata, "latitude", "lat")
	longitude = _coordinate(metadata, "longitude", "lng", "lon")
	if not contains_point(latitude, longitude):
		raise PanoramaNormalizationError("Provider panorama is outside the official study area.")

	raw_headings = metadata.get("available_headings", metadata.get("headings", []))
	if raw_headings is None:
		raw_headings = []
	if not raw_headings and metadata.get("heading") is not None:
		raw_headings = [metadata["heading"]]
	if isinstance(raw_headings, (str, bytes)) or not isinstance(raw_headings, Sequence):
		raise PanoramaNormalizationError("Provider headings must be a list.")
	headings = [_validated_heading(value) for value in raw_headings]

	available_view_metadata: dict[str, Any] = {}
	if "pitch" in metadata:
		available_view_metadata["pitch"] = _validated_view_value(metadata["pitch"], "pitch", -90, 90)
	if "field_of_view" in metadata:
		available_view_metadata["field_of_view"] = _validated_view_value(
			metadata["field_of_view"], "field_of_view", 0.000001, 180
		)

	captured_at: datetime | None = None
	raw_capture_date = metadata.get("captured_at", metadata.get("capture_date", metadata.get("date")))
	if raw_capture_date is not None:
		try:
			captured_at = raw_capture_date if isinstance(raw_capture_date, datetime) else datetime.fromisoformat(str(raw_capture_date))
		except ValueError as exc:
			raise PanoramaNormalizationError("Provider response has an invalid capture date.") from exc

	return Panorama(
		panorama_id=panorama_id,
		panorama_reference=panorama_id,
		latitude=latitude,
		longitude=longitude,
		captured_at=captured_at,
		source=_required_text(source, "provider source"),
		study_area_id=study_area_id,
		available_headings=headings,
		available_view_metadata=available_view_metadata,
		evidence_reference=metadata.get("evidence_reference"),
	)
