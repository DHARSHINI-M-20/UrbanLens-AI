# UrbanLens AI backend

## Overview

This backend supports the FarmwiseAI Street View urban-asset and property-intelligence pipeline. It preserves the official challenge study-area boundary, supports sampling and street import workflows, and prepares the app for authorized Street View, OCR, routing, geospatial association, duplicate fusion, reference matching, discrepancy review, and challenge queries.

## Architecture

1. Study area management
   - Reads the official GeoJSON boundary from `data/Study_Area/Study_area.geojson`
   - Validates that all inserted observations and streets remain within the authoritative area

2. Sampling
   - Builds a 50-meter sampling grid for the official study area
   - Stores generated points in MongoDB without creating panorama assumptions

3. Street/corridor handling
   - Accepts `LineString` and `MultiLineString` GeoJSON features
   - Filters streets to the official boundary
   - Supports explicit source typing: `farmwise_provided`, `permitted_public`, `participant_generated`

4. Street View abstraction
   - Uses an injectable metadata provider contract; the deterministic demo provider uses the same contract
   - Google access remains a separate future authorized adapter
   - Keeps the backend free of prohibited scraping or unofficial imagery access

5. Detection / OCR / routing
   - A CPU-only Ultralytics YOLO-World model proposes building, streetlight, and electric-pole detections
   - Tesseract extracts text and word boxes from supplied local images
   - Local image processing makes no image network requests; remote URLs are rejected
   - YOLO-World classes are candidate detections, not authoritative classifications; results remain reviewable
   - Low-confidence or complex scenes escalate to Amazon Nova Lite through Bedrock

6. Observation workflow
   - Records structured observations with confidence and route metadata
   - Supports duplicate fusion, geospatial association, and human review

7. Reference and discrepancy layers
   - Accepts synthetic, public, or participant-generated reference data
   - `POST /references/ingest/osm` imports public OpenStreetMap buildings, streetlights, and poles
   - OSM records retain OSM IDs, geometry, tags, attribution, and `incomplete_public_coverage` status
   - An unmatched OSM item is not evidence that a building or asset does not exist
   - Flags low-confidence or missing-reference cases for review

## Setup

From PowerShell:

```powershell
cd C:\Users\dhars\UrbanLens-AI\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a project-level `.env` file if needed and set:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=urbanlens
AWS_REGION=ap-south-1
BEDROCK_INFERENCE_PROFILE=apac.amazon.nova-lite-v1:0
# Optional verified per-invocation prices; keep blank when unavailable.
LOCAL_DETECTOR_COST_PER_INVOCATION=
OCR_COST_PER_INVOCATION=
NOVA_LITE_COST_PER_INVOCATION=
```

The local vision model weights are loaded lazily on first inference from the official Ultralytics model distribution; the pinned Ultralytics CLIP dependency supports text-conditioned YOLO-World classes. This requires network access once to obtain the model weights and dependencies. Install Tesseract OCR locally; set `TESSERACT_CMD` when its executable is not available on `PATH`. The image itself must be supplied by an authorized source or a local fixture.

Do not store AWS secret keys in source files or repository documentation.

## MongoDB configuration

This project uses MongoDB Community Server with the existing environment configuration. The backend expects:

- `MONGODB_URI`
- `MONGODB_DATABASE`

The application creates and reuses collections such as:

- `study_areas`
- `streets`
- `panoramas`
- `views`
- `observations`
- `unified_entities`
- `reference_records`
- `matches`
- `discrepancies`
- `review_queue`
- `sampling_points`
- `processing_runs`
- `processing_metrics`
- `ocr_observations`
- `reference_ingestion_runs`

## AWS and Bedrock configuration

The environment is expected to use the FarmwiseAI-approved AWS role and region:

- Region: `ap-south-1`
- Model profile: `apac.amazon.nova-lite-v1:0`

The backend does not hard-code credentials. If Bedrock access is not configured, the app raises a configuration error instead of fabricating model results.

## Running the API

```powershell
cd C:\Users\dhars\UrbanLens-AI\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Open the Swagger UI at:

```text
http://127.0.0.1:8000/docs
```

## Simulated Task 5 demonstration

The demo is stored under the fixed dataset ID `urbanlens-task5-sim-v1`. Every record is marked `simulation: true` and carries the label `SIMULATED DEMONSTRATION DATA — NOT REAL STREET VIEW DATA`. The provider generates metadata only; generated synthetic PNGs are processed in memory by deterministic fixture providers. This is not Google imagery, a real YOLO/Tesseract accuracy result, a Nova response, FarmwiseAI reference data, or a positioning-accuracy validation.

After starting the API and configuring a reachable MongoDB, seed/replay the isolated demo dataset:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/demo/seed
```

