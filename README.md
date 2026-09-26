# UrbanLens-AI

Backend foundation for Google Street View-based urban asset and property intelligence.

## Structure

- `backend/app`: FastAPI application, API modules, services, models, and MongoDB helpers.
- `data/reference`: Source/reference datasets.
- `data/evaluation`: Evaluation datasets and outputs.
- `frontend`: Reserved for the future user interface.

Street View calls, asset detection, matching, and persistence workflows are deliberately not implemented yet.

## Setup

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Copy `backend/.env.example` to `.env` and set `MONGODB_URI` and
`MONGODB_DATABASE`. Never commit this file or API keys. MongoDB stores only
metadata, identifiers, evidence references, attributes, and processing details;
do not store Street View image files in it.

## Run the API

```powershell
uvicorn app.main:app --reload --app-dir backend
```

Open `http://127.0.0.1:8000/health`. It returns:

```json
{
  "status": "ok",
  "service": "UrbanLens AI"
}
```

Interactive documentation will be at `http://127.0.0.1:8000/docs`.
