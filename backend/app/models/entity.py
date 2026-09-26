"""Urban asset or property entity model."""

from pydantic import BaseModel


class Entity(BaseModel):
    entity_id: str
    entity_type: str
    latitude: float
    longitude: float
