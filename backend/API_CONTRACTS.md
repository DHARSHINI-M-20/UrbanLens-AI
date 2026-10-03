# Local and cloud API contract notes

Both implementations are dataset-scoped and serve the same simulated demo dataset in demo mode. Local FastAPI reads MongoDB; the API Gateway Lambda reads DynamoDB. Their storage and implementation are intentionally separate.

## Frontend-facing read collections

| Endpoint | Local response | Cloud response | Frontend expectation | Difference found / target contract |
|---|---|---|---|---|
| `/demo/status` | Object with `seeded`, `dataset_id`, optional dataset/counts, `simulation` | Object with `seeded`, dataset and simulation; no collection counts | `seeded` controls empty/seeded UX; simulation label remains visible | Local has extra optional counts. Target: same required fields, optional `dataset` and `counts`. |
| `/study-area` | `{metadata,geojson}` from official boundary service | `{metadata,geojson}` loaded from S3 | FeatureCollection plus source metadata | Metadata wording differs by source; target preserves `metadata` and exact `geojson` semantics while retaining source attribution. |
| `/streets`, `/sampling/points`, `/panoramas`, `/views` | Arrays of dataset-scoped records | Arrays of records from the fixed cloud dataset | Arrays with `street_id`, `sample_id`, `panorama_id`, or `view_id` and available geometry/coordinates | Local supports selected dataset; cloud only serves the fixed demo dataset. Target: arrays with matching identifiers/field meaning and explicit dataset provenance. |
| `/observations` | Array of MongoDB observations | Array of DynamoDB observations | Observation IDs, attributes, confidence, coordinates, route, match and provenance fields | Storage-specific metadata may differ and optional fields may be missing. Target: preserve domain fields; omit unavailable values rather than synthesize defaults. |
| `/observations/ocr` | Array of OCR observation records | Array from `ocr_observations` collection | OCR record IDs, raw/normalized text, confidence, source | Optional text names vary by provider. Target: preserve raw and normalized values; frontend handles absent optional values. |
| `/references`, `/matching`, `/discrepancies`, `/reviews` | Arrays of persisted domain records | Arrays of synchronized domain records | Reference/match/discrepancy/review identifiers plus source, status and provenance | Local and cloud datasets are fixed/scoped differently; status strings remain source values. Target: arrays with semantically stable field meanings and no status rewriting by the API. |
| `/metrics` | Array of per-view pipeline metric records | Array of synchronized processing metric records | Route, latency, invocation and cost availability fields | Metric granularity may be per view locally or cloud processing object; target keeps explicit IDs/timestamps and never reports unavailable cost as zero. |
| `/analytics/summary` | Aggregate object with distributions, low-confidence count and processing metrics | Now returns the same KPI/distribution keys, with cloud-supported aggregates and explicit unavailable cost | Numeric KPI fields and distribution objects; missing values render unavailable/empty | Previously cloud omitted several chart distributions. Target: same aggregate keys; source-specific unsupported details are null/unavailable, never fabricated. |
| `/demo/runs` | Persisted MongoDB processing-run records | Persisted Lambda processing metric records adapted to run summaries | Array of stored runs; simulation state and timestamp are shown | Cloud records are per processing metric/object rather than the local batch run. Target: explicit IDs, timestamps, `status=simulated`, and only persisted records. |

## Challenge queries

All five routes are `GET` endpoints. Local FastAPI accepts an optional `dataset_id` matching `[A-Za-z0-9_:-]{1,128}` and defaults to `tn_study_area_demo_v1`; Mongo reads are additionally scoped to `challenge_study_area`. The Lambda handler accepts the same query name/path but is fixed to `tn_study_area_demo_v1`; it does **not** provide arbitrary cloud dataset selection. The frontend always sends the fixed demo ID in either mode.

The common response envelope is `{query_name, dataset_id, simulation, result_count, generated_at, run_id, records, provenance, limitations}`. `run_id` is currently null. `records` is always an array. `simulation` identifies the source dataset, including when a query has no matching rows. The shared pure filtering rules are bundled with the cloud handler; MongoDB/DynamoDB storage adapters remain separate. Ordering is deterministic by stable observation/discrepancy ID; grouped output orders street keys and rows. Current seeded data is synthetic.

