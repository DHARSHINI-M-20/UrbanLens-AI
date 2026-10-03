"""Cloud Lambda entrypoint for simulated data processing and API Gateway reads."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import boto3
from botocore.exceptions import ClientError

DATASET_ID = "tn_study_area_demo_v1"
SIMULATION_SOURCE = "SIMULATED_TAMIL_NADU_DATA"
REFERENCE_SOURCE = "SIMULATED_PROPERTY_REGISTER"
SIMULATION_LABEL = "SIMULATED TAMIL NADU URBAN DATA - NOT REAL GOOGLE STREET VIEW DATA"
DEFAULT_REGION = "ap-south-1"
DEFAULT_TABLE = "fai-tce-team11-urbanlens-records"
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
_s3_client = None
_dynamodb_service = None
_bedrock_client = None

try:
    from bedrock_runtime import invoke_image, make_bedrock_runtime_client, normalize_single_result
except ModuleNotFoundError:
    from app.services.bedrock_runtime import invoke_image, make_bedrock_runtime_client, normalize_single_result

try:
    from dynamodb_service import DynamoDBService
except ModuleNotFoundError:
    from app.services.dynamodb_service import DynamoDBService

try:
    from challenge_query_rules import (
        commercial_over_two_floors, low_confidence_floor_reviews,
        routed_metrics_summary, streetlight_findings, unmatched_buildings_by_street, envelope as query_envelope,
    )
except ModuleNotFoundError:
    from app.services.challenge_queries import (
        commercial_over_two_floors, low_confidence_floor_reviews,
        routed_metrics_summary, streetlight_findings, unmatched_buildings_by_street, envelope as query_envelope,
    )


def _region() -> str:
    region = os.getenv("AWS_REGION", DEFAULT_REGION)
    if region != DEFAULT_REGION:
        raise ValueError(f"This function only supports AWS_REGION={DEFAULT_REGION}.")
    return region


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=_region())
    return _s3_client


def _get_dynamodb_service():
    global _dynamodb_service
    if _dynamodb_service is None:
        table = os.getenv("URBANLENS_DYNAMODB_TABLE")
        if not table:
            return None
        _dynamodb_service = DynamoDBService(table_name=table, region=_region())
    return _dynamodb_service


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = make_bedrock_runtime_client(region=_region())
    return _bedrock_client


def _response(status_code: int, payload: Any) -> dict[str, Any]:
    cors_origin = os.getenv("URBANLENS_CORS_ALLOW_ORIGIN") or "http://localhost:5173"
    parsed_origin = urlparse(cors_origin)
    if cors_origin != "*" and (parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc or parsed_origin.path):
        raise ValueError("URBANLENS_CORS_ALLOW_ORIGIN must be one explicit HTTP(S) origin.")
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": cors_origin,
            "access-control-allow-methods": "GET,OPTIONS",
            "access-control-allow-headers": "content-type",
        },
        "body": json.dumps(payload, separators=(",", ":"), default=str),
    }


def _query_result(name: str, records: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    limitations = extra.pop("limitations", [
        "SIMULATED DEMONSTRATION DATA — NOT REAL STREET VIEW DATA.",
        "Results describe only this supplied demo dataset.",
    ])
    return query_envelope(
        name, DATASET_ID, records, simulation=True,
        limitations=limitations, **extra,
    )


def _log(event_name: str, **fields: Any) -> None:
    LOGGER.info(json.dumps({"event": event_name, **fields}, separators=(",", ":"), default=str))


def _emit_metrics(*, duration_ms: float, records: int, bedrock_calls: int, bedrock_attempts: int, bedrock_ms: float,
                  ddb_writes: int, errors: int) -> None:
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "UrbanLens/Task5",
                "Dimensions": [["FunctionName", "DatasetId"]],
                "Metrics": [
                    {"Name": "ProcessingCount", "Unit": "Count"},
                    {"Name": "ProcessingLatency", "Unit": "Milliseconds"},
                    {"Name": "ProcessedRecordCount", "Unit": "Count"},
                    {"Name": "BedrockInvocationCount", "Unit": "Count"},
                    {"Name": "BedrockAttemptCount", "Unit": "Count"},
                    {"Name": "BedrockLatency", "Unit": "Milliseconds"},
                    {"Name": "DynamoDBWriteCount", "Unit": "Count"},
                    {"Name": "ProcessingErrorCount", "Unit": "Count"},
                ],
            }],
        },
        "FunctionName": os.getenv("AWS_LAMBDA_FUNCTION_NAME", "urbanlens-demo-processor"),
        "DatasetId": DATASET_ID,
        "ProcessingCount": 1,
        "ProcessingLatency": round(duration_ms, 3),
        "ProcessedRecordCount": records,
        "BedrockInvocationCount": bedrock_calls,
        "BedrockAttemptCount": bedrock_attempts,
        "BedrockLatency": round(bedrock_ms, 3),
        "DynamoDBWriteCount": ddb_writes,
        "ProcessingErrorCount": errors,
    }, separators=(",", ":")))


def _extract_structured_response(response: dict[str, Any]) -> dict[str, Any]:
    content = response.get("output", {}).get("message", {}).get("content", [])
    text = next((item.get("text") for item in content if isinstance(item, dict) and item.get("text")), None)
    if not isinstance(text, str):
        raise ValueError("Nova Lite returned no structured text.")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Nova Lite response did not contain a JSON object.")
    return normalize_single_result(json.loads(text[start:end + 1]))


def _is_hard_case(record: dict[str, Any]) -> bool:
    if record.get("asset_type") != "building":
        return False
    attributes = record.get("attributes") or {}
    confidence = float(record.get("confidence") or 0)
    use = attributes.get("building_use")
    floors = attributes.get("visible_floor_count")
    return confidence < 0.7 or floors is None or use in {None, "unknown"}


def _nearest_street_id(reference: dict[str, Any], observations: list[dict[str, Any]]) -> str:
    candidates = [record for record in observations if record.get("street_id")
                  and record.get("latitude") is not None and record.get("longitude") is not None]
    if not candidates or reference.get("latitude") is None or reference.get("longitude") is None:
        return "Unassigned"
    lat1, lon1 = float(reference["latitude"]), float(reference["longitude"])
    def distance(record: dict[str, Any]) -> float:
        lat2, lon2 = float(record["latitude"]), float(record["longitude"])
        dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        arc = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, arc)))
    return str(min(candidates, key=distance).get("street_id") or "Unassigned")


def _escalate_at_most_one(records: list[dict[str, Any]], *, bucket: str, prefix: str,
                          s3_client: Any, ddb: Any, bedrock_client: Any | None) -> tuple[int, float, str]:
    if os.getenv("URBANLENS_LAMBDA_BEDROCK_ENABLED", "false").lower() != "true":
        return 0, 0.0, "disabled"
    candidate = next((record for record in records if _is_hard_case(record)), None)
    if candidate is None:
        return 0, 0.0, "no_ambiguous_cases"

    observation_id = str(candidate.get("observation_id") or "")
    if ddb is not None:
        try:
            existing = ddb.get_records(DATASET_ID, collection="observations")
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            state = "blocked" if code in {"AccessDeniedException", "AccessDenied"} else "failed"
            candidate["bedrock_review"] = {"status": state, "error_code": code, "reason": "dynamodb_read_before_escalation"}
            return 0, 0.0, "dynamodb_blocked"
        cached = next((record for record in existing if record.get("observation_id") == observation_id), None)
        if cached and (cached.get("bedrock_review") or {}).get("status") == "success":
            candidate["bedrock_review"] = cached["bedrock_review"]
            return 0, float(cached["bedrock_review"].get("latency_ms") or 0), "already_reviewed"

    view_id = candidate.get("source_view_id")
    if not view_id:
        candidate["bedrock_review"] = {"status": "skipped", "reason": "missing_source_view_id"}
        return 0, 0.0, "missing_source_view_id"
    image_key = f"{prefix}/{DATASET_ID}/evidence/{view_id}.png"
    response = s3_client.get_object(Bucket=bucket, Key=image_key)
    image_metadata = {str(key).lower(): str(value) for key, value in response.get("Metadata", {}).items()}
    if image_metadata.get("dataset_id") != DATASET_ID or image_metadata.get("simulation") != "true" or image_metadata.get("source") != SIMULATION_SOURCE:
        raise ValueError("Synthetic evidence provenance failed validation.")
    body = response["Body"]
    try:
        image_bytes = body.read()
    finally:
        body.close()
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Evidence object is not a valid PNG.")

    started = time.perf_counter()
    profile = os.getenv("BEDROCK_INFERENCE_PROFILE", "apac.amazon.nova-lite-v1:0")
    try:
        model_response, latency_ms = invoke_image(
            bedrock_client or _get_bedrock_client(),
            model_id=profile,
            prompt=(
                "This is a synthetic demonstration image, not Google Street View. "
                "Assess only the shown building. Return JSON with building_use, visible_floor_count, confidence, "
                "uncertainty_indicators, and reasoning_summary. Existing detection attributes: "
                + json.dumps(candidate.get("attributes") or {}, default=str)
            ),
            image_bytes=image_bytes,
            image_format="png",
            max_tokens=256,
            temperature=0.1,
        )
        structured = _extract_structured_response(model_response)
        candidate["bedrock_review"] = {
            "status": "success",
            "model_name": profile,
            "aws_service": "Amazon Bedrock Runtime",
            "processing_route": "bedrock_nova_lite_escalation",
            "confidence": structured.get("confidence"),
            "latency_ms": latency_ms,
            "estimated_cost": None,
            "cost_status": "unavailable",
            "simulation": True,
            "dataset_id": DATASET_ID,
            "observation_id": observation_id,
            "result": structured,
        }
        candidate["model_name"] = profile
        candidate["processing_route"] = "bedrock_nova_lite_escalation"
        candidate["latency_ms"] = latency_ms
        candidate["estimated_cost"] = None
        candidate["cost_status"] = "unavailable"
        return 1, latency_ms, "success"
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
        state = "blocked" if code in {"AccessDeniedException", "AccessDenied"} else "failed"
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        candidate["bedrock_review"] = {
            "status": state, "error_code": code, "model_name": profile,
            "aws_service": "Amazon Bedrock Runtime", "processing_route": "bedrock_nova_lite_escalation",
            "latency_ms": latency_ms, "estimated_cost": None, "cost_status": "unavailable", "simulation": True,
        }
        return 0, latency_ms, state
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        candidate["bedrock_review"] = {
            "status": "failed", "error_code": type(exc).__name__, "model_name": profile,
            "processing_route": "bedrock_nova_lite_escalation", "latency_ms": latency_ms,
            "estimated_cost": None, "cost_status": "unavailable", "simulation": True,
        }
        return 0, latency_ms, "failed"


def _log_api(path: str, method: str, status: int, duration_ms: float, count: int = 0) -> None:
    _log("api_request", dataset_id=DATASET_ID, path=path, method=method, status_code=status,
         duration_ms=round(duration_ms, 3), record_count=count, simulation=True)


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        label = str(value or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _query_api(event: dict[str, Any], *, s3_client: Any | None = None,
               dynamodb_service: Any | None = None) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    method = str(request_context.get("http", {}).get("method") or event.get("httpMethod") or "GET").upper()
    path = str(event.get("rawPath") or event.get("path") or "/").rstrip("/") or "/"
    query = event.get("queryStringParameters") or {}
    raw_query = event.get("rawQueryString") or ""
    if raw_query and not query:
        query = {key: values[-1] for key, values in parse_qs(raw_query).items()}
    if method == "OPTIONS":
        return _response(204, {})
    if method != "GET":
        return _response(405, {"detail": "Cloud API is read-only."})
    if query.get("dataset_id", DATASET_ID) != DATASET_ID:
        return _response(400, {"detail": f"Only dataset {DATASET_ID} is available."})

    started = time.perf_counter()
    if path == "/health":
        response = _response(200, {"status": "ok", "service": "UrbanLens AI cloud processor"})
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000)
        return response

    if path == "/aws/status":
        ddb = dynamodb_service or _get_dynamodb_service()
        dynamodb_status = ddb.get_status() if ddb else {
            "configured": False, "table": None, "exists": None, "status": None, "item_count": None,
        }
        api_id = os.getenv("URBANLENS_API_GATEWAY_ID")
        payload = {
            "aws_configured": True,
            "region": _region(),
            "profile": os.getenv("AWS_PROFILE"),
            "s3": {"configured": bool(os.getenv("URBANLENS_S3_BUCKET")), "bucket": os.getenv("URBANLENS_S3_BUCKET")},
            "lambda": {"configured": True, "function": os.getenv("AWS_LAMBDA_FUNCTION_NAME")},
            "dynamodb": {**dynamodb_status, "tables": [dynamodb_status["table"]] if dynamodb_status.get("exists") else []},
            "bedrock": {"configured": True, "region": _region(),
                        "inference_profile": os.getenv("BEDROCK_INFERENCE_PROFILE", "apac.amazon.nova-lite-v1:0"),
                        "lambda_enabled": os.getenv("URBANLENS_LAMBDA_BEDROCK_ENABLED", "false").lower() == "true"},
            "api_gateway": {"configured": bool(api_id), "api_id": api_id, "url": os.getenv("URBANLENS_API_GATEWAY_URL")},
            "cloudwatch": {"configured": True,
                           "log_group": f"/aws/lambda/{os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'urbanlens-demo-processor')}"},
        }
        response = _response(200, payload)
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000)
        return response

    if path == "/study-area":
        bucket = os.getenv("URBANLENS_S3_BUCKET")
        if not bucket:
            return _response(503, {"detail": "S3 is not configured."})
        prefix = os.getenv("URBANLENS_S3_PREFIX", "urbanlens/datasets").strip("/")
        key = f"{prefix}/{DATASET_ID}/study_area/Study_area.geojson"
        body = (s3_client or _get_s3_client()).get_object(Bucket=bucket, Key=key)["Body"]
        try:
            geometry = json.loads(body.read())
        finally:
            body.close()
        payload = {
            "metadata": {"study_area_id": "challenge_study_area", "source": "data/Study_Area/Study_area.geojson",
                         "provenance": "Official challenge boundary; authoritative geometry only."},
            "geojson": geometry,
        }
        response = _response(200, payload)
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000)
        return response

    ddb = dynamodb_service or _get_dynamodb_service()
    if ddb is None:
        response = _response(503, {"detail": "DynamoDB is not configured."})
        _log_api(path, method, 503, (time.perf_counter() - started) * 1000)
        return response

    if path in {"/datasets", "/demo/status"}:
        datasets = ddb.get_records(DATASET_ID, collection="demo_datasets")
        dataset = datasets[0] if datasets else {
            "dataset_id": DATASET_ID, "simulation": True, "source": SIMULATION_SOURCE,
            "status": "not_synchronized", "label": SIMULATION_LABEL,
        }
        response = _response(200, {"seeded": bool(datasets), "dataset": dataset, "dataset_id": DATASET_ID, "simulation": True})
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(datasets))
        return response

    if path == "/demo/runs":
        items = ddb.get_records(DATASET_ID, collection="processing_metrics")
        runs = [{"run_id": item.get("processing_id") or item.get("view_id"),
                 "dataset_id": DATASET_ID, "status": "simulated", "simulation": True,
                 "started_at": item.get("timestamp"), "completed_at": item.get("timestamp"),
                 "processed_views": 1, "metrics": item,
                 "provenance": item.get("provenance") or SIMULATION_LABEL} for item in items[:100]]
        return _response(200, runs)

    collection_routes = {
        "/streets": "streets", "/sampling/points": "sampling_points", "/panoramas": "panoramas",
        "/views": "views", "/observations": "observations", "/observations/ocr": "ocr_observations",
        "/references": "reference_records", "/matching": "matches", "/discrepancies": "discrepancies",
        "/reviews": "review_queue", "/metrics": "processing_metrics",
    }
    if path in collection_routes:
        records = ddb.get_records(DATASET_ID, collection=collection_routes[path])
        response = _response(200, records)
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
        return response

    observations = ddb.get_records(DATASET_ID, collection="observations")
    discrepancies = ddb.get_records(DATASET_ID, collection="discrepancies")
    reviews = ddb.get_records(DATASET_ID, collection="review_queue")
    metrics = sorted(ddb.get_records(DATASET_ID, collection="processing_metrics"),
                     key=lambda item: str(item.get("view_id") or item.get("metric_id") or ""))
    references = ddb.get_records(DATASET_ID, collection="reference_records")
    if path == "/buildings":
        records = [record for record in observations if record.get("asset_type") == "building"]
    elif path == "/assets":
        records = [record for record in observations if record.get("asset_type") != "building"]
    elif path in {"/analytics", "/analytics/summary"}:
        match_statuses = [str(record.get("match_status", "unmatched")) for record in observations]
        asset_counts = _counts(record.get("asset_type") or record.get("entity_type") or "other" for record in observations)
        use_counts = _counts((record.get("attributes") or {}).get("building_use") or record.get("probable_use") or "unknown"
                             for record in observations if record.get("asset_type", record.get("entity_type")) == "building")
        floor_counts = _counts((record.get("attributes") or {}).get("visible_floor_count", record.get("visible_floors"))
                               if (record.get("attributes") or {}).get("visible_floor_count", record.get("visible_floors")) is not None else "unknown"
                               for record in observations if record.get("asset_type", record.get("entity_type")) == "building")
        match_counts = _counts(match_statuses)
        discrepancy_by_street = _counts(record.get("street_id") or "Unassigned" for record in discrepancies)
        metric_latency = [float(record.get("latency_ms") or 0) for record in metrics]
        payload = {
            "dataset_id": DATASET_ID, "simulation": True, "label": SIMULATION_LABEL,
            "streets_covered": len(ddb.get_records(DATASET_ID, collection="streets")),
            "buildings_analysed": sum(record.get("asset_type", record.get("entity_type")) == "building" for record in observations),
            "unmatched_properties": sum(status in {"unmatched", "possible_match", "mismatch"} for status in match_statuses),
            "streetlights_detected": int(asset_counts.get("streetlight", 0)),
            "electric_poles_detected": int(asset_counts.get("electric_pole", 0)),
            "discrepancy_count": len(discrepancies),
            "reviews_pending": sum(record.get("status") in {"pending", "needs_review"} for record in reviews),
            "low_confidence_count": sum(record.get("confidence") is not None and float(record["confidence"]) < 0.7 for record in observations),
            "low_confidence_observations": sum(record.get("confidence") is not None and float(record["confidence"]) < 0.7 for record in observations),
            "confidence_unavailable_count": sum(record.get("confidence") is None for record in observations),
            "building_use_distribution": use_counts,
            "floor_distribution": floor_counts,
            "asset_type_distribution": asset_counts,
            "match_status_distribution": match_counts,
            "discrepancies_by_street": discrepancy_by_street,
            "processing_route_distribution": _counts(record.get("model_route", record.get("processing_route")) for record in metrics),
            "processing_metrics": {"total_views": len(metrics),
                "average_latency_ms": round(sum(metric_latency) / len(metric_latency), 2) if metric_latency else 0,
                "total_latency_ms": round(sum(metric_latency), 2), "cost_status": "unavailable",
                "estimated_total_cost": None,
                "simulated_fixture_invocation_count": sum(int(record.get("simulated_fixture_invocation_count", 0) or 0) for record in metrics),
                "actual_invocation_count": sum(int(record.get("actual_invocation_count", 0) or 0) for record in metrics)},
            "processing_cost_message": "Cost unavailable unless verified provider pricing is configured.",
        }
        response = _response(200, payload)
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(observations))
        return response
    elif path == "/metrics/summary":
        response = _response(200, {
            "dataset_id": DATASET_ID, "simulation": True,
            "processing_route_distribution": _counts(record.get("model_route", record.get("processing_route")) for record in metrics),
            "workflow_cost_comparison": {"workflow": "proposed_routed_workflow", "estimated_total_cost": None,
                "all_selected_views_to_vlm_cost": None, "all_vlm_cost_status": "unavailable",
                "all_vlm_cost_unavailable_reasons": ["Verified provider pricing is not configured."],
                "comparison_note": "No AWS costs are inferred; no all-VLM model run is claimed."},
            "records": metrics,
        })
    elif path == "/queries/routed-vs-all-vlm":
        response = _response(200, _query_result("routed_vs_all_vlm", metrics,
            measured_routed_metrics=routed_metrics_summary(metrics),
            hypothetical_all_vlm_estimate={"status": "NOT_RUN", "cost_status": "unavailable", "estimated_cost": None},
            all_vlm_run_performed=False, all_vlm_status="NOT_RUN",
            quality_comparison_status="NOT_EVALUABLE", cost_status="unavailable",
            limitations=["No all-VLM baseline was executed.", "Verified provider pricing is unavailable; no cost or quality savings are claimed."]))
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(metrics))
        return response
    elif path.startswith("/queries/observations-by-street/"):
        street_id = path.rsplit("/", 1)[-1]
        records = ddb.get_records(DATASET_ID, collection="observations", street_id=street_id)
    elif path in {"/queries/buildings-over-2-floors-without-match", "/queries/commercial-buildings-without-match"}:
        records = commercial_over_two_floors(observations)
        response = _response(200, _query_result("commercial_buildings_over_two_floors_without_match", records,
            limitations=["No match means no match in supplied references, not evidence that no official property record exists."]))
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
        return response
    elif path == "/queries/streets-without-streetlights":
        records = streetlight_findings(discrepancies, references, observations)
        for record in records:
            if record.get("street_id") == "Unassigned":
                ref = next((item for item in references
                            if str(item.get("reference_id")) == str(record.get("reference_id"))), {})
                record["street_id"] = _nearest_street_id(ref, observations)
        response = _response(200, _query_result("streets_without_streetlight_within_interval", records,
            interval_meters=25, limitations=["Only records declaring complete coverage are eligible. Expected/observed labels come from stored discrepancies; no complete real inventory is available."]))
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
        return response
    elif path == "/queries/low-confidence-floor-counts":
        threshold = float(os.getenv("FLOOR_COUNT_CONFIDENCE_THRESHOLD", "0.7"))
        if not 0 <= threshold <= 1:
            return _response(500, {"detail": "FLOOR_COUNT_CONFIDENCE_THRESHOLD must be between 0 and 1."})
        records = low_confidence_floor_reviews(observations, reviews, threshold)
        response = _response(200, _query_result("low_confidence_floor_counts_requiring_review", records,
            confidence_threshold=threshold,
            limitations=["Confidence is not a calibrated accuracy probability."]))
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
        return response
    elif path in {"/queries/unmatched-buildings-by-street", "/queries/unmatched-buildings-assets"}:
        grouped = unmatched_buildings_by_street(observations)
        records = [record for grouped_records in grouped.values() for record in grouped_records]
        response = _response(200, _query_result("unmatched_buildings_grouped_by_street", records,
            by_street=grouped, limitations=["Unmatched status is relative to the synchronized references."]))
        _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
        return response
    elif path == "/queries/review-queue":
        records = reviews
    else:
        response = _response(404, {"detail": "Cloud route not found."})
        _log_api(path, method, 404, (time.perf_counter() - started) * 1000)
        return response

    response = _response(200, records)
    _log_api(path, method, 200, (time.perf_counter() - started) * 1000, len(records))
    return response


def _process_s3_object(event: dict[str, Any], context: Any, *, s3_client: Any | None,
                       dynamodb_service: Any | None, bedrock_client: Any | None) -> dict[str, Any]:
    started = time.perf_counter()
    if not isinstance(event, dict) or event.get("dataset_id") != DATASET_ID:
        raise ValueError(f"dataset_id must be {DATASET_ID}.")
    bucket, key = event.get("bucket"), event.get("key")
    configured_bucket = os.getenv("URBANLENS_S3_BUCKET")
    prefix = os.getenv("URBANLENS_S3_PREFIX", "urbanlens/datasets").strip("/")
    if not isinstance(bucket, str) or not bucket or (configured_bucket and bucket != configured_bucket):
        raise ValueError("bucket must match the configured UrbanLens bucket.")
    if not isinstance(key, str) or not key.startswith(f"{prefix}/{DATASET_ID}/") or ".." in key.split("/") or "\\" in key:
        raise ValueError("key must be under the configured dataset prefix.")

    s3 = s3_client or _get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    metadata = {str(name).lower(): str(value) for name, value in obj.get("Metadata", {}).items()}
    source = metadata.get("source")
    if metadata.get("dataset_id") != DATASET_ID or metadata.get("simulation") != "true":
        raise ValueError("S3 metadata does not identify the simulated dataset.")
    if source not in {SIMULATION_SOURCE, REFERENCE_SOURCE}:
        raise ValueError("S3 provenance source is not an approved simulation source.")
    body = obj["Body"]
    try:
        raw = body.read()
    finally:
        body.close()
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("dataset_id") != DATASET_ID or data.get("simulation") is not True:
        raise ValueError("S3 payload does not identify the expected simulated dataset.")
    if data.get("source") != source or data.get("real_google_street_view") is True:
        raise ValueError("S3 payload provenance does not match its metadata.")
    records = data.get("records") if isinstance(data.get("records"), list) else [data]
    if any(not isinstance(record, dict) or record.get("dataset_id", DATASET_ID) != DATASET_ID for record in records):
        raise ValueError("Every S3 record must belong to the expected dataset.")

    for record in records:
        record.setdefault("dataset_id", DATASET_ID)
        record.setdefault("simulation", True)
        record.setdefault("source", source)
        record.setdefault("provenance", data.get("provenance", SIMULATION_LABEL))
        record.setdefault("entity_type", record.get("asset_type", "observation"))
        record.setdefault("processing_route", record.get("model_route", "small_model"))
        record.setdefault("model_name", record.get("detector_type", "simulated_fixture"))
        record.setdefault("aws_service", "AWS Lambda")
        record.setdefault("latency_ms", record.get("processing_time_ms"))
        record.setdefault("estimated_cost", None)
        record.setdefault("cost_status", "unavailable")

    ddb = dynamodb_service or _get_dynamodb_service()
    bedrock_calls, bedrock_latency, bedrock_status = _escalate_at_most_one(
        records, bucket=bucket, prefix=prefix, s3_client=s3, ddb=ddb, bedrock_client=bedrock_client,
    )
    bedrock_attempts = int(bedrock_status in {"success", "blocked", "failed"})
    content_hash = hashlib.sha256(raw).hexdigest()
    run_summary = {
        "dataset_id": DATASET_ID, "simulation": True, "source": source,
        "provenance": data.get("provenance", SIMULATION_LABEL), "record_count": len(records),
        "bedrock_invocations": bedrock_calls, "bedrock_invocation_attempts": bedrock_attempts,
        "bedrock_status": bedrock_status,
        "bedrock_latency_ms": bedrock_latency, "processing_route": "s3_lambda_dynamodb",
        "model_name": os.getenv("BEDROCK_INFERENCE_PROFILE", "apac.amazon.nova-lite-v1:0") if bedrock_calls else "simulated_fixture",
        "estimated_cost": None, "cost_status": "unavailable", "processing_id": hashlib.sha256(f"{bucket}/{key}/{content_hash}".encode()).hexdigest(),
        "s3_bucket": bucket, "s3_key": key, "sha256": content_hash,
    }
    ddb_status, ddb_writes, ddb_error = "not_configured", 0, None
    if ddb is not None:
        try:
            ddb_writes = ddb.put_records(DATASET_ID, "observations", records)
            ddb_writes += ddb.put_records(DATASET_ID, "processing_metrics", [run_summary])
            ddb_status = "success"
        except ClientError as exc:
            ddb_error = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            ddb_status = "blocked" if ddb_error in {"AccessDenied", "AccessDeniedException"} else "failed"

    duration = round((time.perf_counter() - started) * 1000, 3)
    status = "success" if ddb_status == "success" else "partial" if ddb_status == "not_configured" else "failed"
    result = {
        "status": status, "dataset_id": DATASET_ID, "simulation": True, "source": source,
        "bucket": bucket, "key": key, "processed_object": key, "record_count": len(records),
        "object_bytes": len(raw), "sha256": content_hash, "processing_time_ms": duration,
        "bedrock": {"status": bedrock_status, "invocations": bedrock_calls, "attempts": bedrock_attempts,
                "latency_ms": bedrock_latency,
                    "inference_profile": os.getenv("BEDROCK_INFERENCE_PROFILE", "apac.amazon.nova-lite-v1:0")},
        "dynamodb": {"status": ddb_status, "writes": ddb_writes,
                     "table": os.getenv("URBANLENS_DYNAMODB_TABLE"), "error_code": ddb_error},
        "processing_id": run_summary["processing_id"],
        "message": "Validated simulated records; at most one ambiguous image is sent to Nova Lite when enabled.",
        "provenance": {"dataset_id": DATASET_ID, "source": source, "simulation": True, "real_google_street_view": False},
    }
    _log("s3_object_processed", aws_request_id=getattr(context, "aws_request_id", None), dataset_id=DATASET_ID,
         bucket=bucket, key=key, record_count=len(records), status=status, dynamodb_status=ddb_status,
            bedrock_status=bedrock_status, bedrock_invocation_attempts=bedrock_attempts, simulation=True)
    _emit_metrics(duration_ms=duration, records=len(records), bedrock_calls=bedrock_calls,
                   bedrock_attempts=bedrock_attempts, bedrock_ms=bedrock_latency,
                   ddb_writes=ddb_writes, errors=int(status == "failed"))
    return result


def handler(event: dict[str, Any], context: Any, *, s3_client: Any | None = None,
            dynamodb_service: Any | None = None, bedrock_client: Any | None = None) -> dict[str, Any]:
    _region()
    if isinstance(event, dict) and ("requestContext" in event or "httpMethod" in event):
        try:
            return _query_api(event, s3_client=s3_client, dynamodb_service=dynamodb_service)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "AWSClientError"))
            status = 503 if code in {"AccessDenied", "AccessDeniedException", "ResourceNotFoundException"} else 502
            return _response(status, {"detail": "Cloud service unavailable.", "error_code": code})
        except Exception as exc:
            return _response(500, {"detail": "Cloud request failed.", "error_code": type(exc).__name__})
    try:
        return _process_s3_object(event, context, s3_client=s3_client,
                                  dynamodb_service=dynamodb_service, bedrock_client=bedrock_client)
    except Exception as exc:
        code = str(exc.response.get("Error", {}).get("Code", type(exc).__name__)) if isinstance(exc, ClientError) else type(exc).__name__
        _log("s3_processing_failed", dataset_id=DATASET_ID, error_code=code, simulation=True)
        _emit_metrics(duration_ms=0, records=0, bedrock_calls=0, bedrock_attempts=0,
                  bedrock_ms=0, ddb_writes=0, errors=1)
        raise
