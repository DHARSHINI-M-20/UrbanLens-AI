from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
from fastapi.testclient import TestClient

from botocore.exceptions import ClientError
import pytest

from app.config import get_settings
from app.main import app
from app.services.s3_storage_service import S3ConfigurationError, S3StorageService

LAMBDA_HANDLER_PATH = Path(__file__).parents[1] / "aws" / "lambda" / "process_demo_object" / "handler.py"
SPEC = importlib.util.spec_from_file_location("urbanlens_demo_lambda_handler", LAMBDA_HANDLER_PATH)
assert SPEC and SPEC.loader
lambda_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lambda_module)
LAMBDA_DIR = LAMBDA_HANDLER_PATH.parent
sys.path.insert(0, str(LAMBDA_DIR))
try:
    import cloud_api as cloud_lambda
finally:
    sys.path.remove(str(LAMBDA_DIR))


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.put_calls = []

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadObject")
        return self.objects[(Bucket, Key)]["head"]

    def put_object(self, **request):
        self.put_calls.append(request)
        self.objects[(request["Bucket"], request["Key"])] = {
            "body": request["Body"],
            "head": {
                "ContentLength": len(request["Body"]),
                "ContentType": request["ContentType"],
                "Metadata": request["Metadata"],
            },
        }

    def upload_file(self, filename, bucket, key, *, ExtraArgs):
        data = Path(filename).read_bytes()
        self.objects[(bucket, key)] = {
            "body": data,
            "head": {
                "ContentLength": len(data),
                "ContentType": ExtraArgs["ContentType"],
                "Metadata": ExtraArgs["Metadata"],
            },
        }

    def get_object(self, *, Bucket, Key):
        item = self.objects[(Bucket, Key)]
        return {"Body": io.BytesIO(item["body"]), "Metadata": item["head"]["Metadata"]}


class FakeCloudS3:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")
        self.image = b"\x89PNG\r\n\x1a\nsynthetic"

    def get_object(self, *, Bucket, Key):
        if Key.endswith(".png"):
            return {
                "Body": io.BytesIO(self.image),
                "Metadata": {"dataset_id": "tn_study_area_demo_v1", "source": "SIMULATED_TAMIL_NADU_DATA", "simulation": "true"},
            }
        return {
            "Body": io.BytesIO(self.payload),
            "Metadata": {"dataset_id": "tn_study_area_demo_v1", "source": "SIMULATED_TAMIL_NADU_DATA", "simulation": "true"},
        }


class FakeCloudDynamoDB:
    def __init__(self):
        self.records = {}
        self.writes = []

    def get_records(self, dataset_id, *, collection=None, street_id=None):
        rows = self.records.get(collection, [])
        if street_id:
            rows = [row for row in rows if row.get("street_id") == street_id]
        return rows

    def put_records(self, dataset_id, collection, records):
        self.writes.append((dataset_id, collection, records))
        existing = {row.get("observation_id", row.get("processing_id")): row for row in self.records.get(collection, [])}
        existing.update({row.get("observation_id", row.get("processing_id")): row for row in records})
        self.records[collection] = list(existing.values())
        return len(records)

    def get_status(self):
        return {"configured": True, "table": "fai-tce-team11-urbanlens-records", "exists": True, "status": "ACTIVE", "item_count": 0}


class FakeNovaRuntime:
    def __init__(self):
        self.calls = []

    def converse(self, **request):
        self.calls.append(request)
        return {"output": {"message": {"content": [{"text": '{"building_use":"commercial","visible_floor_count":3,"confidence":0.82,"uncertainty_indicators":[],"reasoning_summary":"synthetic test"}'}]}}}


