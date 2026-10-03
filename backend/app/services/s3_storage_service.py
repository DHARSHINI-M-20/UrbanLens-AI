"""Optional S3 storage for UrbanLens simulated dataset artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from botocore.exceptions import ClientError
from bson import json_util

from app.config import get_settings

APPROVED_AWS_REGION = "ap-south-1"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class S3ConfigurationError(ValueError):
    """Raised when optional S3 settings are absent or unsafe."""


class S3StorageService:
    """Small S3 adapter that uses the standard boto3 credential chain."""

    def __init__(
        self,
        *,
        bucket: str | None = None,
        prefix: str | None = None,
        region: str | None = None,
        profile: str | None = None,
        client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.bucket = bucket if bucket is not None else settings.urbanlens_s3_bucket
        self.prefix = self._normalize_prefix(prefix if prefix is not None else settings.urbanlens_s3_prefix)
        self.region = region or settings.aws_region
        self.profile = profile if profile is not None else settings.aws_profile
        if self.region != APPROVED_AWS_REGION:
            raise S3ConfigurationError(f"UrbanLens AWS storage is restricted to {APPROVED_AWS_REGION}.")

        if client is None:
            if not self.bucket:
                raise S3ConfigurationError("URBANLENS_S3_BUCKET is not configured.")
            import boto3

            session = boto3.Session(profile_name=self.profile or None, region_name=self.region)
            client = session.client("s3")
        self.client = client

    @staticmethod
    def _normalize_prefix(prefix: str | None) -> str:
        if prefix is None:
            return "urbanlens/datasets"
        normalized = prefix.strip("/")
        if not normalized or "\\" in normalized or any(part in {".", ".."} for part in normalized.split("/")):
            raise S3ConfigurationError("URBANLENS_S3_PREFIX must be a safe relative S3 prefix.")
        return normalized

    @staticmethod
    def _validate_dataset_id(dataset_id: str) -> str:
        if not _SAFE_COMPONENT.fullmatch(dataset_id):
            raise ValueError("dataset_id must be a simple path component.")
        return dataset_id

    def dataset_key(self, dataset_id: str, *parts: str) -> str:
        dataset_id = self._validate_dataset_id(dataset_id)
        safe_parts = []
        for part in parts:
            normalized = part.replace("\\", "/").strip("/")
            if not normalized or any(piece in {".", ".."} for piece in normalized.split("/")):
                raise ValueError("S3 key components must be non-empty and cannot traverse directories.")
            safe_parts.append(normalized)
        return "/".join((self.prefix, dataset_id, *safe_parts))

    def _require_bucket(self, bucket: str | None = None) -> str:
        resolved = bucket or self.bucket
        if not resolved:
            raise S3ConfigurationError("URBANLENS_S3_BUCKET is not configured.")
        return resolved

    def _validate_key(self, key: str, dataset_id: str) -> None:
        expected = f"{self.prefix}/{self._validate_dataset_id(dataset_id)}/"
        if not key.startswith(expected) or "\\" in key or any(piece == ".." for piece in key.split("/")):
            raise ValueError("S3 object key must be under the configured dataset prefix.")

    @staticmethod
    def _metadata(dataset_id: str, source: str, simulation: bool, data: bytes) -> dict[str, str]:
        if not source:
            raise ValueError("S3 object provenance source is required.")
        return {
            "dataset_id": dataset_id,
            "source": source,
            "simulation": str(bool(simulation)).lower(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def _existing_head(self, bucket: str, key: str) -> dict[str, Any] | None:
        try:
            return self.client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error.get("Code") in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        dataset_id: str,
        source: str,
        simulation: bool,
        content_type: str = "application/octet-stream",
        bucket: str | None = None,
        skip_unchanged: bool = True,
    ) -> dict[str, Any]:
        self._validate_key(key, dataset_id)
        resolved_bucket = self._require_bucket(bucket)
        metadata = self._metadata(dataset_id, source, simulation, data)
        if skip_unchanged:
            existing = self._existing_head(resolved_bucket, key)
            if existing and existing.get("Metadata", {}).get("sha256") == metadata["sha256"]:
                return {"bucket": resolved_bucket, "key": key, "size": len(data), "sha256": metadata["sha256"], "uploaded": False}

        self.client.put_object(
            Bucket=resolved_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=metadata,
        )
        return {"bucket": resolved_bucket, "key": key, "size": len(data), "sha256": metadata["sha256"], "uploaded": True}

    def upload_file(
        self,
        file_path: str | Path,
        key: str,
        *,
        dataset_id: str,
        source: str,
        simulation: bool,
        content_type: str = "application/octet-stream",
        bucket: str | None = None,
        skip_unchanged: bool = True,
    ) -> dict[str, Any]:
        path = Path(file_path)
        data = path.read_bytes()
        self._validate_key(key, dataset_id)
        resolved_bucket = self._require_bucket(bucket)
        metadata = self._metadata(dataset_id, source, simulation, data)
        if skip_unchanged:
            existing = self._existing_head(resolved_bucket, key)
            if existing and existing.get("Metadata", {}).get("sha256") == metadata["sha256"]:
                return {"bucket": resolved_bucket, "key": key, "size": len(data), "sha256": metadata["sha256"], "uploaded": False}

        self.client.upload_file(
            str(path),
            resolved_bucket,
            key,
            ExtraArgs={"ContentType": content_type, "Metadata": metadata},
        )
        return {"bucket": resolved_bucket, "key": key, "size": len(data), "sha256": metadata["sha256"], "uploaded": True}

    def upload_json(
        self,
        key: str,
        payload: Any,
        *,
        dataset_id: str,
        source: str,
        simulation: bool,
        bucket: str | None = None,
        skip_unchanged: bool = True,
    ) -> dict[str, Any]:
        encoded = json_util.dumps(payload, separators=(",", ":")).encode("utf-8")
        return self.upload_bytes(
            key,
            encoded,
            dataset_id=dataset_id,
            source=source,
            simulation=simulation,
            content_type="application/json",
            bucket=bucket,
            skip_unchanged=skip_unchanged,
        )

    def object_exists(self, key: str, *, bucket: str | None = None) -> bool:
        resolved_bucket = self._require_bucket(bucket)
        return self._existing_head(resolved_bucket, key) is not None

    def get_object(self, key: str, *, bucket: str | None = None) -> bytes:
        response = self.client.get_object(Bucket=self._require_bucket(bucket), Key=key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def get_object_metadata(self, key: str, *, bucket: str | None = None) -> dict[str, Any]:
        response = self.client.head_object(Bucket=self._require_bucket(bucket), Key=key)
        return {
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "etag": response.get("ETag"),
            "last_modified": response.get("LastModified"),
            "metadata": response.get("Metadata", {}),
        }

    def list_prefix(self, prefix: str, *, bucket: str | None = None) -> list[dict[str, Any]]:
        resolved_bucket = self._require_bucket(bucket)
        paginator = self.client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=resolved_bucket, Prefix=prefix):
            objects.extend({
                "key": item["Key"],
                "size": item.get("Size"),
                "etag": item.get("ETag"),
                "last_modified": item.get("LastModified"),
            } for item in page.get("Contents", []))
        return objects

    def delete_object(self, key: str, *, bucket: str | None = None) -> None:
        self.client.delete_object(Bucket=self._require_bucket(bucket), Key=key)

    def delete_prefix(self, prefix: str, *, bucket: str | None = None) -> int:
        root = f"{self.prefix}/"
        normalized = prefix.strip("/")
        if not normalized.startswith(root) or normalized.count("/") < 2 or "\\" in normalized:
            raise ValueError("delete_prefix requires an explicit dataset-scoped prefix under the configured root.")
        if not normalized.endswith("/"):
            normalized += "/"
        objects = self.list_prefix(normalized, bucket=bucket)
        deleted = 0
        resolved_bucket = self._require_bucket(bucket)
        for offset in range(0, len(objects), 1000):
            batch = objects[offset:offset + 1000]
            if batch:
                response = self.client.delete_objects(
                    Bucket=resolved_bucket,
                    Delete={"Objects": [{"Key": item["key"]} for item in batch], "Quiet": True},
                )
                deleted += len(batch) - len(response.get("Errors", []))
        return deleted

    def head_bucket(self, *, bucket: str | None = None) -> None:
        self.client.head_bucket(Bucket=self._require_bucket(bucket))