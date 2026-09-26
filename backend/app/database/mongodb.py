"""Reusable MongoDB access helpers for UrbanLens AI.

Store structured metadata only. Large Street View images belong in approved
external object storage; MongoDB may store permitted evidence references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, GEOSPHERE, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError

from app.config import get_settings

COLLECTIONS = (
    "study_areas", "streets", "panoramas", "observations", "unified_entities",
    "reference_records", "matches", "discrepancies", "review_queue", "sampling_points",
    "processing_runs",
)

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return a shared client configured solely through MONGODB_URI."""
    global _client
    settings = get_settings()
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not configured.")
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
    return _client


def get_database() -> Database:
    """Return the configured UrbanLens database."""
    settings = get_settings()
    return get_client()[settings.mongodb_database]


def get_collection(name: str) -> Collection:
    """Return an approved collection, guarding against accidental typos."""
    if name not in COLLECTIONS:
        raise ValueError(f"Unknown UrbanLens collection: {name}")
    return get_database()[name]


def create_indexes() -> None:
    """Create database indexes, including GeoJSON-ready 2dsphere indexes."""
    database = get_database()
    existing = set(database.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            try:
                database.create_collection(name)
            except CollectionInvalid:
                # Another API worker may have created the collection first.
                pass
    for name in ("panoramas", "observations", "unified_entities", "reference_records", "sampling_points"):
        database[name].create_index([("location", GEOSPHERE)], name="location_2dsphere")
    for name in ("study_areas", "streets"):
        database[name].create_index([("geometry", GEOSPHERE)], name="geometry_2dsphere")
    database["study_areas"].create_index([("is_current", ASCENDING)], unique=True, sparse=True)
    database["streets"].create_index([("street_id", ASCENDING)], unique=True, sparse=True)
    database["sampling_points"].create_index([("sample_id", ASCENDING)], unique=True, sparse=True)
    database["panoramas"].create_index([("panorama_id", ASCENDING)], unique=True, sparse=True)
    database["observations"].create_index([("panorama_id", ASCENDING)])
    database["review_queue"].create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    database["processing_runs"].create_index([("status", ASCENDING), ("started_at", ASCENDING)])


def check_connection(create_schema: bool = False) -> bool:
    """Ping MongoDB, optionally creating collections and indexes after a ping."""
    try:
        get_client().admin.command("ping")
        if create_schema:
            create_indexes()
        return True
    except (PyMongoError, RuntimeError):
        return False


def to_object_id(value: str | ObjectId) -> ObjectId:
    """Safely convert a string ID to ObjectId."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValueError("Invalid MongoDB ObjectId.") from exc


def geojson_point(latitude: float, longitude: float) -> dict[str, Any]:
    """Build a GeoJSON Point; MongoDB requires [longitude, latitude] order."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude or longitude is outside its valid range.")
    return {"type": "Point", "coordinates": [longitude, latitude]}


def with_location(document: Mapping[str, Any]) -> dict[str, Any]:
    """Add MongoDB GeoJSON location when latitude and longitude are supplied."""
    data = dict(document)
    if "latitude" in data and "longitude" in data:
        data["location"] = geojson_point(float(data["latitude"]), float(data["longitude"]))
    return data


def insert_document(collection: str, document: Mapping[str, Any]) -> ObjectId:
    """Insert one metadata document and return its ObjectId."""
    return get_collection(collection).insert_one(with_location(document)).inserted_id


def find_documents(collection: str, query: Mapping[str, Any] | None = None, *, limit: int = 100) -> list[dict[str, Any]]:
    """Find documents with a bounded result count."""
    return list(get_collection(collection).find(dict(query or {})).limit(limit))


def find_one_document(collection: str, query: Mapping[str, Any]) -> dict[str, Any] | None:
    """Find one document using a MongoDB query."""
    return get_collection(collection).find_one(dict(query))


def update_document(collection: str, document_id: str | ObjectId, updates: Mapping[str, Any]) -> bool:
    """Update one document by ObjectId and report whether it exists."""
    result = get_collection(collection).update_one(
        {"_id": to_object_id(document_id)}, {"$set": with_location(updates)}
    )
    return result.matched_count == 1


def delete_document(collection: str, document_id: str | ObjectId) -> bool:
    """Delete one document by ObjectId and report whether it was removed."""
    return get_collection(collection).delete_one({"_id": to_object_id(document_id)}).deleted_count == 1
