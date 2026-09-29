from __future__ import annotations

from app.services.reference_import_service import normalize_manual_reference_records
from app.services.study_area_service import STUDY_AREA_ID


def test_manual_reference_import_keeps_inside_record_and_source_provenance():
    accepted, excluded = normalize_manual_reference_records(
        [{
            "reference_id": "farmwise-fixture-1",
            "record_type": "building",
            "latitude": 11.032,
            "longitude": 76.98,
            "source": "partner_property_export",
            "source_type": "farmwise_internal",
            "partner_version": "fixture-2026-09",
        }],
        source="request-default-source",
        source_type="participant_generated_demo",
    )
    assert excluded == 0
    assert len(accepted) == 1
    assert accepted[0]["reference_id"] == "farmwise-fixture-1"
    assert accepted[0]["source"] == "partner_property_export"
    assert accepted[0]["reference_source"] == "partner_property_export"
    assert accepted[0]["source_type"] == "farmwise_internal"
    assert accepted[0]["partner_version"] == "fixture-2026-09"
    assert accepted[0]["study_area_id"] == STUDY_AREA_ID
    assert accepted[0]["geometry"]["type"] == "Point"


def test_manual_reference_import_excludes_outside_record():
    accepted, excluded = normalize_manual_reference_records(
        [{
            "reference_id": "outside-fixture",
            "record_type": "building",
            "latitude": 12.0,
            "longitude": 77.0,
            "source": "public_fixture",
            "source_type": "public",
        }],
        source="fallback",
        source_type="demo",
    )
    assert accepted == []
    assert excluded == 1


def test_manual_reference_import_clips_crossing_geometry_to_official_area():
    accepted, excluded = normalize_manual_reference_records(
        [{
            "reference_id": "crossing-fixture",
            "record_type": "building",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76.97, 11.032], [76.98, 11.032], [76.98, 11.033],
                                 [76.97, 11.033], [76.97, 11.032]]],
            },
            "source": "public_fixture",
            "source_type": "public",
        }],
        source="fallback",
        source_type="demo",
    )
    assert excluded == 0
    assert len(accepted) == 1
    assert accepted[0]["geometry"] != accepted[0]["source_geometry"]
    assert accepted[0]["source"] == "public_fixture"
