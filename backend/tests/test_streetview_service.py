from __future__ import annotations

import pytest

from app.services import streetview_service
from app.services.streetview_service import (
    MockStreetViewProvider,
    PanoramaNormalizationError,
    StreetViewProviderError,
    normalize_panorama_metadata,
)


@pytest.fixture
def in_boundary(monkeypatch):
    monkeypatch.setattr(streetview_service, "contains_point", lambda latitude, longitude: True)


def test_normalizes_successful_provider_response(in_boundary):
    panorama = normalize_panorama_metadata(
        {
            "pano_id": "provider-pano-1",
            "lat": 11.032,
            "lng": 76.981,
            "date": "2026-09-24T10:30:00",
            "headings": [0, 180],
            "pitch": 0,
            "field_of_view": 90,
        },
        source="approved_provider_fixture",
    )

    assert panorama.panorama_id == "provider-pano-1"
    assert panorama.source == "approved_provider_fixture"
    assert panorama.available_headings == [0.0, 180.0]
    assert panorama.available_view_metadata == {"pitch": 0.0, "field_of_view": 90.0}


def test_rejects_malformed_provider_response(in_boundary):
    with pytest.raises(PanoramaNormalizationError, match="must be an object"):
        normalize_panorama_metadata({"panorama": []}, source="fixture")


def test_rejects_missing_panorama_reference(in_boundary):
    with pytest.raises(PanoramaNormalizationError, match="panorama reference"):
        normalize_panorama_metadata({"latitude": 11.032, "longitude": 76.981}, source="fixture")


def test_rejects_panorama_outside_official_study_area(monkeypatch):
    monkeypatch.setattr(streetview_service, "contains_point", lambda latitude, longitude: False)
    with pytest.raises(PanoramaNormalizationError, match="outside the official study area"):
        normalize_panorama_metadata(
            {"panorama_id": "provider-pano-1", "latitude": 11.032, "longitude": 76.981},
            source="fixture",
        )


def test_accepts_in_boundary_panorama(in_boundary):
    panorama = normalize_panorama_metadata(
        {"panorama_id": "provider-pano-1", "latitude": 11.032, "longitude": 76.981},
        source="fixture",
    )
    assert panorama.study_area_id == "challenge_study_area"


def test_missing_orientation_metadata_remains_unavailable(in_boundary):
    panorama = normalize_panorama_metadata(
        {"panorama_id": "p-no-orientation", "latitude": 11.032, "longitude": 76.981},
        source="fixture",
    )
    assert panorama.available_headings == []
    assert panorama.available_view_metadata == {}


def test_normalizes_provider_singular_heading_and_preserves_camera_values(in_boundary):
    panorama = normalize_panorama_metadata(
        {"panorama_id": "p-oriented", "latitude": 11.032, "longitude": 76.981,
         "heading": 271.5, "pitch": -4.5, "field_of_view": 72},
        source="fixture",
    )
    assert panorama.available_headings == [271.5]
    assert panorama.available_view_metadata == {"pitch": -4.5, "field_of_view": 72.0}


def test_rejects_invalid_heading(in_boundary):
    with pytest.raises(PanoramaNormalizationError, match="Heading"):
        normalize_panorama_metadata(
            {"panorama_id": "p1", "latitude": 11.032, "longitude": 76.981, "headings": [361]},
            source="fixture",
        )


def test_rejects_invalid_pitch(in_boundary):
    with pytest.raises(PanoramaNormalizationError, match="pitch"):
        normalize_panorama_metadata(
            {"panorama_id": "p1", "latitude": 11.032, "longitude": 76.981, "pitch": 91},
            source="fixture",
        )


def test_rejects_invalid_field_of_view(in_boundary):
    with pytest.raises(PanoramaNormalizationError, match="field_of_view"):
        normalize_panorama_metadata(
            {"panorama_id": "p1", "latitude": 11.032, "longitude": 76.981, "field_of_view": 181},
            source="fixture",
        )


def test_mock_provider_reports_provider_failure():
    provider = MockStreetViewProvider(error=RuntimeError("provider unavailable"))
    with pytest.raises(StreetViewProviderError, match="provider unavailable"):
        provider.discover_metadata(latitude=11.032, longitude=76.981, radius_meters=50)


def test_mock_provider_does_not_download_images(in_boundary):
    provider = MockStreetViewProvider(
        response={"panorama_id": "p1", "latitude": 11.032, "longitude": 76.981}
    )
    response = provider.discover_metadata(latitude=11.032, longitude=76.981, radius_meters=50)
    panorama = normalize_panorama_metadata(response, source="fixture")
    assert "image" not in response
    assert panorama.panorama_id == "p1"