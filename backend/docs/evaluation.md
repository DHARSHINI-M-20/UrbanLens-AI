# Ground-truth evaluation

## Purpose and scope

The evaluation package scores UrbanLens pipeline outputs against explicitly labelled `GroundTruthDataset` data. It does not infer labels from demo output, call Google Street View, invoke Bedrock, or claim system-wide accuracy. Each result is scoped to a dataset ID and version. Metrics use only labels that are present and report unknown or excluded labels separately.

The first registered fixture is `urbanlens_synthetic_eval_v1`, version `1.0.0`. Both its truth labels and deterministic mock-provider outputs are synthetic. Every run from it includes:

> SYNTHETIC EVALUATION RESULT — NOT REAL STREET VIEW PERFORMANCE

The fixture ground-truth metadata is labelled `SYNTHETIC EVALUATION GROUND TRUTH — NOT REAL STREET VIEW DATA`. It is not evidence of real-world Street View accuracy. Its intentionally imperfect mock outputs include misses, extra detections, wrong floor/use values, exact and normalized OCR cases, ambiguous/unknown labels, reference-match outcomes, discrepancy labels, and review/routing cases.

## Schema

`app/evaluation/schema.py` defines a versioned dataset with metadata and image/view samples. Each sample has a required `dataset_id` and `image_id`, optional panorama/source provenance, and an explicit `labeled_classes` list that says which detection classes are exhaustively annotated in that image. Child annotations support:

- buildings: stable ID, presence, optional pixel box, floor count, use, location, reference-match, discrepancy, review and expected-route labels;
- assets: optional ID, class, presence, and optional box;
- OCR: region ID, explicitly labelled text (including an empty string when no text is present), or `null` when unknown;
- positioning: entity association and optional latitude/longitude or reference geometry;
- reference matching, discrepancy type/presence, and review/routing truth.

Unknown values remain `null`. Missing labels are not converted into negative examples. Detection false positives are counted only for classes listed as exhaustively labelled in that image. OCR and other entity-level measures score explicitly annotated examples; unannotated regions are not assumed to be negatives.

## Metrics and interpretation

Reusable functions are in `app/evaluation/metrics.py`:

- building and per-asset-class detection TP/FP/FN, precision, recall and F1; boxes use IoU matching when available, with explicit IDs as fallback when geometry is absent;
- OCR raw exact-match rate, Unicode/whitespace-normalized match rate, character error rate, and token-level word accuracy. Normalization preserves case;
- floor-count exact accuracy and MAE, with unknown truth excluded and missing predictions reported separately;
- building-use accuracy and confusion matrix;
- positioning haversine errors in meters, mean/median, known-coordinate count, unknown truth exclusions and missing predictions;
- reference-match and discrepancy precision/recall/F1; discrepancy results are grouped by class;
- human-review and expected-routing decision precision/recall/F1, including false and missed reviews;
- routing decision counts and percentages, plus latency aggregation (p95 only at 20 or more samples);
- cost only from explicit non-negative finite pricing input and invocation counts. Otherwise cost is `unavailable` with a reason.

Every label-based result includes evaluated counts and `excluded_unknown_ground_truth`. Undefined denominators return `null`, not fabricated zeros. The current fixture does not contain independently adjudicated fused-entity outcomes, so fusion quality is `not_evaluable`. Fixture wall-clock time is evaluator overhead, so model latency is also `not_evaluable`. Cost is `unavailable` without explicitly supplied prices.

The all-VLM baseline has not been executed. Every run reports `all_vlm_run: false` and quality, cost, and latency comparisons as unavailable. The runner does not invoke VLM or Bedrock.

## Run the fixture

From `backend` with the project virtual environment active:

```powershell
python -m app.evaluation
python -m app.evaluation --subset eval-view-01 --subset eval-view-02
python -m app.evaluation --category ocr --category floor_count
```

The runner is available as `EvaluationRunner`. Trusted local integrations can validate an explicitly authorized annotation object with `GroundTruthDataset.model_validate(...)`, provide an adapter implementing `predict(sample)`, and call `run_dataset(...)`. Provider selection and filesystem paths are not accepted by the HTTP endpoint.

## API

`POST /evaluation/run` runs only the registered synthetic fixture. Optional request fields are `dataset_version`, `subset` (fixture image IDs), and `categories`. The endpoint is stateless; it stores no results and accepts no image path, code, model, provider, AWS, or pricing configuration. Unknown datasets and IDs are rejected.

Example:

```json
{
  "dataset_id": "urbanlens_synthetic_eval_v1",
  "dataset_version": "1.0.0",
  "categories": ["detection", "ocr", "floor_count"]
}
```

## Reused components

The fixture adapter runs the existing `ObservationPipelineService` with its `MockVisionProvider` and `MockOCRProvider`, and injects a no-call router that retains route decisions while suppressing external VLM calls. It also exercises existing positioning, reference matching, discrepancy, review, and fusion services. `normalize_ocr_text` is reused for normalized OCR comparisons. The existing `ProcessingMetricsService` remains an operational usage summary and is not used as ground-truth accuracy.

## What remains unmeasured

The synthetic fixture only demonstrates the evaluation mechanics. It does not establish real-world building/asset detection, OCR, floor/use, positioning, fusion, matching, discrepancy, review, latency, or cost performance. No full-pipeline real-image ground-truth dataset exists yet. A defensible real evaluation requires an authorized image source, versioned labels with documented annotation coverage, an appropriate pipeline prediction provider, and verified pricing before cost can be reported. No all-VLM baseline has been executed.
