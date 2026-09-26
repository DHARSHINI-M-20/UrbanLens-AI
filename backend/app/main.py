"""FastAPI entry point for UrbanLens AI."""

from fastapi import FastAPI, HTTPException

from app.api import (
    analytics,
    discrepancies,
    matching,
    observations,
    panoramas,
    review,
    sampling,
    study_area,
    streets,
)
from app.config import get_settings
from app.database.mongodb import check_connection

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")


@app.on_event("startup")
def test_database_connection() -> None:
    """Test MongoDB at API startup and prepare indexes when it is reachable."""
    app.state.mongodb_reachable = check_connection(create_schema=True)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Confirm that the API is running."""
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/db", tags=["health"])
def database_health_check() -> dict[str, bool | str]:
    """Report MongoDB reachability without exposing connection details."""
    reachable = check_connection()
    app.state.mongodb_reachable = reachable
    if not reachable:
        raise HTTPException(status_code=503, detail="MongoDB is not reachable.")
    return {"status": "ok", "database": settings.mongodb_database}


# Route modules are registered now so their endpoints can grow independently.
app.include_router(study_area.router, prefix="/study-area", tags=["study-area"])
app.include_router(sampling.router, prefix="/sampling", tags=["sampling"])
app.include_router(streets.router, prefix="/streets", tags=["streets"])
app.include_router(panoramas.router, prefix="/panoramas", tags=["panoramas"])
app.include_router(observations.router, prefix="/observations", tags=["observations"])
app.include_router(matching.router, prefix="/matching", tags=["matching"])
app.include_router(discrepancies.router, prefix="/discrepancies", tags=["discrepancies"])
app.include_router(review.router, prefix="/review", tags=["review"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
