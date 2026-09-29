"""Provider-independent normalization for selected-view visual detections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
import time
from typing import Any, Protocol
from uuid import uuid4

from app.services.study_area_service import STUDY_AREA_ID, contains_point

SUPPORTED_ASSET_TYPES = {
    "building", "streetlight", "electric_pole", "traffic_sign", "traffic_signal",
    "transformer", "waste_bin", "signboard", "utility_asset", "other",
}


class VisionProvider(Protocol):
    """Detector/classifier contract; providers return only their actual detections."""

    name: str

    def detect(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Analyze a selected-view image/context and return structured detections."""


class MockVisionProvider:
    """Deterministic fixture provider. Empty fixtures produce no detections."""

    name = "mock_fixture"

    def __init__(self, detections: Sequence[Mapping[str, Any]] = ()) -> None:
        self.detections = tuple(dict(item) for item in detections)

    def detect(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        return self.detections


class UnconfiguredVisionProvider:
    """Safe default until an approved detector is configured."""

    name = "unconfigured"

    def detect(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        return ()


class LocalYOLOWorldVisionProvider:
    """CPU-only open-vocabulary detector for buildings, streetlights, and poles.

    YOLO-World proposes instances for these configured classes. Results are
    candidate visual observations, not authoritative asset classifications.
    Model weights are loaded lazily from the official Ultralytics model source.
    """

    name = "ultralytics_yolov8s_worldv2_cpu"
    supported_classes = ("building", "streetlight", "electric pole")
    _class_mapping = {
        "building": "building",
        "streetlight": "streetlight",
        "street light": "streetlight",
        "electric pole": "electric_pole",
        "utility pole": "electric_pole",
    }

    def __init__(
        self,
        *,
        model: Any | None = None,
        model_factory: Any | None = None,
        confidence_threshold: float = 0.25,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1.")
        self._model = model
        self._model_factory = model_factory
        self.confidence_threshold = confidence_threshold
        self.last_latency_ms = 0.0
        self.invocation_count = 0

    def _get_model(self) -> Any:
        if self._model is None:
            model_cache = Path.home() / ".cache" / "urbanlens-ai" / "weights"
            model_cache.mkdir(parents=True, exist_ok=True)
            model_path = model_cache / "yolov8s-worldv2.pt"
            if self._model_factory is not None:
                self._model = self._model_factory(str(model_path))
            else:
                try:
                    from ultralytics import YOLOWorld
                    import ultralytics.utils as ultralytics_utils
                    from ultralytics.nn import text_model
                except ImportError as exc:
                    raise RuntimeError("Install ultralytics to enable the local YOLO-World detector.") from exc
                ultralytics_utils.SETTINGS.update({"weights_dir": str(model_cache)})
                ultralytics_utils.WEIGHTS_DIR = model_cache
                text_model.WEIGHTS_DIR = model_cache
                self._model = YOLOWorld(str(model_path))
            self._model.set_classes(list(self.supported_classes))
        return self._model

    @staticmethod
    def _image_from_context(view_context: Mapping[str, Any]) -> Any:
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
                raise ValueError("Local vision provider accepts local files only, not remote image URLs.")
            return Image.open(image_path).convert("RGB")
        raise ValueError("Selected-view context must include image, image_bytes, or a local image_path.")

    @staticmethod
    def _class_name(names: Any, class_id: int) -> str:
        if isinstance(names, Mapping):
            return str(names.get(class_id, names.get(str(class_id), ""))).strip().lower()
        if isinstance(names, Sequence) and class_id < len(names):
            return str(names[class_id]).strip().lower()
        return ""

    def detect(self, view_context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        image = self._image_from_context(view_context)
        model = self._get_model()
        started = time.perf_counter()
        self.invocation_count += 1
        outputs = model.predict(source=image, device="cpu", verbose=False, conf=self.confidence_threshold)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.last_latency_ms = elapsed_ms
        detections: list[dict[str, Any]] = []
        for output in outputs or ():
            boxes = getattr(output, "boxes", None)
            if boxes is None:
                continue
            coordinates = getattr(boxes, "xyxy", ())
            classes = getattr(boxes, "cls", ())
            confidences = getattr(boxes, "conf", ())
            for index, (xyxy, class_id, confidence) in enumerate(zip(coordinates, classes, confidences)):
                try:
                    class_index = int(class_id)
                    score = float(confidence)
                    x1, y1, x2, y2 = [float(value) for value in xyxy]
                except (TypeError, ValueError):
                    continue
                source_class = self._class_name(getattr(output, "names", {}), class_index)
                asset_type = self._class_mapping.get(source_class)
                if asset_type is None or score < self.confidence_threshold:
                    continue
                detections.append({
                    "observation_id": f"{view_context.get('view_id', 'view')}_{asset_type}_{index}",
                    "asset_type": asset_type,
                    "confidence": score,
                    "bounding_region": {
                        "x": max(0.0, x1), "y": max(0.0, y1),
                        "width": max(0.0, x2 - x1), "height": max(0.0, y2 - y1),
                    },
                    "model_name": self.name,
                    "source": self.name,
                    "processing_time_ms": elapsed_ms,
                })
        return detections


def normalize_detections(
    view_context: Mapping[str, Any],
    detections: Sequence[Mapping[str, Any]],
    *,
    provider_name: str,
) -> list[dict[str, Any]]:
    """Normalize provider-produced detections, preserving their provenance."""
    if not isinstance(view_context, Mapping):
        raise ValueError("Selected-view context must be an object.")
    view_id = view_context.get("view_id")
    latitude, longitude = view_context.get("latitude"), view_context.get("longitude")
    if not view_id or latitude is None or longitude is None:
        raise ValueError("Selected-view context needs view_id, latitude, and longitude.")
    latitude, longitude = float(latitude), float(longitude)
    if not contains_point(latitude, longitude):
        raise ValueError("Selected view is outside the official study area.")
    if isinstance(detections, (str, bytes)) or not isinstance(detections, Sequence):
        raise ValueError("Vision provider detections must be a sequence.")

    observations: list[dict[str, Any]] = []
    for detection in detections:
        if not isinstance(detection, Mapping):
            continue
        raw_type = str(detection.get("asset_type") or detection.get("entity_type") or "").strip().lower()
        asset_type = raw_type.replace("-", "_").replace(" ", "_")
        if asset_type not in SUPPORTED_ASSET_TYPES:
            continue
        try:
            confidence = float(detection["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= confidence <= 1:
            continue

        attributes = dict(detection.get("attributes") or {})
        if asset_type == "building":
            for key in ("visible_floor_count", "building_use", "frontage", "building_name", "business_name"):
                if key in detection and detection[key] is not None:
                    attributes[key] = detection[key]
        bbox = detection.get("bounding_region", detection.get("bounding_box"))
        observations.append({
            "observation_id": str(detection.get("observation_id") or f"obs_{uuid4().hex}"),
            "source_view_id": str(view_id),
            "panorama_reference": view_context.get("panorama_reference"),
            "latitude": latitude,
            "longitude": longitude,
            "heading": view_context.get("heading"),
            "pitch": view_context.get("pitch"),
            "field_of_view": view_context.get("field_of_view"),
            "asset_type": asset_type,
            "attributes": attributes,
            "bounding_region": dict(bbox) if isinstance(bbox, Mapping) else None,
            "confidence": confidence,
            "model_name": str(detection.get("model_name") or provider_name),
            "detector_type": str(detection.get("detector_type") or provider_name),
            "source": str(detection.get("source") or provider_name),
            "source_mode": str(view_context.get("source_mode") or "unknown"),
            "study_area_id": str(view_context.get("study_area_id") or STUDY_AREA_ID),
            "street_id": view_context.get("street_id"),
            "dataset_id": view_context.get("dataset_id"),
            "simulation": bool(view_context.get("simulation", False)),
            "provenance": view_context.get("provenance") or view_context.get("source_mode") or "unknown",
            "review_status": "pending",
            "processing_time_ms": detection.get("processing_time_ms"),
        })
    return observations


def detect_view_observations(
    view_context: Mapping[str, Any],
    provider: VisionProvider,
) -> list[dict[str, Any]]:
    """Run the configured detector and normalize only provider-returned results."""
    detections = provider.detect(view_context)
    return normalize_detections(view_context, detections, provider_name=provider.name)
