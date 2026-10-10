# UrbanLens authentication and roles

## Local setup

The local FastAPI service now owns login, sessions, and role enforcement. It uses a separate SQLite identity store so authentication does not depend on the optional MongoDB observation database. Passwords are stored as salted scrypt hashes. Browser sessions use random opaque tokens in an `HttpOnly`, `SameSite=Lax` cookie; unsafe requests require the session's CSRF token in `X-CSRF-Token`. Sessions expire after eight hours and logout revokes the server-side session.

No default account or password is shipped. On a fresh local database, choose **Create the initial administrator** on the login page. The form creates the only initial administrator and signs it in; it is unavailable after the first account is created. Production blocks this web setup endpoint. The protected CLI bootstrap also remains available from the `backend` directory:

```powershell
python -m app.create_admin
```

Run it in the activated Python environment used for FastAPI.

The command prompts for an email, name, and password without echoing the password. Use at least 12 characters. The store defaults to the operating system temporary directory under `urbanlens-ai/identity.sqlite3`; set `URBANLENS_AUTH_DB_PATH` to choose a persistent protected location. Back up and restrict access to that file. Do not put its contents or passwords in source control.

Local development sign-up is enabled by default. New users can create Urban Analyst, Reviewer, or Viewer accounts from the login page; passwords are hashed before storage, and accounts are immediately available in administrator User Management (the list refreshes every five seconds). Public sign-up cannot create an Administrator. In production, sign-up is disabled unless `URBANLENS_ALLOW_PUBLIC_REGISTRATION=true` is explicitly configured. Production deployments should enable it only when public role assignment is intended.

Run FastAPI on `127.0.0.1:8001` and the Vite frontend on `127.0.0.1:5173`. The existing Vite `/api` proxy forwards authentication and local API requests to FastAPI; set `URBANLENS_BACKEND_PROXY_TARGET` if you choose another backend port. Port 8000 may already be occupied by an older API process without authentication routes. Set `VITE_API_MODE=local` for the MongoDB-backed dashboard. Configure `URBANLENS_CORS_ORIGINS` with exact trusted web origins if calling FastAPI cross-origin; wildcard origins are rejected. In production set `URBANLENS_ENVIRONMENT=production`; session cookies are then always Secure and the existing production mutation-host restriction remains active.

## Roles

| Role | Pages and API capabilities |
|---|---|
| Administrator | All dashboard pages, review decisions, demo lifecycle actions, system status, and user administration. Cannot demote/deactivate their own account or remove the last active administrator. |
| Analyst | Dashboard, map, properties, analytics, history, and challenge queries. Read-only record APIs. |
| Reviewer | Dashboard, map, properties, and review queue. Can submit review decisions; the reviewer identity is taken from the authenticated account, not the request body. The current dataset has no per-record assignment model, so authorized reviewers see the dataset's queue. |
| Viewer | Dashboard, map, properties, and analytics, read-only. |

The canonical page policy is in `backend/app/security.py` and mirrored for route rendering in `frontend/src/auth/permissions.ts`. Backend middleware denies unauthenticated requests with 401, disallowed roles with 403, and unsafe requests without a valid CSRF token with 403. User role changes and account activation are administrator-only; self-role changes are rejected.

## Cloud limitation

The existing API Gateway/Lambda read API is a separate public, read-only service. It does not validate these local SQLite sessions and has no user-management or review-write endpoint. The frontend route/navigation guards still apply after authentication, but they do **not** secure direct requests to that cloud API. Do not expose private data or treat cloud mode as protected by these local roles. Production cloud RBAC requires a deployed identity provider/API authorizer (or equivalent server-side token verification) and updated Lambda/API Gateway configuration. The browser session cookie is `SameSite=Lax`; configure the auth API on the same site/origin (for example, with a reverse proxy). Pointing `VITE_AUTH_API_BASE_URL` at an unrelated cross-site host is not supported.

Google Street View remains unauthorized/unconfigured, and the existing cloud records remain explicitly simulated. Authentication does not change their provenance or make Bedrock/cloud invocation available.
