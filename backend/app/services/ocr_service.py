"""OCR support for street signage, building names, and visible identifiers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
import time
from typing import Any, Protocol


class OCRProvider(Protocol):
    """OCR adapter for an approved OCR implementation."""

    name: str

    def recognize(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Return text blocks actually recognized from the selected view."""


class MockOCRProvider:
    """Deterministic OCR fixtures for tests; empty fixtures produce no text."""

    name = "mock_fixture"

    def __init__(self, results: Sequence[Mapping[str, Any]] = ()) -> None:
        self.results = tuple(dict(item) for item in results)

    def recognize(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        return self.results


class UnconfiguredOCRProvider:
    """Safe default until an approved OCR provider is configured."""

    name = "unconfigured"

    def recognize(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        return ()


class TesseractOCRProvider:
    """Local Tesseract adapter; it performs no network access or image upload."""

    name = "tesseract_local"

    def __init__(self, *, language: str = "eng", executable_path: str | None = None) -> None:
        self.language = language
        self.executable_path = executable_path
        self.last_latency_ms = 0.0
        self.invocation_count = 0

    def _image_from_context(self, view_context: Mapping[str, Any]) -> Any:
        image = view_context.get("image")
        if image is not None:
            return image
        image_bytes = view_context.get("image_bytes")
        image_path = view_context.get("image_path")
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Install Pillow to decode local view images.") from exc
        if isinstance(image_bytes, bytes):
            return Image.open(BytesIO(image_bytes)).convert("RGB")
        if isinstance(image_path, (str, Path)):
            if str(image_path).startswith(("http://", "https://")):
                raise ValueError("Local OCR accepts local files only, not remote image URLs.")
            return Image.open(image_path).convert("RGB")
        raise ValueError("Selected-view context must include image, image_bytes, or a local image_path.")

    def recognize(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError("Install pytesseract to enable local OCR.") from exc
        if self.executable_path:
            pytesseract.pytesseract.tesseract_cmd = self.executable_path
        image = self._image_from_context(view_context)
        started = time.perf_counter()
        self.invocation_count += 1
        data = pytesseract.image_to_data(image, lang=self.language, output_type=Output.DICT)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.last_latency_ms = elapsed_ms
        results: list[dict[str, Any]] = []
        for index, text in enumerate(data.get("text", [])):
            raw_text = str(text)
            if not normalize_ocr_text(raw_text):
                continue
            try:
                raw_confidence = float(data.get("conf", [])[index])
                confidence = max(0.0, min(1.0, raw_confidence / 100)) if raw_confidence >= 0 else None
                x, y, width, height = (int(data[key][index]) for key in ("left", "top", "width", "height"))
            except (IndexError, TypeError, ValueError, KeyError):
                confidence = None
                x = y = width = height = None
            results.append({
                "text": raw_text,
                "confidence": confidence,
                "bounding_region": ({"x": x, "y": y, "width": width, "height": height}
                                     if width and height else None),
                "source": self.name,
                "processing_time_ms": elapsed_ms,
            })
        return results


def normalize_ocr_text(value: str) -> str:
    """Normalize Unicode and whitespace without altering the preserved raw text."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def process_view_ocr(view_context: Mapping[str, Any], provider: OCRProvider) -> list[dict[str, Any]]:
    """Normalize only text blocks returned by the configured OCR provider."""
    results = provider.recognize(view_context)
    if isinstance(results, (str, bytes)) or not isinstance(results, Sequence):
        raise ValueError("OCR provider results must be a sequence.")
    view_id = str(view_context.get("view_id") or "")
    normalized: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, Mapping) or not isinstance(result.get("text"), str):
            continue
        raw_text = result["text"]
        clean_text = normalize_ocr_text(raw_text)
        if not clean_text:
            continue
        confidence_value = result.get("confidence")
        try:
            confidence = float(confidence_value) if confidence_value is not None else None
        except (TypeError, ValueError):
            continue
        if confidence is not None and not 0 <= confidence <= 1:
            continue
        normalized.append({
            "ocr_id": str(result.get("ocr_id") or f"ocr_{len(normalized) + 1}_{view_id}"),
            "raw_text": raw_text,
            "normalized_text": clean_text,
            "ocr_text": raw_text,
            "confidence": confidence,
            "bounding_region": result.get("bounding_region", result.get("bounding_box")),
            "source_view_id": view_id,
            "source": str(result.get("source") or provider.name),
            "review_status": "pending" if confidence is not None and confidence >= 0.5 else "needs_review",
            "processing_time_ms": result.get("processing_time_ms"),
        })
    return normalized


def extract_text_ocr(
    *,
    ocr_text: str | None = None,
    confidence: float = 0.0,
    bounding_region: dict[str, Any] | None = None,
    language: str | None = None,
    source: str = "small_model",
    status: str = "not_run",
    source_view_id: str | None = None,
) -> dict[str, Any]:
    """Return OCR metadata without fabricating unsupported results."""
    raw_text = ocr_text or ""
    return {
        "ocr_text": raw_text,
        "raw_text": raw_text,
        "normalized_text": normalize_ocr_text(raw_text),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "bounding_region": bounding_region,
        "language": language,
        "source": source,
        "source_view_id": source_view_id,
        "status": status,
        "review_status": "needs_review" if status == "not_run" else "pending",
    }
