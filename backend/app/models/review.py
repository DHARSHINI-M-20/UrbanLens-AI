"""Human-review model."""

from pydantic import BaseModel


class Review(BaseModel):
    entity_id: str
    decision: str
    reviewer_notes: str | None = None
