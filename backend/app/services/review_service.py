"""Human review queue for uncertain, conflicting, or weak observations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ReviewService:
    """Create and manage review entries for downstream review workflows."""

    VALID_STATUSES = {"pending", "approved", "rejected", "needs_review"}

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def create_review_entry(
        self,
        *,
        observation_id: str,
        reason: str,
        priority: str = "medium",
        status: str = "pending",
        reviewer_result: str | None = None,
    ) -> dict[str, Any]:
        review_id = f"review_{len(self.entries) + 1}_{observation_id}"
        created = datetime.now(timezone.utc).isoformat()
        entry = {
            "review_id": review_id,
            "observation_id": observation_id,
            "reason": reason,
            "priority": priority,
            "status": status,
            "created_at": created,
            "reviewed_at": None,
            "reviewer_result": reviewer_result,
        }
        self.entries.append(entry)
        return entry

    def list_reviews(self) -> list[dict[str, Any]]:
        return list(self.entries)

    def record_decision(
        self,
        review_id: str,
        *,
        status: str,
        reviewer: str,
        reviewer_decision: str | None = None,
    ) -> dict[str, Any]:
        """Store a reviewer decision and timestamp without discarding queue provenance."""
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Unsupported review status: {status}")
        if not reviewer.strip():
            raise ValueError("Reviewer identity is required.")
        entry = next((item for item in self.entries if item["review_id"] == review_id), None)
        if entry is None:
            raise KeyError(review_id)
        entry.update({
            "status": status,
            "reviewer": reviewer.strip(),
            "reviewer_decision": reviewer_decision,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        return dict(entry)
