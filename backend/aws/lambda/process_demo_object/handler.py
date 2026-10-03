"""Validate and summarize one simulated JSON artifact stored in S3."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import boto3

DATASET_ID = "tn_study_area_demo_v1"
SIMULATED_SOURCES = {"SIMULATED_TAMIL_NADU_DATA", "SIMULATED_PROPERTY_REGISTER"}
DEFAULT_REGION = "ap-south-1"
_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=os.getenv("AWS_REGION", DEFAULT_REGION))
    return _s3_client


def handler(event: dict[str, Any], context: Any, *, s3_client: Any | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    if not isinstance(event, dict) or event.get("dataset_id") != DATASET_ID:
        raise ValueError(f"dataset_id must be {DATASET_ID}.")

    bucket = event.get("bucket")
    key = event.get("key")
    configured_bucket = os.getenv("URBANLENS_S3_BUCKET")
    prefix = os.getenv("URBANLENS_S3_PREFIX", "urbanlens/datasets").strip("/")
    if not isinstance(bucket, str) or not bucket or (configured_bucket and bucket != configured_bucket):
        raise ValueError("bucket must match the configured UrbanLens S3 bucket.")
    expected_key_prefix = f"{prefix}/{DATASET_ID}/"
    if not isinstance(key, str) or not key.startswith(expected_key_prefix) or ".." in key.split("/") or "\\" in key:
        raise ValueError("key must be under the configured dataset prefix.")

    response = (s3_client or _get_s3_client()).get_object(Bucket=bucket, Key=key)
    metadata = {str(name).lower(): str(value) for name, value in response.get("Metadata", {}).items()}
    source = metadata.get("source")
    if metadata.get("dataset_id") != DATASET_ID or metadata.get("simulation") != "true":
        raise ValueError("S3 object metadata does not identify this simulated dataset.")
    if source not in SIMULATED_SOURCES:
        raise ValueError("S3 object provenance source is not an approved simulated source.")

    body = response["Body"]
    try:
        raw = body.read()
    finally:
        body.close()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("dataset_id") != DATASET_ID:
        raise ValueError("S3 JSON payload must identify the expected dataset.")
    if payload.get("simulation") is not True or payload.get("source") != source:
        raise ValueError("S3 JSON payload provenance does not match its S3 metadata.")
    if payload.get("real_google_street_view") is True:
        raise ValueError("The simulated dataset cannot claim real Google Street View imagery.")

    records = payload.get("records")
    record_count = len(records) if isinstance(records, list) else 1
    return {
        "status": "success",
        "dataset_id": DATASET_ID,
        "simulation": True,
        "source": source,
        "bucket": bucket,
        "key": key,
        "processed_object": key,
        "record_count": record_count,
        "object_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
        "message": "Validated simulated JSON metadata; no computer vision was performed.",
        "provenance": {
            "dataset_id": metadata["dataset_id"],
            "source": source,
            "simulation": True,
            "real_google_street_view": False,
        },
    }