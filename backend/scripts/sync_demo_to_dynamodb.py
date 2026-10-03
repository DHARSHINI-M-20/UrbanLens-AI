"""Synchronize the seeded simulated Task 5 dataset into one DynamoDB table."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from app.database.mongodb import check_connection, get_collection
from app.services.demo_service import ALL_DEMO_COLLECTIONS, DEMO_DATASET_ID
from app.services.dynamodb_service import DynamoDBService


def sync_demo_dataset(*, service: DynamoDBService | None = None) -> dict[str, Any]:
    if not check_connection():
        raise RuntimeError("MongoDB is unavailable; no DynamoDB synchronization was attempted.")
    dataset = get_collection("demo_datasets").find_one({"dataset_id": DEMO_DATASET_ID})
    if dataset is None or dataset.get("simulation") is not True:
        raise RuntimeError(f"Simulated dataset {DEMO_DATASET_ID} is not seeded in MongoDB.")

    dynamodb = service or DynamoDBService()
    table = dynamodb.ensure_table()
    written_by_collection: dict[str, int] = {}
    removed_by_collection: dict[str, int] = {}
    for collection_name in ALL_DEMO_COLLECTIONS:
        records = list(get_collection(collection_name).find({"dataset_id": DEMO_DATASET_ID}))
        outcome = dynamodb.reconcile_records(DEMO_DATASET_ID, collection_name, records)
        written_by_collection[collection_name] = outcome["written"]
        if outcome["stale_removed"]:
            removed_by_collection[collection_name] = outcome["stale_removed"]
    return {
        "dataset_id": DEMO_DATASET_ID,
        "simulation": True,
        "table": dynamodb.table_name,
        "table_status": table.get("TableStatus"),
        "records_written": sum(written_by_collection.values()),
        "records_by_collection": written_by_collection,
        "stale_target_items_removed_by_collection": removed_by_collection,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", help="Override the configured fai-tce-team11 DynamoDB table.")
    args = parser.parse_args()
    try:
        service = DynamoDBService(table_name=args.table) if args.table else DynamoDBService()
        print(json.dumps(sync_demo_dataset(service=service), indent=2, sort_keys=True))
        return 0
    except (ClientError, NoCredentialsError, PartialCredentialsError, RuntimeError, ValueError, OSError) as exc:
        print(f"DynamoDB synchronization failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())