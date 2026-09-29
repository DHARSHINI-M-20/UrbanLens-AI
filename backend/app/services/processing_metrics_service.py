"""Cost and latency tracking for the Street View processing pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ProcessingMetricsService:
    """Tracks view-level and aggregate workflow metrics."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record_view(
        self,
        *,
        view_id: str,
        small_model_used: bool,
        vlm_used: bool,
        model_route: str,
        latency_ms: float,
        estimated_cost: float | None = None,
        all_vlm_cost: float | None = None,
        all_vlm_cost_unavailable_reason: str | None = None,
        buildings_detected: int = 0,
        streetlights_detected: int = 0,
        electric_poles_detected: int = 0,
        ocr_observations: int = 0,
        matched_observations: int = 0,
        unmatched_observations: int = 0,
        low_confidence_observations: int = 0,
        detector_invocations: int = 0,
        ocr_invocations: int = 0,
        nova_lite_invocations: int = 0,
        nova_lite_invocation_attempts: int = 0,
        detector_latency_ms: float = 0.0,
        ocr_latency_ms: float = 0.0,
        nova_lite_latency_ms: float = 0.0,
        cost_status: str | None = None,
        cost_unavailable_reason: str | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        record = {
            "view_id": view_id,
            "small_model_used": bool(small_model_used),
            "vlm_used": bool(vlm_used),
            "model_route": model_route,
            "latency_ms": float(latency_ms),
            "estimated_cost": float(estimated_cost) if estimated_cost is not None else None,
            "all_vlm_cost": float(all_vlm_cost) if all_vlm_cost is not None else None,
            "all_vlm_cost_unavailable_reason": all_vlm_cost_unavailable_reason if all_vlm_cost is None else None,
            "buildings_detected": int(buildings_detected),
            "streetlights_detected": int(streetlights_detected),
            "electric_poles_detected": int(electric_poles_detected),
            "ocr_observations": int(ocr_observations),
            "matched_observations": int(matched_observations),
            "unmatched_observations": int(unmatched_observations),
            "low_confidence_observations": int(low_confidence_observations),
            "detector_invocations": int(detector_invocations),
            "ocr_invocations": int(ocr_invocations),
            "nova_lite_invocations": int(nova_lite_invocations),
            "nova_lite_invocation_attempts": int(nova_lite_invocation_attempts),
            "actual_invocation_count": int(detector_invocations + ocr_invocations + nova_lite_invocations),
            "detector_latency_ms": float(detector_latency_ms),
            "ocr_latency_ms": float(ocr_latency_ms),
            "nova_lite_latency_ms": float(nova_lite_latency_ms),
            "cost_status": cost_status or ("available" if estimated_cost is not None else "unavailable"),
            "cost_unavailable_reason": cost_unavailable_reason if estimated_cost is None else None,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        }
        self.records.append(record)
        return record

    def summary(self) -> dict[str, Any]:
        total_views = len(self.records)
        small_model_views = sum(1 for row in self.records if row.get("small_model_used"))
        vlm_views = sum(1 for row in self.records if row.get("vlm_used"))
        total_latency = sum(float(row.get("latency_ms", 0.0) or 0.0) for row in self.records)
        known_costs = [float(row["estimated_cost"]) for row in self.records if row.get("estimated_cost") is not None]
        complete_cost_data = bool(self.records) and len(known_costs) == len(self.records)
        total_cost = sum(known_costs) if complete_cost_data else None
        cost_status = "available" if complete_cost_data else "partial" if known_costs else "unavailable"
        return {
            "total_views": total_views,
            "small_model_views": small_model_views,
            "vlm_views": vlm_views,
            "vlm_percentage": round((vlm_views / total_views), 4) if total_views else 0.0,
            "average_latency_ms": round((total_latency / total_views), 2) if total_views else 0.0,
            "total_latency_ms": round(total_latency, 2),
            "actual_invocation_count": sum(int(row.get("actual_invocation_count", 0) or 0) for row in self.records),
            "detector_invocations": sum(int(row.get("detector_invocations", 0) or 0) for row in self.records),
            "ocr_invocations": sum(int(row.get("ocr_invocations", 0) or 0) for row in self.records),
            "nova_lite_invocations": sum(int(row.get("nova_lite_invocations", 0) or 0) for row in self.records),
            "nova_lite_invocation_attempts": sum(int(row.get("nova_lite_invocation_attempts", 0) or 0) for row in self.records),
            "detector_latency_ms": round(sum(float(row.get("detector_latency_ms", 0) or 0) for row in self.records), 2),
            "ocr_latency_ms": round(sum(float(row.get("ocr_latency_ms", 0) or 0) for row in self.records), 2),
            "nova_lite_latency_ms": round(sum(float(row.get("nova_lite_latency_ms", 0) or 0) for row in self.records), 2),
            "buildings_detected": sum(int(row.get("buildings_detected", 0) or 0) for row in self.records),
            "streetlights_detected": sum(int(row.get("streetlights_detected", 0) or 0) for row in self.records),
            "electric_poles_detected": sum(int(row.get("electric_poles_detected", 0) or 0) for row in self.records),
            "ocr_observations": sum(int(row.get("ocr_observations", 0) or 0) for row in self.records),
            "matched_observations": sum(int(row.get("matched_observations", 0) or 0) for row in self.records),
            "unmatched_observations": sum(int(row.get("unmatched_observations", 0) or 0) for row in self.records),
            "low_confidence_observations": sum(int(row.get("low_confidence_observations", 0) or 0) for row in self.records),
            "estimated_total_cost": round(total_cost, 4) if total_cost is not None else None,
            "known_cost_subtotal": round(sum(known_costs), 4) if known_costs else None,
            "cost_status": cost_status,
            "cost_unavailable_reasons": sorted({
                str(row["cost_unavailable_reason"])
                for row in self.records if row.get("cost_unavailable_reason")
            }),
        }

    def hypothetical_all_vlm_comparison(self) -> dict[str, Any]:
        summary = self.summary()
        routed_cost = summary["estimated_total_cost"]
        all_vlm_costs = [row.get("all_vlm_cost") for row in self.records]
        all_vlm_available = bool(self.records) and all(cost is not None for cost in all_vlm_costs)
        all_vlm_reasons = sorted({
            str(row["all_vlm_cost_unavailable_reason"])
            for row in self.records if row.get("all_vlm_cost_unavailable_reason")
        })
        return {
            "workflow": "proposed_routed_workflow",
            "estimated_total_cost": routed_cost,
            "all_selected_views_to_vlm_cost": round(sum(float(cost) for cost in all_vlm_costs), 4) if all_vlm_available else None,
            "all_vlm_cost_status": "available" if all_vlm_available else "unavailable",
            "all_vlm_cost_unavailable_reasons": all_vlm_reasons or ([] if all_vlm_available else ["NOVA_LITE_COST_PER_INVOCATION is not configured for all selected views."]),
            "comparison_note": "Costs are unavailable unless configured invocation pricing is recorded; no AWS bill is inferred.",
        }
