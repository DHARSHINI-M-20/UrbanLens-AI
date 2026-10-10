"""Local session authentication and centralized role permissions.

Passwords use scrypt; browser sessions are opaque random tokens whose hashes are
stored in SQLite. This store is deliberately separate from the optional MongoDB
observation database so login remains available when MongoDB is offline.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

ROLES = {"administrator", "analyst", "reviewer", "viewer"}
SESSION_COOKIE = "urbanlens_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
_SCRYPT_N = 2**14

# One policy source for both API requests and frontend route visibility.
PAGE_PERMISSIONS: dict[str, set[str]] = {
    "/": {"administrator", "analyst", "reviewer", "viewer"},
    "/map": {"administrator", "analyst", "reviewer", "viewer"},
    "/properties": {"administrator", "analyst", "reviewer", "viewer"},
    "/analytics": {"administrator", "analyst", "viewer"},
    "/history": {"administrator", "analyst"},
    "/challenge-queries": {"administrator", "analyst"},
    "/review": {"administrator", "reviewer"},
    "/settings": {"administrator"},
    "/admin/users": {"administrator"},
}

_READ_ONLY = {
    "/study-area", "/streets", "/sampling/points", "/observations",
    "/references", "/matching", "/discrepancies", "/analytics",
}
_ANALYST_EXTRA = {"/metrics", "/demo/runs", "/queries"}
_REVIEWER_EXTRA = {"/observations/ocr", "/reviews"}


def auth_db_path() -> Path:
    default_path = Path(tempfile.gettempdir()) / "urbanlens-ai" / "identity.sqlite3"
    return Path(os.getenv("URBANLENS_AUTH_DB_PATH", str(default_path)))


def connect() -> sqlite3.Connection:
    path = auth_db_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    connection = sqlite3.connect(path, timeout=10)
    if os.name != "nt":
        path.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_auth_store() -> None:
    with database() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('administrator','analyst','reviewer','viewer')),
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                csrf_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
        """)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    return f"scrypt${_SCRYPT_N}$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest_hex)))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {"id": row["user_id"], "email": row["email"], "name": row["display_name"],
            "role": row["role"], "active": bool(row["active"])}


def create_user(email: str, name: str, role: str, password: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    if (len(normalized_email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email)):
        raise ValueError("Enter a valid email address.")
    if role not in ROLES:
        raise ValueError("Unknown role.")
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError("Name must contain 1 to 120 characters.")
    user_id = secrets.token_urlsafe(18)
    with database() as db:
        db.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,active,created_at) VALUES(?,?,?,?,?,1,?)",
                   (user_id, normalized_email, name.strip(), role, hash_password(password), int(time.time())))
        row = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return public_user(row)


def setup_required() -> bool:
    with database() as db:
        return db.execute("SELECT COUNT(*) FROM users WHERE role='administrator'").fetchone()[0] == 0


def create_initial_admin(email: str, name: str, password: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    if (len(normalized_email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email)):
        raise ValueError("Enter a valid email address.")
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError("Name must contain 1 to 120 characters.")
    password_hash = hash_password(password)
    user_id = secrets.token_urlsafe(18)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM users WHERE role='administrator'").fetchone()[0] != 0:
            raise ValueError("Initial setup has already been completed. Sign in or contact an administrator.")
        db.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,active,created_at) VALUES(?,?,?,'administrator',?,1,?)",
            (user_id, normalized_email, name.strip(), password_hash, int(time.time())),
        )
        row = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return public_user(row)


def authenticate(email: str, password: str) -> tuple[dict[str, Any], str, str, int] | None:
    with database() as db:
        row = db.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email.strip(),)).fetchone()
        if row is None:
            # Spend comparable work for unknown usernames; no credential details leak.
            hashlib.scrypt(password.encode("utf-8"), salt=b"UrbanLensAuthSalt", n=_SCRYPT_N, r=8, p=1, dklen=32)
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        if not row["active"]:
            raise HTTPException(status_code=403, detail="This account is inactive. Contact an administrator.")
        now = int(time.time())
        raw_token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        expires = now + SESSION_TTL_SECONDS
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        db.execute("INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?)",
                   (hashlib.sha256(raw_token.encode()).hexdigest(), row["user_id"], csrf, expires, now))
        return public_user(row), raw_token, csrf, expires


def resolve_session(raw_token: str | None) -> dict[str, Any] | None:
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with database() as db:
        row = db.execute("""SELECT u.*, s.csrf_token, s.expires_at FROM sessions s
            JOIN users u ON u.user_id=s.user_id WHERE s.token_hash=?""", (token_hash,)).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= int(time.time()) or not row["active"]:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            return None
        return {"user": public_user(row), "csrf_token": row["csrf_token"], "expires_at": row["expires_at"],
                "token_hash": token_hash}


def revoke_session(token_hash: str | None) -> None:
    if token_hash:
        with database() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))


def can_access_api(role: str, path: str, method: str) -> bool:
    if role == "administrator":
        return True
    if role not in ROLES or method not in {"GET", "HEAD"}:
        return role == "reviewer" and method == "PATCH" and path.startswith("/reviews/") and path.endswith("/decision")
    if path == "/demo/status" or path in {"/metrics", "/metrics/summary"}:
        return True
    if path in _READ_ONLY or any(path.startswith(prefix + "/") for prefix in _READ_ONLY):
        return True
    if role == "analyst" and (path in _ANALYST_EXTRA or any(path.startswith(prefix + "/") for prefix in _ANALYST_EXTRA)):
        return True
    if role == "reviewer" and (path in _REVIEWER_EXTRA or any(path.startswith(prefix + "/") for prefix in _REVIEWER_EXTRA)):
        return True
    return False


def current_session(request: Request) -> dict[str, Any]:
    session = getattr(request.state, "auth_session", None)
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session
