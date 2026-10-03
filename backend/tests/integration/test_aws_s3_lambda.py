from __future__ import annotations

import json
import os
import uuid

import boto3
import pytest

from app.config import get_settings
from app.services.demo_service import DEMO_DATASET_ID, DEMO_SOURCE
from app.services.dynamodb_service import DynamoDBService
from app.services.s3_storage_service import S3StorageService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("URBANLENS_AWS_INTEGRATION") != "1", reason="Real AWS integration is opt-in."),
]


def test_real_s3_to_lambda_round_trip_cleans_only_its_test_object():
    settings = get_settings()
    if not settings.urbanlens_s3_bucket or not settings.urbanlens_lambda_function:
        pytest.skip("Configure the UrbanLens S3 bucket and Lambda function before running this opt-in test.")
    storage = S3StorageService()
    key = storage.dataset_key(
        DEMO_DATASET_ID,
        "metadata",
        "integration-tests",
        f"round-trip-{uuid.uuid4().hex}.json",
    )
    payload = {
        "dataset_id": DEMO_DATASET_ID,
        "simulation": True,
        "source": DEMO_SOURCE,
        "real_google_street_view": False,
        "records": [{
            "observation_id": f"aws-integration-{uuid.uuid4().hex}",
            "dataset_id": DEMO_DATASET_ID,
            "asset_type": "building",
            "confidence": 0.95,
            "attributes": {"building_use": "commercial", "visible_floor_count": 3},
            "simulation": True,
            "source": DEMO_SOURCE,
        }],
    }
    upload = storage.upload_json(
        key,
        payload,
        dataset_id=DEMO_DATASET_ID,
        source=DEMO_SOURCE,
        simulation=True,
    )
    assert upload["uploaded"]
    test_record = payload["records"][0]
    dynamodb = DynamoDBService()
    result = None
    try:
        session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
        response = session.client("lambda").invoke(
            FunctionName=settings.urbanlens_lambda_function,
            InvocationType="RequestResponse",
            Payload=json.dumps({"dataset_id": DEMO_DATASET_ID, "bucket": storage.bucket, "key": key}).encode("utf-8"),
        )
        result = json.loads(response["Payload"].read())
        assert response.get("FunctionError") is None
        assert result["status"] == "success"
        assert result["dataset_id"] == DEMO_DATASET_ID
        assert result["source"] == DEMO_SOURCE
        assert result["simulation"] is True
        assert result["processing_time_ms"] >= 0
        assert result["dynamodb"]["status"] == "success"
        stored_observation = next(
            item for item in dynamodb.get_records(DEMO_DATASET_ID, collection="observations")
            if item.get("observation_id") == test_record["observation_id"]
        )
        assert stored_observation["provenance"]
        stored_run = next(
            item for item in dynamodb.get_records(DEMO_DATASET_ID, collection="processing_metrics")
            if item.get("processing_id") == result["processing_id"]
        )
        assert stored_run["simulation"] is True
    finally:
        storage.delete_object(key)
        dynamodb.delete_record(DEMO_DATASET_ID, "observations", test_record)
        if result and result.get("processing_id"):
            dynamodb.delete_record(DEMO_DATASET_ID, "processing_metrics", {
                "dataset_id": DEMO_DATASET_ID,
                "processing_id": result["processing_id"],
            })
    assert storage.object_exists(key) is False