| Query | Local endpoint / cloud handler operation | Request/default | Filtering and unknown semantics | Additional response fields | Provenance and limitation |
|---|---|---|---|---|---|
| Commercial buildings >2 floors without match | `GET /queries/buildings-over-2-floors-without-match` / same API Gateway path | Optional `dataset_id`; default above | Building; commercial use; finite whole-number floors >2; explicit `match_status=unmatched`. Missing/unknown status, fractional floors, and missing floors are excluded. | None | “No match” is only within supplied references, not evidence that no official property record exists. |
| Expected streetlights without an observed match | `GET /queries/streets-without-streetlights` / same API Gateway path | Optional `dataset_id`; fixed 25 m interval | Requires a stored `expected_streetlight_not_observed` discrepancy linked to a streetlight reference whose `coverage_status` is `complete` or `simulated_complete`. Unknown/incomplete coverage is excluded. Query labels distinguish expected and observed condition; the distance result comes from stored discrepancy processing. | `interval_meters`; records include `coverage_status`, `coverage_complete`, `expected_asset_condition`, `observed_asset_condition` | Current reference coverage is synthetic. Query does not infer absence from an incomplete inventory. |
| Low-confidence floors pending review | `GET /queries/low-confidence-floor-counts` / same API Gateway path | Optional `dataset_id`; threshold defaults to `FLOOR_COUNT_CONFIDENCE_THRESHOLD` (0.7), separately configured in local/cloud environment | Requires finite whole-number floors, finite confidence in [0,1] strictly below threshold, and review status `pending` or `needs_review`. Unknown floors/confidence are excluded. | `confidence_threshold` | Provider confidence is not calibrated accuracy probability. |
| Unmatched buildings by street | `GET /queries/unmatched-buildings-by-street` / same API Gateway path | Optional `dataset_id` locally; fixed cloud dataset | Building with explicit `match_status=unmatched`; missing/unknown status is excluded. Missing street ID is grouped under `Unassigned`. | `by_street` maps street IDs to records; `records` is the flattened ordered list | Unmatched is relative to the supplied references. |
| Routed vs all-VLM | `GET /queries/routed-vs-all-vlm` / same API Gateway path | Optional `dataset_id`; no run controls | Reads stored routed metrics. It never runs all-VLM. Missing latency/cost stays unavailable. | `measured_routed_metrics`, `hypothetical_all_vlm_estimate` with `status=NOT_RUN`, `all_vlm_run_performed=false`, `all_vlm_status=NOT_RUN`, `quality_comparison_status=NOT_EVALUABLE`, `cost_status` | Metrics from the seeded dataset are synthetic; no quality/cost savings are claimed. |

Current query routes:

- `/queries/buildings-over-2-floors-without-match` (commercial buildings only)
- `/queries/streets-without-streetlights`
- `/queries/low-confidence-floor-counts`
- `/queries/unmatched-buildings-by-street`
- `/queries/routed-vs-all-vlm`

Legacy query route names remain available as aliases where applicable. Cloud route code is present and covered by fake-DynamoDB handler tests; actual API Gateway deployment and live cloud response contracts have not been verified by those tests.

## Review decisions

Local `PATCH /reviews/{review_id}/decision` remains backward compatible with status/reviewer fields and additionally accepts optional `corrected_attributes` and `reviewer_note`. Corrections are stored as `{original, corrected}` pairs on the review record; the source observation is left unchanged. Cloud review reads remain GET-only.

## Collection pagination

The current collection API responses remain arrays for compatibility. Local endpoints apply route-specific caps (for example, observations/references/discrepancies are capped at 5,000; review records at 1,000; panoramas at 500); cloud DynamoDB reads currently return the fixed dataset collection. No shared `page/page_size/total/items` server-cursor contract exists. The frontend’s table pagination is client-side over the records returned by those bounded APIs and must not be described as full-dataset/server pagination.

## Overlapping service modules

These files are intentionally retained; names alone were not used to delete or consolidate code.

| Pair | Current call-site evidence | Interpretation |
|---|---|---|
| `geo_service.py` / `geospatial_service.py` | `geo_service.py` has internal geometry parsing/corridor helpers but no application import was found; `GeospatialService` is exercised by a member pipeline test, with no current API/service import found. Official production study-area checks currently use `study_area_service.py`. | Distinct helper/class responsibilities, but both are outside active API calls found in this audit. Cleanup needs focused ownership/test review. |
| `matching_service.py` / `reference_matching_service.py` | `matching_service.py` is a future-logic stub. `reference_matching_service.py` is imported by matching/observation APIs, demo processing, discrepancy service, and evaluation. | Active implementation is `reference_matching_service.py`; stub retained. |
| `discrepancy_engine.py` / `discrepancy_service.py` | `discrepancy_engine.py` is a future stub. `discrepancy_service.py` is imported by discrepancy/observation APIs and evaluation. | Active implementation is `discrepancy_service.py`; stub retained. |
| `fusion_service.py` / `observation_fusion_service.py` | `fusion_service.py` is a future stub. `observation_fusion_service.py` is imported by observation API/evaluation and exercised by tests. | Active implementation is `observation_fusion_service.py`; stub retained. |
| `view_selector.py` / `view_selection_service.py` | `view_selector.py` is a future stub. `view_selection_service.py` is imported by views API and demo processing. | Active implementation is `view_selection_service.py`; stub retained. |

These call-site findings are repository-static analysis, not proof that unused modules have no external consumers.