def test_aws_configuration_reads_optional_profile_and_resource_settings(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "farmwiseai")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "fai-tce-team11-streetview")
    monkeypatch.setenv("URBANLENS_S3_PREFIX", "urbanlens/datasets")
    monkeypatch.setenv("URBANLENS_LAMBDA_FUNCTION", "fai-tce-team11-urbanlens-demo-processor")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.aws_profile == "farmwiseai"
    assert settings.aws_region == "ap-south-1"
    assert settings.urbanlens_s3_bucket == "fai-tce-team11-streetview"
    assert settings.urbanlens_s3_prefix == "urbanlens/datasets"
    assert settings.urbanlens_lambda_function == "fai-tce-team11-urbanlens-demo-processor"
    get_settings.cache_clear()


def test_s3_configuration_rejects_unapproved_region_and_unsafe_prefix():
    with pytest.raises(S3ConfigurationError, match="restricted"):
        S3StorageService(bucket="bucket", region="us-east-1", client=FakeS3())
    with pytest.raises(S3ConfigurationError, match="safe relative"):
        S3StorageService(bucket="bucket", prefix="../outside", client=FakeS3())


def test_s3_upload_json_is_deterministic_provenance_tagged_and_idempotent():
    fake = FakeS3()
    service = S3StorageService(bucket="bucket", prefix="urbanlens/datasets", client=fake)
    key = service.dataset_key("tn_study_area_demo_v1", "observations", "observations.json")
    payload = {
        "dataset_id": "tn_study_area_demo_v1",
        "simulation": True,
        "source": "SIMULATED_TAMIL_NADU_DATA",
        "records": [{"observation_id": "obs-1"}],
    }
    first = service.upload_json(
        key, payload, dataset_id="tn_study_area_demo_v1",
        source="SIMULATED_TAMIL_NADU_DATA", simulation=True,
    )
    second = service.upload_json(
        key, payload, dataset_id="tn_study_area_demo_v1",
        source="SIMULATED_TAMIL_NADU_DATA", simulation=True,
    )
    assert first["uploaded"] is True
    assert second["uploaded"] is False
    assert len(fake.put_calls) == 1
    assert fake.put_calls[0]["ContentType"] == "application/json"
    assert fake.put_calls[0]["Metadata"]["dataset_id"] == "tn_study_area_demo_v1"
    assert fake.put_calls[0]["Metadata"]["simulation"] == "true"
    assert json.loads(service.get_object(key))["records"][0]["observation_id"] == "obs-1"
    assert service.get_object_metadata(key)["metadata"]["source"] == "SIMULATED_TAMIL_NADU_DATA"


def test_s3_exists_and_upload_are_scoped_to_dataset_prefix():
    service = S3StorageService(bucket="bucket", client=FakeS3())
    key = service.dataset_key("tn_study_area_demo_v1", "metadata", "data.json")
    assert service.object_exists(key) is False
    with pytest.raises(ValueError, match="configured dataset prefix"):
        service.upload_bytes(
            "unrelated/private.json", b"{}", dataset_id="tn_study_area_demo_v1",
            source="SIMULATED_TAMIL_NADU_DATA", simulation=True,
        )


def test_s3_upload_file_preserves_dataset_provenance(tmp_path):
    fake = FakeS3()
    service = S3StorageService(bucket="bucket", client=fake)
    path = tmp_path / "boundary.geojson"
    path.write_text('{"type":"FeatureCollection"}', encoding="utf-8")
    key = service.dataset_key("tn_study_area_demo_v1", "study_area", "Study_area.geojson")
    result = service.upload_file(
        path, key, dataset_id="tn_study_area_demo_v1",
        source="OFFICIAL_STUDY_AREA_BOUNDARY", simulation=False,
        content_type="application/geo+json",
    )
    assert result["uploaded"] is True
    assert fake.objects[("bucket", key)]["head"]["Metadata"]["simulation"] == "false"
    assert service.get_object(key) == path.read_bytes()


def test_aws_status_is_graceful_when_optional_cloud_settings_are_absent(monkeypatch):
    monkeypatch.delenv("URBANLENS_S3_BUCKET", raising=False)
    monkeypatch.delenv("URBANLENS_LAMBDA_FUNCTION", raising=False)
    get_settings.cache_clear()
    response = TestClient(app).get("/aws/status")
    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["s3"]["reachable"] is None
    assert response.json()["lambda"]["exists"] is None
    assert "AWS_ACCESS_KEY_ID" not in response.text


