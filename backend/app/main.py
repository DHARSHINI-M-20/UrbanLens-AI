"""FastAPI entry point for UrbanLens AI."""

import os
from contextlib import asynccontextmanager
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    auth,
    aws_integration,
    demo,
    discrepancies,
    evaluation,
    matching,
    metrics,
    observations,
    panoramas,
    queries,
    references,
    review,
    sampling,
    study_area,
    streets,
    views,
)
from app.config import get_settings
from app.database.mongodb import check_connection
from app.security import (SESSION_COOKIE, can_access_api,
                          initialize_auth_store, resolve_session)

settings = get_settings()
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Check optional MongoDB connectivity when the local API starts."""
    initialize_auth_store()
    application.state.mongodb_reachable = check_connection(create_schema=True)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
cors_origins = [origin.strip() for origin in os.getenv("URBANLENS_CORS_ORIGINS", "").split(",") if origin.strip()]
if "*" in cors_origins:
    raise RuntimeError("URBANLENS_CORS_ORIGINS must list explicit origins; wildcard CORS is not allowed.")
app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "X-CSRF-Token"], allow_credentials=True)


@app.middleware("http")
async def enforce_local_mutation_body_limits_and_authorization(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 25_000_000:
                return JSONResponse(status_code=413, content={"detail": "Request body exceeds the 25 MB limit."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
    if os.getenv("URBANLENS_ENVIRONMENT", "development").lower() == "production" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        host = request.client.host if request.client else ""
        try:
            trusted_local = ip_address(host).is_loopback
        except ValueError:
            trusted_local = False
        if not trusted_local:
            return JSONResponse(status_code=403, content={"detail": "Mutation endpoints are restricted to the local development host."})
    path = request.url.path
    if request.method == "OPTIONS" or path in {
        "/health", "/auth/login", "/auth/register", "/auth/setup/status", "/auth/setup/administrator"
    }:
        return await call_next(request)
    session = resolve_session(request.cookies.get(SESSION_COOKIE))
    if session is None:
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})
    request.state.auth_session = session
    if request.method not in {"GET", "HEAD"}:
        supplied_csrf = request.headers.get("x-csrf-token", "")
        if not supplied_csrf or not secrets_compare(supplied_csrf, session["csrf_token"]):
            return JSONResponse(status_code=403, content={"detail": "Valid CSRF token required."})
    if not path.startswith("/auth/") and not can_access_api(session["user"]["role"], path, request.method):
        return JSONResponse(status_code=403, content={"detail": "Your role is not permitted to access this endpoint."})
    return await call_next(request)


def secrets_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(left, right)


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
app.include_router(views.router, prefix="/views", tags=["views"])
app.include_router(observations.router, prefix="/observations", tags=["observations"])
app.include_router(references.router, prefix="/references", tags=["references"])
app.include_router(matching.router, prefix="/matching", tags=["matching"])
app.include_router(discrepancies.router, prefix="/discrepancies", tags=["discrepancies"])
app.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
app.include_router(review.router, prefix="/reviews", tags=["reviews"])
app.include_router(review.router, prefix="/review", tags=["review"])  # backward-compatible alias
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(aws_integration.router, prefix="/aws", tags=["aws"])
app.include_router(demo.router, prefix="/demo", tags=["demo"])
app.include_router(queries.router, prefix="/queries", tags=["queries"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(auth.router)