Check status and counts:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/demo/status
```

Replay the existing simulated views:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/demo/process
```

Reset only this dataset (never other/user records):

```powershell
Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:8000/demo/reset
```

In another terminal, run the frontend with the Vite `/api` proxy to the backend:

```powershell
cd C:\Users\dhars\UrbanLens-AI\frontend
npm run dev
```

Open the URL printed by Vite. The persistent banner identifies simulation mode; the map uses a local CSS grid and does not request online map tiles. The UI can seed/reseed, process, reset, filter by street, inspect evidence, and persist review decisions.

## Data-source distinctions

This project clearly separates:

1. FarmwiseAI-provided resources
   - official study-area boundary from `data/Study_Area/Study_area.geojson`

2. Permitted public data
   - non-FarmwiseAI mappings or reference layers when explicitly imported and labeled as such

3. Participant-generated or synthetic demo data
   - demo street entries, demo reference records, and non-authoritative synthetic inputs must be tagged accordingly

Never label synthetic demo data as official FarmwiseAI data.

## Street View compliance approach

This backend intentionally does not:

- scrape Google Maps
- scrape Street View pages
- use unofficial Google endpoints
- download restricted imagery without authorization

The Street View abstraction supports an authorized provider later, and only stores permitted evidence metadata rather than generated imagery archives.

## API endpoints

### Study area
- `GET /study-area`
- `GET /study-area/bounds`
- `POST /study-area/contains`

### Sampling
- `POST /sampling/generate`
- `GET /sampling/points`
- `DELETE /sampling/points`

### Streets
- `POST /streets/import`
- `GET /streets`
- `GET /streets/{street_id}`

### Views
- `GET /views`
- `POST /views/register`
- `POST /views/select`

### Panoramas
- `POST /panoramas/discover` (requires an authorized provider adapter)
- `GET /panoramas`

### Observations
- `GET /observations`
- `POST /observations/`
- `POST /observations/process` (requires configured local vision provider)
- `GET /observations/ocr`
- `GET /observations/{observation_id}`

### References
- `GET /references`
- `POST /references/import`
- `POST /references/ingest/osm`

### Matching and discrepancies
- `POST /matching/run`
- `GET /matching`
- `POST /discrepancies/generate`

### Queries
- `GET /queries/commercial-buildings-without-match`
- `GET /queries/streets-without-streetlights`
- `GET /queries/low-confidence-floor-counts`
- `GET /queries/unmatched-buildings-assets`
- `GET /queries/observations-by-street/{street_id}`
- `GET /queries/observations-by-asset-type/{asset_type}`
- `GET /queries/review-queue`

### Metrics
- `GET /metrics`
- `GET /metrics/summary`

## Testing

Run the focused validation suite:

```powershell
cd C:\Users\dhars\UrbanLens-AI\backend
.\run_tests.ps1 -q
```

The runner temporarily places the project venv's `site-packages` ahead of the base interpreter so an unrelated user-level `py.py` cannot shadow pytest's `py.path`; it restores the caller's `PYTHONPATH` afterward. The suite covers the complete offline pipeline plus a dataset-isolated MongoDB persistence/API integration test. Real Google and Bedrock tests remain opt-in and do not run during ordinary tests.

Tests use deterministic model-output fixtures; they do not download detector weights, call Overpass, access Street View, or invoke AWS. A separate local end-to-end test uses generated image pixels, a stubbed YOLO-World output, and the installed local Tesseract executable.

## Sample API calls

### Create a street import

```json
{
  "geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[76.9805, 11.0315], [76.9835, 11.0325]]},
        "properties": {"name": "Main Road"}
      }
    ]
  },
  "source": "synthetic_demo",
  "source_type": "participant_generated"
}
```

### Create a basic observation

```json
{
  "observation_id": "obs_1",
  "street_id": "street_demo",
  "panorama_reference": "pano_demo_1",
  "latitude": 11.0321,
  "longitude": 76.9811,
  "asset_type": "building",
  "attributes": {"building_use": "commercial"},
  "confidence": 0.82,
  "model_route": "small_model",
  "source": "small_model",
  "human_review_status": "pending"
}
```

## Notes

- The official study-area boundary remains the source of truth.
- The backend is integration-ready for authorized Street View and dataset ingestion, but those external providers and datasets are still required for production-grade coverage.
- Bedrock calls are intentionally selective and only happen for low-confidence or complex-scene cases.
