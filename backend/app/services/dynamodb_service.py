"""Dataset-scoped DynamoDB persistence for the optional AWS cloud path."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

APPROVED_AWS_REGION = "ap-south-1"
DEFAULT_TABLE_NAME = "fai-tce-team11-urbanlens-records"
GSI_NAME = "by_dataset_collection"


class DynamoDBConfigurationError(ValueError):
    """Raised when cloud database settings are incomplete or unsafe."""


def _native_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _native_value(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, (list, tuple)):
        return [_native_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if value is None or isinstance(value, (str, int, bool, bytes)):
        return value
    if hasattr(value, "binary"):
        return bytes(value.binary)
    return str(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items() if key not in {"pk", "sk", "gsi1pk", "gsi1sk"}}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def entity_id(collection: str, record: dict[str, Any]) -> str:
    collection_ids = {
        "observations": ("observation_id",),
        "ocr_observations": ("ocr_id",),
        "reference_records": ("reference_id",),
        "matches": ("match_id", "observation_id"),
        "discrepancies": ("discrepancy_id",),
        "review_queue": ("review_id",),
        "streets": ("street_id",),
        "sampling_points": ("sample_id",),
        "panoramas": ("panorama_id",),
        "views": ("view_id",),
        "study_areas": ("study_area_id",),
        "unified_entities": ("canonical_observation_id",),
        "demo_datasets": ("dataset_id",),
        "processing_metrics": ("processing_id", "view_id"),
        "processing_runs": ("run_id", "processing_run_id"),
    }
    candidates = collection_ids.get(collection, ()) + (
        "observation_id", "ocr_id", "reference_id", "match_id", "discrepancy_id",
        "review_id", "street_id", "sample_id", "view_id", "panorama_id",
        "canonical_observation_id", "processing_id", "dataset_id",
    )
    for field in candidates:
        if record.get(field) is not None:
            return str(record[field])
    stable = json.dumps(record, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(f"{collection}:{stable}".encode("utf-8")).hexdigest()


def make_item(dataset_id: str, collection: str, record: dict[str, Any]) -> dict[str, Any]:
    if not dataset_id or record.get("dataset_id") != dataset_id:
        raise ValueError("DynamoDB writes require a matching, explicit dataset_id.")
    identifier = entity_id(collection, record)
    street_id = str(record.get("street_id") or "_")
    payload = _native_value(record)
    item = dict(payload)
    item.update({
        "pk": f"DATASET#{dataset_id}",
        "sk": f"COLLECTION#{collection}#ID#{identifier}",
        "gsi1pk": f"DATASET#{dataset_id}#COLLECTION#{collection}",
        "gsi1sk": f"STREET#{street_id}#ID#{identifier}",
        "dataset_id": dataset_id,
        "entity_id": identifier,
        "entity_type": str(record.get("asset_type") if collection == "observations" else collection),
        "source_collection": collection,
        "payload": payload,
    })
    return item


class DynamoDBService:
    """One on-demand table retaining the Mongo record shape as payloads."""

    def __init__(
        self,
        *,
        table_name: str | None = None,
        region: str | None = None,
        profile: str | None = None,
        resource: Any | None = None,
    ) -> None:
        settings = None
        if table_name is None or region is None or profile is None:
            try:
                from app.config import get_settings

                settings = get_settings()
            except ImportError:
                settings = None
        self.table_name = table_name or getattr(settings, "urbanlens_dynamodb_table", None) or DEFAULT_TABLE_NAME
        self.region = region or getattr(settings, "aws_region", APPROVED_AWS_REGION)
        self.profile = profile if profile is not None else getattr(settings, "aws_profile", None)
        if self.region != APPROVED_AWS_REGION:
            raise DynamoDBConfigurationError(f"UrbanLens DynamoDB is restricted to {APPROVED_AWS_REGION}.")
        if not self.table_name.startswith("fai-tce-team11-"):
            raise DynamoDBConfigurationError("DynamoDB table must use the fai-tce-team11- prefix.")
        if resource is None:
            import boto3

            session = boto3.Session(profile_name=self.profile or None, region_name=self.region)
            resource = session.resource("dynamodb")
        self.resource = resource
        self.table = resource.Table(self.table_name)

    def ensure_table(self) -> dict[str, Any]:
        client = self.resource.meta.client
        try:
            return client.describe_table(TableName=self.table_name)["Table"]
        except client.exceptions.ResourceNotFoundException:
            client.create_table(
                TableName=self.table_name,
                AttributeDefinitions=[
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                    {"AttributeName": "gsi1pk", "AttributeType": "S"},
                    {"AttributeName": "gsi1sk", "AttributeType": "S"},
                ],
                KeySchema=[
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                BillingMode="PAY_PER_REQUEST",
                GlobalSecondaryIndexes=[{
                    "IndexName": GSI_NAME,
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }],
            )
            self.resource.meta.client.get_waiter("table_exists").wait(
                TableName=self.table_name,
                WaiterConfig={"Delay": 2, "MaxAttempts": 30},
            )
            return client.describe_table(TableName=self.table_name)["Table"]

    def put_records(self, dataset_id: str, collection: str, records: list[dict[str, Any]]) -> int:
        if not dataset_id:
            raise ValueError("dataset_id is required.")
        written = 0
        with self.table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
            for record in records:
                batch.put_item(Item=make_item(dataset_id, collection, record))
                written += 1
        return written

    def reconcile_records(self, dataset_id: str, collection: str, records: list[dict[str, Any]]) -> dict[str, int]:
        """Upsert source records and remove obsolete keys only in this dataset/collection."""
        expected = {make_item(dataset_id, collection, record)["sk"] for record in records}
        prefix = f"COLLECTION#{collection}#"
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}") & Key("sk").begins_with(prefix),
            ProjectionExpression="pk, sk",
        )
        existing = list(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}") & Key("sk").begins_with(prefix),
                ProjectionExpression="pk, sk",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            existing.extend(response.get("Items", []))
        partition_key = f"DATASET#{dataset_id}"
        stale = [
            item for item in existing
            if item.get("pk") == partition_key
            and str(item.get("sk", "")).startswith(prefix)
            and item.get("sk") not in expected
        ]

        written = self.put_records(dataset_id, collection, records)
        if stale:
            with self.table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
                for item in stale:
                    batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        return {"written": written, "stale_removed": len(stale)}

    def delete_record(self, dataset_id: str, collection: str, record: dict[str, Any]) -> None:
        if not dataset_id or record.get("dataset_id") != dataset_id:
            raise ValueError("DynamoDB deletes require a matching, explicit dataset_id.")
        self.table.delete_item(Key={
            "pk": f"DATASET#{dataset_id}",
            "sk": f"COLLECTION#{collection}#ID#{entity_id(collection, record)}",
        })

    def get_records(
        self,
        dataset_id: str,
        *,
        collection: str | None = None,
        street_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if collection and street_id:
            response = self.table.query(
                IndexName=GSI_NAME,
                KeyConditionExpression=Key("gsi1pk").eq(f"DATASET#{dataset_id}#COLLECTION#{collection}")
                & Key("gsi1sk").begins_with(f"STREET#{street_id}#"),
            )
        elif collection:
            response = self.table.query(
                IndexName=GSI_NAME,
                KeyConditionExpression=Key("gsi1pk").eq(f"DATASET#{dataset_id}#COLLECTION#{collection}"),
            )
        else:
            response = self.table.query(KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}"))

        items = list(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            args = {"ExclusiveStartKey": response["LastEvaluatedKey"]}
            if collection and street_id:
                response = self.table.query(
                    IndexName=GSI_NAME,
                    KeyConditionExpression=Key("gsi1pk").eq(f"DATASET#{dataset_id}#COLLECTION#{collection}")
                    & Key("gsi1sk").begins_with(f"STREET#{street_id}#"),
                    **args,
                )
            elif collection:
                response = self.table.query(
                    IndexName=GSI_NAME,
                    KeyConditionExpression=Key("gsi1pk").eq(f"DATASET#{dataset_id}#COLLECTION#{collection}"),
                    **args,
                )
            else:
                response = self.table.query(
                    KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}"), **args
                )
            items.extend(response.get("Items", []))
        return [_json_value(item.get("payload", item)) for item in items]

    def count_records(self, dataset_id: str) -> int:
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}"),
            Select="COUNT",
        )
        total = int(response.get("Count", 0))
        while response.get("LastEvaluatedKey"):
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"DATASET#{dataset_id}"),
                Select="COUNT",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            total += int(response.get("Count", 0))
        return total

    def get_status(self) -> dict[str, Any]:
        try:
            table = self.resource.meta.client.describe_table(TableName=self.table_name)["Table"]
            return {
                "configured": True,
                "table": self.table_name,
                "exists": True,
                "status": table.get("TableStatus"),
                "item_count_estimate": table.get("ItemCount"),
                "dataset_item_count": self.count_records("tn_study_area_demo_v1"),
            }
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "AWSClientError"))
            if code == "ResourceNotFoundException":
                return {"configured": True, "table": self.table_name, "exists": False, "status": None, "item_count": None}
            raise