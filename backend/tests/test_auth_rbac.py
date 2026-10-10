from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import security
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("URBANLENS_AUTH_DB_PATH", str(tmp_path / "auth.sqlite3"))
    security.initialize_auth_store()
    security.create_user("root@example.test", "Root Admin", "administrator", "admin-test-password-123")
    with TestClient(app) as test_client:
        yield test_client


def sign_in(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_unauthenticated_protected_api_is_401(client):
    assert client.get("/study-area").status_code == 401
    assert client.get("/auth/session").status_code == 401


def test_invalid_credentials_and_inactive_account(client):
    assert client.post("/auth/login", json={"email": "root@example.test", "password": "wrong-password"}).status_code == 401
    csrf = sign_in(client, "root@example.test", "admin-test-password-123")
    with security.database() as db:
        db.execute("UPDATE users SET active=0 WHERE email='root@example.test'")
    assert client.get("/auth/session").status_code == 401
    response = client.post("/auth/login", json={"email": "root@example.test", "password": "admin-test-password-123"})
    assert response.status_code == 403
    assert csrf


@pytest.mark.parametrize(("role", "allowed_path", "denied_path"), [
    ("analyst", "/study-area", "/reviews"),
    ("reviewer", "/study-area", "/queries/routed-vs-all-vlm"),
    ("viewer", "/study-area", "/queries/routed-vs-all-vlm"),
])
def test_role_api_allow_and_deny(client, role, allowed_path, denied_path):
    token = f"{role}-test-password-123"
    email = f"{role}@example.test"
    security.create_user(email, role.title(), role, token)
    sign_in(client, "root@example.test", "admin-test-password-123")
    # Public response contains no password hash or credential material.
    response = client.post("/auth/users", json={"email": email, "name": role.title(), "role": role, "password": token},
                           headers={"X-CSRF-Token": sign_in(client, "root@example.test", "admin-test-password-123")})
    assert response.status_code == 409
    sign_in(client, email, token)
    assert security.can_access_api(role, allowed_path, "GET")
    assert not security.can_access_api(role, denied_path, "GET")
    assert client.get(allowed_path).status_code != 403
    assert client.get(denied_path).status_code == 403
    if role != "administrator":
        assert client.get("/auth/users").status_code == 403


def test_admin_user_management_and_self_role_protection(client):
    csrf = sign_in(client, "root@example.test", "admin-test-password-123")
    created = client.post("/auth/users", json={"email": "new@example.test", "name": "New Reviewer",
                                               "role": "reviewer", "password": "new-user-password-123"},
                          headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    assert "password_hash" not in created.text and "new-user-password-123" not in created.text
    user_id = created.json()["id"]
    assert client.patch(f"/auth/users/{user_id}", json={"active": False}, headers={"X-CSRF-Token": csrf}).json()["active"] is False
    me = client.get("/auth/session").json()["user"]
    self_update = client.patch(f"/auth/users/{me['id']}", json={"role": "viewer"}, headers={"X-CSRF-Token": csrf})
    assert self_update.status_code == 403
    assert client.get("/auth/users").status_code == 200


def test_mutation_requires_csrf_and_logout_revokes_session(client):
    sign_in(client, "root@example.test", "admin-test-password-123")
    assert client.post("/study-area/contains", json={"latitude": 11.03, "longitude": 76.97}).status_code == 403
    csrf = client.get("/auth/session").json()["csrf_token"]
    response = client.post("/study-area/contains", json={"latitude": 11.03, "longitude": 76.97},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/study-area").status_code == 401


def test_session_expiration_revokes_session(client):
    sign_in(client, "root@example.test", "admin-test-password-123")
    token = client.cookies.get(security.SESSION_COOKIE)
    token_hash = __import__("hashlib").sha256(token.encode()).hexdigest()
    with security.database() as db:
        db.execute("UPDATE sessions SET expires_at=0 WHERE token_hash=?", (token_hash,))
    assert client.get("/study-area").status_code == 401


def test_password_hash_is_not_plaintext():
    encoded = security.hash_password("sample-password-123")
    assert encoded.startswith("scrypt$")
    assert encoded != "sample-password-123"
    assert security.verify_password("sample-password-123", encoded)
    assert not security.verify_password("wrong-password", encoded)


def test_permission_policy_limits_reviewer_mutations():
    assert security.can_access_api("reviewer", "/reviews/rev-1/decision", "PATCH")
    assert not security.can_access_api("viewer", "/reviews/rev-1/decision", "PATCH")
    assert not security.can_access_api("analyst", "/demo/process", "POST")