def test_lambda_validates_simulation_provenance_and_returns_structured_result(monkeypatch):
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "bucket")
    monkeypatch.setenv("URBANLENS_S3_PREFIX", "urbanlens/datasets")
    source = "SIMULATED_TAMIL_NADU_DATA"
    payload = {"dataset_id": "tn_study_area_demo_v1", "simulation": True, "source": source, "records": [{}, {}]}
    fake = FakeS3()
    service = S3StorageService(bucket="bucket", client=fake)
    key = service.dataset_key("tn_study_area_demo_v1", "observations", "sample.json")
    service.upload_json(key, payload, dataset_id="tn_study_area_demo_v1", source=source, simulation=True)

    result = lambda_module.handler({"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": key}, None, s3_client=fake)
    assert result["status"] == "success"
    assert result["simulation"] is True
    assert result["source"] == source
    assert result["record_count"] == 2
    assert result["processing_time_ms"] >= 0
    assert result["provenance"]["real_google_street_view"] is False
    assert "no computer vision" in result["message"]


@pytest.mark.parametrize("event", [
    {"dataset_id": "another-dataset", "bucket": "bucket", "key": "urbanlens/datasets/tn_study_area_demo_v1/a.json"},
    {"dataset_id": "tn_study_area_demo_v1", "bucket": "other", "key": "urbanlens/datasets/tn_study_area_demo_v1/a.json"},
    {"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": "unrelated/a.json"},
])
def test_lambda_rejects_invalid_dataset_bucket_or_key(monkeypatch, event):
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "bucket")
    with pytest.raises(ValueError):
        lambda_module.handler(event, None, s3_client=FakeS3())


def test_lambda_rejects_non_simulated_provenance_and_real_google_claim(monkeypatch):
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "bucket")
    fake = FakeS3()
    service = S3StorageService(bucket="bucket", client=fake)
    key = service.dataset_key("tn_study_area_demo_v1", "metadata", "claim.json")
    payload = {
        "dataset_id": "tn_study_area_demo_v1", "simulation": True,
        "source": "SIMULATED_TAMIL_NADU_DATA", "real_google_street_view": True,
    }
    service.upload_json(key, payload, dataset_id="tn_study_area_demo_v1", source=payload["source"], simulation=True)
    with pytest.raises(ValueError, match="cannot claim real Google"):
        lambda_module.handler({"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": key}, None, s3_client=fake)

    wrong_key = service.dataset_key("tn_study_area_demo_v1", "metadata", "wrong-source.json")
    fake.put_object(
        Bucket="bucket", Key=wrong_key, Body=b'{}', ContentType="application/json",
        Metadata={"dataset_id": "tn_study_area_demo_v1", "simulation": "true", "source": "google_street_view"},
    )
    with pytest.raises(ValueError, match="approved simulated source"):
        lambda_module.handler({"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": wrong_key}, None, s3_client=fake)


def _cloud_observation_payload(confidence=0.43):
    return {
        "dataset_id": "tn_study_area_demo_v1",
        "simulation": True,
        "source": "SIMULATED_TAMIL_NADU_DATA",
        "provenance": "SIMULATED TAMIL NADU URBAN DATA - NOT REAL GOOGLE STREET VIEW DATA",
        "real_google_street_view": False,
        "records": [{
            "observation_id": "obs-hard-1",
            "source_view_id": "tn_demo_view_01a",
            "dataset_id": "tn_study_area_demo_v1",
            "asset_type": "building",
            "confidence": confidence,
            "attributes": {"building_use": "commercial", "visible_floor_count": 3},
            "simulation": True,
            "source": "SIMULATED_TAMIL_NADU_DATA",
            "model_route": "small_model",
        }],
    }


