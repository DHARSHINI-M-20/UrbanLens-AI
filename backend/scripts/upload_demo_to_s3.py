"""Upload a seeded simulated Task 5 dataset to the configured S3 bucket."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from typing import Any

from bson import json_util
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from app.database.mongodb import check_connection, get_collection
from app.services.demo_service import (
    DEMO_DATASET_ID,
    DEMO_SOURCE,
    REFERENCE_SOURCE,
    _synthetic_png,
)
from app.services.s3_storage_service import S3StorageService
from app.services.simulated_streetview_provider import SIMULATION_LABEL
from app.services.study_area_service import STUDY_AREA_FILE

COLLECTION_ARTIFACTS = (
    ("streets", "streets/streets.json", DEMO_SOURCE),
    ("sampling_points", "assets/sampling_points.json", DEMO_SOURCE),
    ("panoramas", "panoramas/panoramas.json", DEMO_SOURCE),
    ("views", "views/views.json", DEMO_SOURCE),
    ("reference_records", "references/reference_records.json", REFERENCE_SOURCE),
    ("observations", "observations/observations.json", DEMO_SOURCE),
    ("ocr_observations", "ocr/ocr_observations.json", DEMO_SOURCE),
    ("unified_entities", "assets/unified_entities.json", DEMO_SOURCE),
    ("matches", "assets/matches.json", DEMO_SOURCE),
    ("discrepancies", "assets/discrepancies.json", DEMO_SOURCE),
    ("review_queue", "reviews/review_queue.json", DEMO_SOURCE),
    ("processing_metrics", "metadata/processing_metrics.json", DEMO_SOURCE),
)


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "_id"}


def upload_demo_dataset(*, service: S3StorageService | None = None) -> dict[str, Any]:
    if not check_connection():
        raise RuntimeError("MongoDB is unavailable; seed the local simulated dataset before uploading.")
    if not STUDY_AREA_FILE.is_file():
        raise FileNotFoundError(f"Official study-area boundary not found: {STUDY_AREA_FILE}")

    dataset = get_collection("demo_datasets").find_one({"dataset_id": DEMO_DATASET_ID})
    if dataset is None or dataset.get("simulation") is not True:
        raise RuntimeError(f"Simulated dataset {DEMO_DATASET_ID} is not seeded in MongoDB.")

    storage = service or S3StorageService()
    manifest_key = storage.dataset_key(DEMO_DATASET_ID, "metadata", "manifest.json")
    prior_manifest = None
    if storage.object_exists(manifest_key):
        prior_manifest = json_util.loads(storage.get_object(manifest_key))

    object_entries = []
    uploaded_count = 0
    unchanged_count = 0

    boundary_key = storage.dataset_key(DEMO_DATASET_ID, "study_area", "Study_area.geojson")
    boundary_result = storage.upload_file(
        STUDY_AREA_FILE,
        boundary_key,
        dataset_id=DEMO_DATASET_ID,
        source="OFFICIAL_STUDY_AREA_BOUNDARY",
        simulation=False,
        content_type="application/geo+json",
    )
    uploaded_count += int(boundary_result["uploaded"])
    unchanged_count += int(not boundary_result["uploaded"])
    object_entries.append({
        "key": boundary_key,
        "category": "study_area",
        "content_type": "application/geo+json",
        "size": boundary_result["size"],
        "sha256": boundary_result["sha256"],
        "source": "OFFICIAL_STUDY_AREA_BOUNDARY",
        "simulation": False,
        "provenance": "Official challenge boundary; authoritative geometry only.",
    })

    for collection_name, relative_key, source in COLLECTION_ARTIFACTS:
        records = [
            _public_document(item)
            for item in get_collection(collection_name).find({"dataset_id": DEMO_DATASET_ID})
        ]
        if not records:
            continue
        key = storage.dataset_key(DEMO_DATASET_ID, *relative_key.split("/"))
        artifact = {
            "dataset_id": DEMO_DATASET_ID,
            "simulation": True,
            "source": source,
            "reference_source": REFERENCE_SOURCE,
            "study_area_source": "data/Study_Area/Study_area.geojson",
            "provenance": SIMULATION_LABEL,
            "real_google_street_view": False,
            "record_count": len(records),
            "records": records,
        }
        result = storage.upload_json(
            key,
            artifact,
            dataset_id=DEMO_DATASET_ID,
            source=source,
            simulation=True,
        )
        uploaded_count += int(result["uploaded"])
        unchanged_count += int(not result["uploaded"])
        object_entries.append({
            "key": key,
            "category": collection_name,
            "content_type": "application/json",
            "size": result["size"],
            "sha256": result["sha256"],
            "record_count": len(records),
            "source": source,
            "reference_source": REFERENCE_SOURCE,
            "simulation": True,
            "provenance": SIMULATION_LABEL,
        })

    for view in get_collection("views").find({"dataset_id": DEMO_DATASET_ID}):
        view_id = str(view["view_id"])
        image_key = storage.dataset_key(DEMO_DATASET_ID, "evidence", f"{view_id}.png")
        image_bytes = _synthetic_png(view_id)
        result = storage.upload_bytes(
            image_key,
            image_bytes,
            dataset_id=DEMO_DATASET_ID,
            source=DEMO_SOURCE,
            simulation=True,
            content_type="image/png",
        )
        uploaded_count += int(result["uploaded"])
        unchanged_count += int(not result["uploaded"])
        object_entries.append({
            "key": image_key,
            "category": "synthetic_evidence",
            "content_type": "image/png",
            "size": result["size"],
            "sha256": result["sha256"],
            "view_id": view_id,
            "source": DEMO_SOURCE,
            "simulation": True,
            "provenance": SIMULATION_LABEL,
            "real_google_street_view": False,
        })

    manifest = {
        "dataset_id": DEMO_DATASET_ID,
        "dataset_type": DEMO_SOURCE,
        "reference_source": REFERENCE_SOURCE,
        "study_area_source": "data/Study_Area/Study_area.geojson",
        "study_area_provenance": "Official challenge boundary; authoritative geometry only.",
        "simulation": True,
        "real_google_street_view": False,
        "label": SIMULATION_LABEL,
        "created_at": (prior_manifest or {}).get("created_at") or datetime.now(timezone.utc).isoformat(),
        "objects": object_entries,
    }
    manifest_result = storage.upload_json(
        manifest_key,
        manifest,
        dataset_id=DEMO_DATASET_ID,
        source=DEMO_SOURCE,
        simulation=True,
    )
    uploaded_count += int(manifest_result["uploaded"])
    unchanged_count += int(not manifest_result["uploaded"])
    return {
        "bucket": storage.bucket,
        "dataset_id": DEMO_DATASET_ID,
        "prefix": storage.dataset_key(DEMO_DATASET_ID) + "/",
        "manifest_key": manifest_key,
        "objects": len(object_entries) + 1,
        "uploaded": uploaded_count,
        "unchanged": unchanged_count,
        "record_counts": {name: entry.get("record_count", 0) for name, entry in ((item["category"], item) for item in object_entries) if "record_count" in entry},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", help="Override the configured UrbanLens bucket.")
    args = parser.parse_args()
    try:
        service = S3StorageService(bucket=args.bucket) if args.bucket else S3StorageService()
        summary = upload_demo_dataset(service=service)
        print(json.dumps(summary, indent=2, sort_keys=True))
        print(json.dumps({
            "lambda_event": {
                "dataset_id": DEMO_DATASET_ID,
                "bucket": service.bucket,
                "key": service.dataset_key(DEMO_DATASET_ID, "observations", "observations.json"),
            }
        }, indent=2, sort_keys=True))
        return 0
    except (ClientError, NoCredentialsError, PartialCredentialsError, RuntimeError, ValueError, OSError) as exc:
        print(f"Upload failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())