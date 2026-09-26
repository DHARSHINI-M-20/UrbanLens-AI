"""Reference-data model."""

from pydantic import BaseModel


class ReferenceRecord(BaseModel):
    source: str
    external_id: str
    entity_type: str