def test_cloud_lambda_persists_observations_and_emits_metrics(monkeypatch, capsys, caplog):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "bucket")
    monkeypatch.setenv("URBANLENS_DYNAMODB_TABLE", "fai-tce-team11-urbanlens-records")
    monkeypatch.setenv("URBANLENS_LAMBDA_BEDROCK_ENABLED", "false")
    dynamodb = FakeCloudDynamoDB()
    result = cloud_lambda.handler(
        {"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": "urbanlens/datasets/tn_study_area_demo_v1/observations/observations.json"},
        None,
        s3_client=FakeCloudS3(_cloud_observation_payload()),
        dynamodb_service=dynamodb,
    )
    assert result["status"] == "success"
    assert result["dynamodb"]["writes"] == 2
    assert dynamodb.records["observations"][0]["dataset_id"] == "tn_study_area_demo_v1"
    assert dynamodb.records["observations"][0]["simulation"] is True
    assert dynamodb.records["observations"][0]["aws_service"] == "AWS Lambda"
    assert dynamodb.records["observations"][0]["estimated_cost"] is None
    assert '"event":"s3_object_processed"' in caplog.text
    logs = capsys.readouterr().out
    assert '"ProcessingCount":1' in logs
    assert '"DynamoDBWriteCount":2' in logs


def test_cloud_lambda_escalates_at_most_one_case_and_reuses_saved_result(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("URBANLENS_S3_BUCKET", "bucket")
    monkeypatch.setenv("URBANLENS_DYNAMODB_TABLE", "fai-tce-team11-urbanlens-records")
    monkeypatch.setenv("URBANLENS_LAMBDA_BEDROCK_ENABLED", "true")
    dynamodb = FakeCloudDynamoDB()
    runtime = FakeNovaRuntime()
    event = {"dataset_id": "tn_study_area_demo_v1", "bucket": "bucket", "key": "urbanlens/datasets/tn_study_area_demo_v1/observations/observations.json"}
    first = cloud_lambda.handler(event, None, s3_client=FakeCloudS3(_cloud_observation_payload()),
                                dynamodb_service=dynamodb, bedrock_client=runtime)
    second = cloud_lambda.handler(event, None, s3_client=FakeCloudS3(_cloud_observation_payload()),
                                 dynamodb_service=dynamodb, bedrock_client=runtime)
    assert first["bedrock"]["invocations"] == 1
    assert first["status"] == "success"
    assert runtime.calls[0]["modelId"] == "apac.amazon.nova-lite-v1:0"
    assert runtime.calls[0]["inferenceConfig"]["maxTokens"] == 256
    assert second["bedrock"]["invocations"] == 0
    assert runtime.calls == runtime.calls[:1]
    saved = dynamodb.records["observations"][0]
    assert saved["bedrock_review"]["status"] == "success"
    assert saved["simulation"] is True


def test_cloud_api_returns_frontend_compatible_dataset_and_observations(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("URBANLENS_DYNAMODB_TABLE", "fai-tce-team11-urbanlens-records")
    dynamodb = FakeCloudDynamoDB()
    dynamodb.records["demo_datasets"] = [{"dataset_id": "tn_study_area_demo_v1", "simulation": True, "source": "SIMULATED_TAMIL_NADU_DATA"}]
    dynamodb.records["observations"] = [{"observation_id": "obs-1", "dataset_id": "tn_study_area_demo_v1", "simulation": True}]
    status = cloud_lambda.handler({"version": "2.0", "rawPath": "/datasets", "requestContext": {"http": {"method": "GET"}}}, None,
                                  dynamodb_service=dynamodb)
    observations = cloud_lambda.handler({"version": "2.0", "rawPath": "/observations", "requestContext": {"http": {"method": "GET"}}}, None,
                                        dynamodb_service=dynamodb)
    assert status["statusCode"] == 200
    assert json.loads(status["body"])["dataset"]["dataset_id"] == "tn_study_area_demo_v1"
    assert observations["statusCode"] == 200
    assert json.loads(observations["body"])[0]["observation_id"] == "obs-1"