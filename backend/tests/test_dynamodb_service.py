from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.dynamodb_service import (
    DynamoDBConfigurationError,
    DynamoDBService,
    make_item,
)


class FakeBatchWriter:
    def __init__(self):
        self.items = []
        self.deleted = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def put_item(self, *, Item):
        self.items.append(Item)

    def delete_item(self, *, Key):
        self.deleted.append(Key)


class FakeTable:
    def __init__(self):
        self.batch = FakeBatchWriter()
        self.queries = []
        self.query_items = []

    def batch_writer(self, *, overwrite_by_pkeys):
        assert overwrite_by_pkeys == ["pk", "sk"]
        return self.batch

    def query(self, **request):
        self.queries.append(request)
        if request.get("Select") == "COUNT":
            return {"Count": len(self.query_items)}
        if request.get("ProjectionExpression"):
            return {"Items": list(self.query_items)}
        return {"Items": [{"payload": {"observation_id": "obs-1", "confidence": Decimal("0.91")}}]}

    def delete_item(self, **request):
        self.deleted_key = request["Key"]


class FakeDynamoResource:
    def __init__(self):
        self.table = FakeTable()

    def Table(self, table_name):
        self.table_name = table_name
        return self.table


def test_make_item_preserves_payload_and_builds_dataset_collection_keys():
    record = {
        "observation_id": "obs-1",
        "dataset_id": "tn_study_area_demo_v1",
        "asset_type": "building",
        "street_id": "street-1",
        "confidence": 0.91,
        "attributes": {"visible_floor_count": 3},
        "simulation": True,
        "source": "SIMULATED_TAMIL_NADU_DATA",
    }
    item = make_item("tn_study_area_demo_v1", "observations", record)
    assert item["pk"] == "DATASET#tn_study_area_demo_v1"
    assert item["sk"] == "COLLECTION#observations#ID#obs-1"
    assert item["gsi1pk"] == "DATASET#tn_study_area_demo_v1#COLLECTION#observations"
    assert item["entity_type"] == "building"
    assert item["confidence"] == Decimal("0.91")
    assert item["payload"]["attributes"]["visible_floor_count"] == 3
    assert "pk" not in item["payload"]
    assert item["payload"] is not item


def test_entity_ids_use_collection_specific_fields_before_shared_fields():
    assert make_item("tn_study_area_demo_v1", "views", {
        "dataset_id": "tn_study_area_demo_v1", "street_id": "street-1",
        "panorama_id": "pano-1", "view_id": "view-1",
    })["entity_id"] == "view-1"
    assert make_item("tn_study_area_demo_v1", "unified_entities", {
        "dataset_id": "tn_study_area_demo_v1", "canonical_observation_id": "obs-1",
    })["entity_id"] == "obs-1"
    assert make_item("tn_study_area_demo_v1", "discrepancies", {
        "dataset_id": "tn_study_area_demo_v1", "observation_id": "obs-1",
        "reference_id": "ref-1", "discrepancy_id": "disc-1",
    })["entity_id"] == "disc-1"


def test_make_item_rejects_mismatched_or_missing_dataset_id():
    with pytest.raises(ValueError, match="matching"):
        make_item("tn_study_area_demo_v1", "observations", {"dataset_id": "other"})


def test_dynamodb_service_upserts_and_queries_only_the_requested_dataset():
    resource = FakeDynamoResource()
    service = DynamoDBService(resource=resource)
    records = [{
        "observation_id": "obs-1", "dataset_id": "tn_study_area_demo_v1",
        "asset_type": "building", "street_id": "street-1",
    }]
    assert service.put_records("tn_study_area_demo_v1", "observations", records) == 1
    assert resource.table.batch.items[0]["dataset_id"] == "tn_study_area_demo_v1"
    assert service.get_records("tn_study_area_demo_v1", collection="observations", street_id="street-1") == [
        {"observation_id": "obs-1", "confidence": 0.91}
    ]
    assert resource.table.queries[0]["IndexName"] == "by_dataset_collection"


def test_dynamodb_count_uses_dataset_partition_query():
    resource = FakeDynamoResource()
    resource.table.query_items = [{"pk": "dataset", "sk": "item-1"}, {"pk": "dataset", "sk": "item-2"}]
    service = DynamoDBService(resource=resource)
    assert service.count_records("tn_study_area_demo_v1") == 2
    assert resource.table.queries[0]["Select"] == "COUNT"


def test_dynamodb_service_restricts_region_and_table_prefix():
    resource = FakeDynamoResource()
    with pytest.raises(DynamoDBConfigurationError, match="restricted"):
        DynamoDBService(region="us-east-1", resource=resource)
    with pytest.raises(DynamoDBConfigurationError, match="fai-tce-team11"):
        DynamoDBService(table_name="urbanlens-records", resource=resource)


def test_dynamodb_delete_requires_matching_dataset_and_uses_exact_composite_key():
    resource = FakeDynamoResource()
    service = DynamoDBService(resource=resource)
    record = {"dataset_id": "tn_study_area_demo_v1", "observation_id": "obs-unique"}
    service.delete_record("tn_study_area_demo_v1", "observations", record)
    assert resource.table.deleted_key == {
        "pk": "DATASET#tn_study_area_demo_v1",
        "sk": "COLLECTION#observations#ID#obs-unique",
    }
    with pytest.raises(ValueError, match="matching"):
        service.delete_record("tn_study_area_demo_v1", "observations", {"dataset_id": "other"})


def test_reconcile_removes_only_stale_keys_for_the_target_dataset_collection():
    resource = FakeDynamoResource()
    resource.table.query_items = [
        {"pk": "DATASET#tn_study_area_demo_v1", "sk": "COLLECTION#views#ID#street-1"},
        {"pk": "DATASET#another-dataset", "sk": "COLLECTION#views#ID#unrelated"},
    ]
    service = DynamoDBService(resource=resource)
    outcome = service.reconcile_records("tn_study_area_demo_v1", "views", [{
        "dataset_id": "tn_study_area_demo_v1", "view_id": "view-1", "street_id": "street-1",
    }])
    assert outcome == {"written": 1, "stale_removed": 1}
    assert resource.table.batch.deleted == [{
        "pk": "DATASET#tn_study_area_demo_v1", "sk": "COLLECTION#views#ID#street-1",
    }]