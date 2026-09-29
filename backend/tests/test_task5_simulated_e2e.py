from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from app.database.mongodb import check_connection, get_collection
from app.main import app
from app.services import demo_service

pytestmark = pytest.mark.integration


def test_simulated_task5_seed_process_persist_and_api_consumption(monkeypatch):
    if not check_connection():
        pytest.skip("Configured MongoDB is unavailable for the simulated persistence test.")

    dataset_id = f"task5-e2e-{uuid.uuid4().hex}"
    monkeypatch.setattr(demo_service, "DEMO_DATASET_ID", dataset_id)
    try:
        seeded = demo_service.seed_demo_dataset()
        assert seeded["streets"] == 3
        assert seeded["panoramas"] == 6
        assert seeded["views"] == 6
        assert seeded["simulation"] is True
        assert "NOT REAL STREET VIEW DATA" in seeded["label"]

        prefix = {"dataset_id": dataset_id}
        observations = list(get_collection("observations").find(prefix))
        reviews = list(get_collection("review_queue").find(prefix))
        discrepancies = list(get_collection("discrepancies").find(prefix))
        fused = list(get_collection("unified_entities").find(prefix))
        metrics = list(get_collection("processing_metrics").find(prefix))
        matches = list(get_collection("matches").find(prefix))
        ocr = list(get_collection("ocr_observations").find(prefix))

        assert len(observations) >= 50
        assert {item["asset_type"] for item in observations} >= {"building", "streetlight", "electric_pole", "signboard"}
        assert {item["match_status"] for item in observations} >= {"matched", "mismatch", "unmatched"}
        assert any(item.get("simulation") and item.get("provenance") for item in observations)
        assert any(item.get("simulation") for item in ocr)
        assert any(item.get("positioning", {}).get("positioning_method") == "multi_view_ray_intersection"
                   for item in observations)
        assert any(item.get("supporting_view_count", 0) >= 2 for item in fused)
        assert len({item.get("fused_attributes", {}).get("building_name") for item in fused
                if item.get("asset_type") == "building"}) >= 15
        assert reviews and discrepancies and matches and metrics
        assert any(item.get("model_route") == "small_model" for item in metrics)
        assert any(item.get("simulated_escalation_invocations", 0) for item in metrics)
        assert all(item.get("nova_lite_invocations", 0) == 0 for item in metrics)
        assert all(item.get("actual_invocation_count", 0) == 0 for item in metrics)
        assert all(item.get("simulated_fixture_invocation_count", 0) > 0 for item in metrics)
        assert all(item.get("positioning_latency_ms", 0) >= 0 for item in metrics)
        assert all(item.get("estimated_cost") is None for item in metrics)
        discrepancy_types = {item["discrepancy_type"] for item in discrepancies}
        assert "floor_count_mismatch" in discrepancy_types
        assert "expected_streetlight_not_observed" in discrepancy_types

        async def verify_api_contracts():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                paths = [
                    f"/streets?dataset_id={dataset_id}",
                    f"/panoramas?dataset_id={dataset_id}",
                    f"/views?dataset_id={dataset_id}",
                    f"/observations?dataset_id={dataset_id}",
                    f"/observations/ocr?dataset_id={dataset_id}",
                    f"/references?dataset_id={dataset_id}",
                    f"/matching?dataset_id={dataset_id}",
                    f"/discrepancies?dataset_id={dataset_id}",
                    f"/reviews?dataset_id={dataset_id}",
                    f"/metrics?dataset_id={dataset_id}",
                    f"/metrics/summary?dataset_id={dataset_id}",
                    f"/analytics/summary?dataset_id={dataset_id}",
                ]
                responses = [await client.get(path) for path in paths]
                assert all(response.status_code == 200 for response in responses)
                assert all(response.json() for response in responses[:10])
                assert responses[-1].json()["simulation"] is True
                review = next(item for item in reviews if item.get("status") in {"pending", "needs_review"})
                decision = await client.patch(
                    f"/reviews/{review['review_id']}/decision",
                    json={"status": "approved", "reviewer": "e2e-test", "reviewer_decision": "confirmed"},
                )
                assert decision.status_code == 200
                assert decision.json()["status"] == "approved"

        asyncio.run(verify_api_contracts())
    finally:
        demo_service.reset_demo_dataset()
