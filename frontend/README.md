# UrbanLens AI frontend

UrbanLens AI is a React dashboard for exploring study-area, street, observation, OCR, matching, discrepancy, review, processing-metric, and Task 5 challenge-query records. The current seeded dataset is deterministic simulated data. It is not Google Street View imagery and its synthetic reference records are not an official property register.

## Requirements

- Node.js and npm compatible with the versions used to create `package-lock.json`.
- The FastAPI backend and a reachable MongoDB instance for local mode.
- The frontend does not contain AWS credentials. AWS mode talks to the configured read-only API Gateway URL.

## Start locally

From the repository root, start MongoDB using your local setup. Then start FastAPI:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configure the repository-root `.env` as needed. At minimum, local persistence requires `MONGODB_URI` and `MONGODB_DATABASE`. From another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`; the development proxy is same-origin from the browser. The banner reports backend errors and provides a retry action. It identifies the fixed dataset as `tn_study_area_demo_v1` and labels its records synthetic. The dashboard does not offer arbitrary dataset selection; AWS mode is fixed to the cloud demo dataset. Use **Seed demo** to populate the local simulated dataset. Reseed and reset require confirmation and affect only that demo dataset.

## API mode

Copy `.env.example` or configure the Vite process environment:

```env
VITE_API_MODE=local
VITE_API_BASE_URL=/api
```

For the existing AWS read API, set `VITE_API_MODE=aws` and `VITE_API_BASE_URL` to the deployed API Gateway URL. Do not put AWS keys or other credentials in frontend environment variables. AWS mode is read-only; cloud review decisions and demo seeding are disabled. It serves synchronized simulated records, not real imagery or property data.

The backend API contract notes are in [`../backend/API_CONTRACTS.md`](../backend/API_CONTRACTS.md). Collection endpoints return record arrays; analytics and demo status return objects. Challenge-query endpoints return a provenance-bearing envelope with `records`, result count, generation time, simulation state, and limitations.

## Task 5 challenge queries

Open **Task 5 Queries** in the navigation and run any of the five queries against the fixed demo dataset:

1. Commercial buildings over two floors that are explicitly unmatched in supplied references. This does not mean no official property record exists.
2. Expected streetlight discrepancies from records declaring complete coverage; incomplete/unknown coverage is excluded. The observation condition comes from the stored discrepancy.
3. Known floor counts below the provider-confidence threshold that remain pending review. Missing confidence/floors are excluded.
4. Explicitly unmatched buildings grouped by street; missing match status is excluded.
5. Stored routed metrics with `NOT_RUN` all-VLM state and `NOT_EVALUABLE` quality comparison unless an actual baseline is later measured.

The fifth query does not execute an all-VLM baseline. Quality comparison is `NOT_EVALUABLE`; all-VLM cost remains unavailable without verified pricing. Query results from the seeded dataset are explicitly simulated.

Large property and review tables use **client-side pagination** over the records already returned by bounded collection endpoints. This limits rendered rows but is not server-side cursor pagination; the backend still applies its endpoint-specific result caps.

## Review workflow

Local mode allows confirm/reject decisions and optional corrections for floor count, probable use, asset type, and OCR text. A correction is stored on the review record with the original value; the original observation is not overwritten. A reviewer note is optional. AWS mode is read-only.

## Validation commands

```powershell
npm run lint
npm run build
npm run test:unit
```

`npm run test:smoke` is a source-wiring/UI-label smoke check, not browser-driven E2E: this environment has no browser automation package or browser binary, and Vite’s dev server could not load its Windows native binding under the current sandbox. It checks route wiring and the challenge-query labels without starting the API or making external calls.

Backend tests run from `backend` using `..\backend\run_tests.ps1 -q` (or `python -m pytest -q` in an activated backend environment). Normal tests use offline fixtures and mocks. Real AWS and authorized Street View integrations are opt-in; do not enable them for routine validation.

## Limitations

- The seeded streets, panorama metadata, images, detections, OCR, reference records, and VLM mock outputs are synthetic.
- The official study-area boundary is real challenge geometry; it does not make the generated observations real.
- No full-pipeline ground-truth evaluation or measured CV accuracy is provided.
- Local YOLO/Tesseract provider code exists but its presence does not establish accuracy on the demo data.
- Real authorized Google Street View integration, an authoritative FarmwiseAI reference dataset, Lambda Bedrock permission verification, and a full ground-truth evaluation set remain external blockers.
- Local/cloud challenge queries share pure filtering rules, but storage adapters remain separate and deployed cloud response parity remains unverified.
- Route-level lazy loading splits page code; bundle sizes should still be reviewed from each build because no page-load benchmark is available.
