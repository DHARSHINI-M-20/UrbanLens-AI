"""Metric calculators for explicitly labelled evaluation examples."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.services.ocr_service import normalize_ocr_text


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def confusion_metrics(tp: int, fp: int, fn: int, *, evaluated: int,
                      excluded_unknown_ground_truth: int = 0) -> dict[str, Any]:
    denominator = 2 * tp + fp + fn
    return {
        "status": "evaluated" if evaluated else "not_evaluable",
        "evaluated": evaluated,
        "excluded_unknown_ground_truth": excluded_unknown_ground_truth,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "f1": round(2 * tp / denominator, 6) if denominator else None,
    }


def bounding_box_iou(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    """Return pixel-space intersection over union for x/y/width/height boxes."""
    try:
        ax1, ay1 = float(first["x"]), float(first["y"])
        ax2, ay2 = ax1 + float(first["width"]), ay1 + float(first["height"])
        bx1, by1 = float(second["x"]), float(second["y"])
        bx2, by2 = bx1 + float(second["width"]), by1 + float(second["height"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = max(0.0, (ax2 - ax1) * (ay2 - ay1)) + max(0.0, (bx2 - bx1) * (by2 - by1)) - intersection
    return intersection / union if union else 0.0


def _box(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    candidate = item.get("bounding_box", item.get("bounding_region"))
    return candidate if isinstance(candidate, Mapping) else None


def _match_instances(ground_truth: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]],
                     *, iou_threshold: float = 0.5) -> tuple[int, str]:
    """Find a maximum-cardinality pairing by IoU or stable ID when geometry is absent."""
    edges: list[list[tuple[float, int, str]]] = []
    for truth in ground_truth:
        truth_id = truth.get("building_id", truth.get("asset_id", truth.get("entity_id")))
        truth_box = _box(truth)
        candidates: list[tuple[float, int, str]] = []
        for index, prediction in enumerate(predictions):
            prediction_id = prediction.get("entity_id", prediction.get("asset_id", prediction.get("observation_id")))
            prediction_box = _box(prediction)
            if truth_box is not None and prediction_box is not None:
                score = bounding_box_iou(truth_box, prediction_box)
                if score >= iou_threshold:
                    candidates.append((score, index, "bbox_iou"))
            elif truth_id is not None and prediction_id is not None and str(truth_id) == str(prediction_id):
                candidates.append((1.0, index, "stable_id"))
        edges.append(sorted(candidates, key=lambda row: (-row[0], row[1])))

    prediction_owner: dict[int, int] = {}
    matched_basis: dict[int, str] = {}

    def assign(truth_index: int, visited: set[int]) -> bool:
        for _score, prediction_index, basis in edges[truth_index]:
            if prediction_index in visited:
                continue
            visited.add(prediction_index)
            current_owner = prediction_owner.get(prediction_index)
            if current_owner is None or assign(current_owner, visited):
                prediction_owner[prediction_index] = truth_index
                matched_basis[prediction_index] = basis
                return True
        return False

    for truth_index in range(len(ground_truth)):
        assign(truth_index, set())
    used_basis = set(matched_basis.values())
    basis_name = "+".join(sorted(used_basis)) if used_basis else "bbox_iou_or_stable_id"
    return len(prediction_owner), basis_name


def detection_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]],
                      *, asset_types: Sequence[str] | None = None) -> dict[str, Any]:
    """Evaluate exhaustive class labels; unlabeled image/classes are excluded."""
    class_names = list(asset_types or sorted({
        str(asset.get("asset_type")) for sample in samples for asset in sample.get("assets", [])
    }))

    def for_class(class_name: str, *, building: bool = False) -> dict[str, Any]:
        tp = fp = fn = evaluated = excluded = labeled_images = 0
        bases: Counter[str] = Counter()
        for sample in samples:
            image_id = str(sample["image_id"])
            if class_name not in sample.get("labeled_classes", []):
                excluded += 1
                continue
            labeled_images += 1
            gt_key = "buildings" if building else "assets"
            truth_items = [dict(row) for row in sample.get(gt_key, [])
                           if row.get("presence", True) and (building or row.get("asset_type") == class_name)]
            predicted_items = [dict(row) for row in predictions_by_image.get(image_id, {}).get("observations", [])
                               if (row.get("asset_type") or row.get("entity_type")) == class_name]
            matched, basis = _match_instances(truth_items, predicted_items)
            tp += matched
            fn += len(truth_items) - matched
            fp += len(predicted_items) - matched
            # The denominator records labeled image/class opportunities, including
            # explicitly labeled negative images with zero objects.
            evaluated += 1
            bases[basis] += 1
        result = confusion_metrics(tp, fp, fn, evaluated=evaluated,
                                   excluded_unknown_ground_truth=excluded)
        result.update({"labeled_images": labeled_images,
                       "evaluated_instances": tp + fp + fn,
                       "matching_basis": dict(bases)})
        return result

    buildings = for_class("building", building=True)
    by_type = {name: for_class(name) for name in class_names}
    total = confusion_metrics(
        sum(row["true_positives"] for row in by_type.values()),
        sum(row["false_positives"] for row in by_type.values()),
        sum(row["false_negatives"] for row in by_type.values()),
        evaluated=sum(row["evaluated"] for row in by_type.values()),
        excluded_unknown_ground_truth=sum(row["excluded_unknown_ground_truth"] for row in by_type.values()),
    )
    total["evaluated_images_by_class"] = sum(row["labeled_images"] for row in by_type.values())
    total["evaluated_instances"] = total["true_positives"] + total["false_positives"] + total["false_negatives"]
    return {"buildings": buildings, "assets": {"overall": total, "by_class": by_type}}


def _prediction_for_entity(entity: Mapping[str, Any], predictions: Sequence[Mapping[str, Any]],
                           *, asset_type: str = "building") -> Mapping[str, Any] | None:
    entity_id = entity.get("building_id", entity.get("entity_id", entity.get("asset_id")))
    same_type = [row for row in predictions if (row.get("asset_type") or row.get("entity_type")) == asset_type]
    for row in same_type:
        row_id = row.get("entity_id", row.get("asset_id", row.get("observation_id")))
        if entity_id is not None and row_id is not None and str(entity_id) == str(row_id):
            truth_box, prediction_box = _box(entity), _box(row)
            if truth_box is None or prediction_box is None or bounding_box_iou(truth_box, prediction_box) >= 0.5:
                return row
    truth_box = _box(entity)
    if truth_box is not None:
        candidates = [(bounding_box_iou(truth_box, _box(row) or {}), row) for row in same_type if _box(row)]
        candidates = [item for item in candidates if item[0] >= 0.5]
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
    return None


def _associated_entity_id(sample: Mapping[str, Any], entity_id: str,
                          predictions: Sequence[Mapping[str, Any]], *, asset_type: str = "building") -> str:
    truth = next((row for row in sample.get("buildings", []) if str(row.get("building_id")) == entity_id), None)
    if truth is None:
        truth = next((row for row in sample.get("assets", []) if str(row.get("asset_id")) == entity_id), None)
        asset_type = str((truth or {}).get("asset_type") or asset_type)
    detection = _prediction_for_entity(truth, predictions, asset_type=asset_type) if truth else None
    return str((detection or {}).get("observation_id", entity_id))


def scalar_classification_metrics(pairs: Sequence[tuple[str, str]], *,
                                  excluded_unknown_ground_truth: int = 0) -> dict[str, Any]:
    evaluated = len(pairs)
    correct = sum(truth == predicted for truth, predicted in pairs)
    labels = sorted({label for pair in pairs for label in pair})
    matrix = {truth: {predicted: 0 for predicted in labels} for truth in labels}
    for truth, predicted in pairs:
        matrix[truth][predicted] += 1
    return {"status": "evaluated" if evaluated else "not_evaluable",
            "evaluated": evaluated,
            "excluded_unknown_ground_truth": excluded_unknown_ground_truth,
            "correct": correct,
            "accuracy": _ratio(correct, evaluated),
            "confusion_matrix": matrix}


def floor_count_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    evaluated = excluded = exact = valid_prediction_count = missing_prediction = 0
    errors: list[float] = []
    for sample in samples:
        preds = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for building in sample.get("buildings", []):
            truth = building.get("floor_count")
            if truth is None:
                excluded += 1
                continue
            evaluated += 1
            pred = _prediction_for_entity(building, preds)
            value = ((pred.get("attributes") or {}).get("visible_floor_count", pred.get("visible_floors"))
                     if pred else None)
            try:
                numeric = int(value) if value is not None else None
            except (TypeError, ValueError):
                numeric = None
            if numeric is None:
                missing_prediction += 1
                continue
            valid_prediction_count += 1
            errors.append(abs(int(truth) - numeric))
            exact += int(int(truth) == numeric)
    return {"status": "evaluated" if evaluated else "not_evaluable",
            "evaluated": evaluated,
            "excluded_unknown_ground_truth": excluded,
            "missing_prediction": missing_prediction,
            "exact_matches": exact,
            "exact_accuracy": _ratio(exact, evaluated),
            "mae_evaluated": valid_prediction_count,
            "mean_absolute_error": round(statistics.mean(errors), 6) if errors else None}


def building_use_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pairs: list[tuple[str, str]] = []
    excluded = association_missing = 0
    for sample in samples:
        preds = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for building in sample.get("buildings", []):
            truth = building.get("building_use")
            if truth is None:
                excluded += 1
                continue
            pred = _prediction_for_entity(building, preds)
            if pred is None:
                pairs.append((str(truth), "__missing_prediction__"))
            else:
                attributes = pred.get("attributes") or {}
                value = attributes.get("building_use", pred.get("probable_use"))
                pairs.append((str(truth), str(value) if value is not None else "__missing_prediction__"))
    result = scalar_classification_metrics(pairs, excluded_unknown_ground_truth=excluded)
    result["association_missing"] = association_missing
    return result


def _levenshtein(first: Sequence[Any], second: Sequence[Any]) -> int:
    previous = list(range(len(second) + 1))
    for i, left in enumerate(first, 1):
        current = [i]
        for j, right in enumerate(second, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def ocr_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    exact = normalized = evaluated = excluded = 0
    cer_values: list[float] = []
    word_values: list[float] = []
    for sample in samples:
        predictions = predictions_by_image.get(str(sample["image_id"]), {}).get("ocr", [])
        by_region = {str(row.get("region_id", row.get("ocr_id", ""))): row for row in predictions}
        for label in sample.get("ocr", []):
            truth = label.get("ground_truth_text")
            if truth is None:
                excluded += 1
                continue
            evaluated += 1
            prediction = by_region.get(str(label.get("region_id")), {})
            raw_actual = prediction.get("raw_text", prediction.get("text"))
            raw_actual = str(raw_actual) if raw_actual is not None else ""
            exact += int(raw_actual == truth)
            clean_truth = normalize_ocr_text(truth)
            clean_actual = normalize_ocr_text(raw_actual)
            normalized += int(clean_actual == clean_truth)
            char_denominator = max(1, len(clean_truth))
            cer_values.append(_levenshtein(list(clean_truth), list(clean_actual)) / char_denominator)
            truth_words, actual_words = clean_truth.split(), clean_actual.split()
            word_denominator = max(1, len(truth_words))
            word_values.append(max(0.0, 1 - _levenshtein(truth_words, actual_words) / word_denominator))
    return {"status": "evaluated" if evaluated else "not_evaluable",
            "evaluated": evaluated, "excluded_unknown_ground_truth": excluded,
            "exact_match_count": exact, "exact_match_rate": _ratio(exact, evaluated),
            "normalized_match_count": normalized, "normalized_match_rate": _ratio(normalized, evaluated),
            "mean_character_error_rate": round(statistics.mean(cer_values), 6) if cer_values else None,
            "mean_word_level_accuracy": round(statistics.mean(word_values), 6) if word_values else None,
            "normalization": "Unicode NFKC plus whitespace collapse; case is preserved."}


def haversine_meters(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    lat1, lat2 = math.radians(float(first["latitude"])), math.radians(float(second["latitude"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(second["longitude"]) - float(first["longitude"]))
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))


def positioning_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[float] = []
    excluded = missing = 0
    for sample in samples:
        predicted = predictions_by_image.get(str(sample["image_id"]), {}).get("positioning", [])
        by_id = {str(row.get("entity_id")): row for row in predicted if row.get("entity_id") is not None}
        observations = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for label in sample.get("positioning", []):
            if label.get("latitude") is None or label.get("longitude") is None:
                excluded += 1
                continue
            entity_id = str(label.get("entity_id"))
            row = by_id.get(entity_id)
            if row is None:
                row = by_id.get(_associated_entity_id(sample, entity_id, observations))
            if row is None or row.get("latitude") is None or row.get("longitude") is None:
                missing += 1
                continue
            errors.append(haversine_meters(label, row))
    return {"status": "evaluated" if errors or missing else "not_evaluable",
            "evaluated": len(errors) + missing, "coordinate_pairs_evaluated": len(errors),
            "excluded_unknown_ground_truth": excluded, "missing_prediction": missing,
            "mean_error_meters": round(statistics.mean(errors), 4) if errors else None,
            "median_error_meters": round(statistics.median(errors), 4) if errors else None}


def reference_matching_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pairs: list[tuple[bool, bool]] = []
    excluded = 0
    for sample in samples:
        predicted = predictions_by_image.get(str(sample["image_id"]), {}).get("reference_matches", [])
        by_id = {str(row.get("entity_id")): row for row in predicted if row.get("entity_id") is not None}
        observations = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for label in sample.get("reference_matches", []):
            if label.get("matched") is None:
                excluded += 1
                continue
            entity_id = str(label.get("entity_id"))
            row = by_id.get(entity_id) or by_id.get(_associated_entity_id(sample, entity_id, observations))
            pairs.append((bool(label["matched"]), bool(row and row.get("matched"))))
    tp = sum(t and p for t, p in pairs)
    fp = sum(not t and p for t, p in pairs)
    fn = sum(t and not p for t, p in pairs)
    result = confusion_metrics(tp, fp, fn, evaluated=len(pairs), excluded_unknown_ground_truth=excluded)
    result.update({"matched_count": sum(truth for truth, _ in pairs),
                   "unmatched_count": sum(not truth for truth, _ in pairs)})
    return result


def discrepancy_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "evaluated": 0, "excluded": 0})
    for sample in samples:
        predictions = predictions_by_image.get(str(sample["image_id"]), {}).get("discrepancies", [])
        observations = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for label in sample.get("discrepancies", []):
            name = str(label.get("discrepancy_type"))
            entity_id = str(label.get("entity_id"))
            linked_ids = {entity_id, _associated_entity_id(sample, entity_id, observations)}
            row = next((item for item in predictions
                        if str(item.get("entity_id", item.get("observation_id", ""))) in linked_ids
                        and item.get("discrepancy_type") == name), None)
            if label.get("expected_present") is None:
                by_class[name]["excluded"] += 1
                continue
            by_class[name]["evaluated"] += 1
            truth, pred = bool(label["expected_present"]), row is not None
            by_class[name]["tp"] += int(truth and pred)
            by_class[name]["fp"] += int(not truth and pred)
            by_class[name]["fn"] += int(truth and not pred)
    return {name: confusion_metrics(value["tp"], value["fp"], value["fn"],
                                    evaluated=value["evaluated"],
                                    excluded_unknown_ground_truth=value["excluded"])
            for name, value in sorted(by_class.items())}


def review_metrics(samples: Sequence[Mapping[str, Any]], predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pairs: list[tuple[bool, bool]] = []
    excluded = 0
    for sample in samples:
        predictions = predictions_by_image.get(str(sample["image_id"]), {}).get("review_routing", [])
        by_id = {str(row.get("entity_id")): row for row in predictions if row.get("entity_id") is not None}
        observations = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for label in sample.get("review_routing", []):
            truth = label.get("review_required")
            if truth is None:
                excluded += 1
                continue
            entity_id = str(label.get("entity_id"))
            row = by_id.get(entity_id) or by_id.get(_associated_entity_id(sample, entity_id, observations))
            pairs.append((bool(truth), bool(row and row.get("review_required"))))
    tp = sum(t and p for t, p in pairs)
    fp = sum(not t and p for t, p in pairs)
    fn = sum(t and not p for t, p in pairs)
    result = confusion_metrics(tp, fp, fn, evaluated=len(pairs), excluded_unknown_ground_truth=excluded)
    result.update({"false_review_count": fp, "missed_review_count": fn})
    return result


def routing_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(records)
    local_routes = {"local", "small_model", "lightweight"}
    vlm_routes = {"vlm", "vlm_escalation"}
    local = sum(str(row.get("route") or row.get("model_route")) in local_routes for row in records)
    vlm = sum(str(row.get("route") or row.get("model_route")) in vlm_routes for row in records)
    errors = sum(str(row.get("route") or row.get("model_route")) in {"error", "unavailable"} for row in records)
    return {"status": "evaluated" if total else "not_evaluable", "total_processed": total,
            "routed_to_local_count": local, "routed_to_vlm_count": vlm,
            "unavailable_or_error_count": errors,
            "local_percentage": round(100 * local / total, 4) if total else None,
            "vlm_percentage": round(100 * vlm / total, 4) if total else None}


def routing_decision_metrics(samples: Sequence[Mapping[str, Any]],
                             predictions_by_image: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pairs: list[tuple[str, str]] = []
    excluded = 0
    for sample in samples:
        predicted = predictions_by_image.get(str(sample["image_id"]), {}).get("routing_decisions", [])
        by_id = {str(row.get("entity_id")): row for row in predicted if row.get("entity_id") is not None}
        observations = predictions_by_image.get(str(sample["image_id"]), {}).get("observations", [])
        for label in sample.get("review_routing", []):
            truth = label.get("expected_route")
            if truth is None:
                excluded += 1
                continue
            entity_id = str(label.get("entity_id"))
            row = by_id.get(entity_id) or by_id.get(_associated_entity_id(sample, entity_id, observations))
            predicted_route = str(row.get("route")) if row and row.get("route") is not None else "__missing_prediction__"
            pairs.append((str(truth), predicted_route))
    result = scalar_classification_metrics(pairs, excluded_unknown_ground_truth=excluded)
    result["metric_name"] = "expected routing-decision accuracy"
    return result


def latency_metrics(records: Sequence[Mapping[str, Any]], *, minimum_for_p95: int = 20) -> dict[str, Any]:
    values = [float(row["latency_ms"]) for row in records
              if row.get("latency_ms") is not None and float(row["latency_ms"]) >= 0]
    values.sort()
    p95 = values[math.ceil(0.95 * len(values)) - 1] if len(values) >= minimum_for_p95 else None
    return {"status": "evaluated" if values else "not_evaluable", "sample_count": len(values),
            "mean_latency_ms": round(statistics.mean(values), 4) if values else None,
            "median_latency_ms": round(statistics.median(values), 4) if values else None,
            "p95_latency_ms": round(p95, 4) if p95 is not None else None,
            "p95_reason": None if p95 is not None else f"At least {minimum_for_p95} measured samples are required."}


def cost_metrics(usage: Sequence[Mapping[str, Any]], pricing: Mapping[str, float] | None) -> dict[str, Any]:
    if not pricing:
        return {"status": "unavailable", "estimated_cost": None, "reason": "Pricing not configured."}
    if not usage:
        return {"status": "unavailable", "estimated_cost": None, "reason": "Invocation usage is unavailable."}
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in pricing.values()):
        return {"status": "unavailable", "estimated_cost": None,
                "reason": "Pricing inputs must be finite, non-negative values."}
    total = 0.0
    for row in usage:
        for name, count in (row.get("invocations") or {}).items():
            if count and name not in pricing:
                return {"status": "unavailable", "estimated_cost": None,
                        "reason": f"Pricing not configured for {name}."}
            if name in pricing and (pricing[name] < 0 or count < 0):
                return {"status": "unavailable", "estimated_cost": None,
                        "reason": "Pricing and invocation counts must be non-negative."}
            total += float(pricing.get(name, 0.0)) * int(count)
    return {"status": "available", "estimated_cost": round(total, 8), "currency": "USD",
            "reason": None, "pricing_source": "explicit evaluation input"}


def all_vlm_comparison(*, all_vlm_run: bool = False) -> dict[str, Any]:
    if not all_vlm_run:
        return {"all_vlm_run": False, "quality_comparison": "unavailable",
                "cost_comparison": "unavailable", "latency_comparison": "unavailable",
                "reason": "No all-VLM baseline has been executed."}
    return {"all_vlm_run": True, "quality_comparison": "not_evaluable",
            "cost_comparison": "not_evaluable", "latency_comparison": "not_evaluable",
            "reason": "Baseline prediction records must be supplied to compute comparisons."}

