from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import security
from app.main import app


@pytest.fixture
def authenticated_client(tmp_path, monkeypatch):
    """An isolated real administrator session for protected API regression tests."""
    monkeypatch.setenv("URBANLENS_AUTH_DB_PATH", str(tmp_path / "auth-regression.sqlite3"))
    security.initialize_auth_store()
    security.create_user("test-admin@example.test", "Regression Admin", "administrator", "regression-admin-pass-123")
    with TestClient(app) as client:
        response = client.post("/auth/login", json={
            "email": "test-admin@example.test", "password": "regression-admin-pass-123",
        })
        assert response.status_code == 200
        client.headers.update({"X-CSRF-Token": response.json()["csrf_token"]})
        yield client
