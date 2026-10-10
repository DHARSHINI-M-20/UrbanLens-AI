"""Session login and administrator-only account management."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security import (SESSION_COOKIE, SESSION_TTL_SECONDS, authenticate,
                          create_initial_admin, create_user, current_session, database,
                          public_user, revoke_session, setup_required)

router = APIRouter(prefix="/auth", tags=["authentication"])
Role = Literal["administrator", "analyst", "reviewer", "viewer"]


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class InitialAdminInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=1024)


class RegistrationInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["analyst", "reviewer", "viewer"]
    password: str = Field(min_length=12, max_length=1024)


class UserCreateInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=12, max_length=1024)


class UserUpdateInput(BaseModel):
    role: Role | None = None
    active: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)


def _cookie_secure() -> bool:
    import os
    return (os.getenv("URBANLENS_ENVIRONMENT", "development").lower() == "production"
            or os.getenv("URBANLENS_AUTH_COOKIE_SECURE", "false").lower() == "true")


def _admin(request: Request) -> dict:
    session = current_session(request)
    if session["user"]["role"] != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return session


def _active_admin_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM users WHERE role='administrator' AND active=1").fetchone()[0])


@router.get("/setup/status")
def setup_status() -> dict[str, bool]:
    import os
    production = os.getenv("URBANLENS_ENVIRONMENT", "development").lower() == "production"
    registration_enabled = not production or os.getenv("URBANLENS_ALLOW_PUBLIC_REGISTRATION", "false").lower() == "true"
    return {"setup_required": setup_required(), "registration_enabled": registration_enabled}


@router.post("/register", status_code=201)
def register(payload: RegistrationInput) -> dict:
    import os
    production = os.getenv("URBANLENS_ENVIRONMENT", "development").lower() == "production"
    if production and os.getenv("URBANLENS_ALLOW_PUBLIC_REGISTRATION", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Public registration is disabled.")
    try:
        return create_user(str(payload.email), payload.name, payload.role, payload.password)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/setup/administrator", status_code=201)
def setup_administrator(payload: InitialAdminInput) -> dict:
    import os
    if os.getenv("URBANLENS_ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=403, detail="Use the protected administrator bootstrap command in production.")
    try:
        return create_initial_admin(str(payload.email), payload.name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "already been completed" in str(exc) else 422,
                            detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc


@router.post("/login")
def login(payload: LoginInput, response: Response) -> dict:
    result = authenticate(str(payload.email), payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user, token, csrf_token, expires_at = result
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL_SECONDS, httponly=True,
                        secure=_cookie_secure(), samesite="lax", path="/")
    return {"user": user, "csrf_token": csrf_token, "expires_at": expires_at}


@router.get("/session")
def session(request: Request) -> dict:
    current = current_session(request)
    return {"user": current["user"], "csrf_token": current["csrf_token"], "expires_at": current["expires_at"]}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    current = current_session(request)
    revoke_session(current["token_hash"])
    response.delete_cookie(SESSION_COOKIE, path="/", secure=_cookie_secure(), httponly=True, samesite="lax")
    return {"logged_out": True}


@router.get("/users")
def list_users(request: Request) -> list[dict]:
    _admin(request)
    with database() as db:
        rows = db.execute("SELECT * FROM users ORDER BY email COLLATE NOCASE").fetchall()
    return [public_user(row) for row in rows]


@router.post("/users", status_code=201)
def add_user(payload: UserCreateInput, request: Request) -> dict:
    _admin(request)
    try:
        return create_user(str(payload.email), payload.name, payload.role, payload.password)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdateInput, request: Request) -> dict:
    actor = _admin(request)["user"]
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide a role, active state, or name to update.")
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Role, active state, and name cannot be null.")
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Name cannot be empty.")
    with database() as db:
        target = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="User not found.")
        if actor["id"] == user_id and ("role" in changes or changes.get("active") is False):
            raise HTTPException(status_code=403, detail="You cannot change your own role or deactivate your account.")
        next_role = changes.get("role", target["role"])
        next_active = changes.get("active", bool(target["active"]))
        if target["role"] == "administrator" and target["active"] and (next_role != "administrator" or not next_active):
            if _active_admin_count(db) <= 1:
                raise HTTPException(status_code=409, detail="At least one active administrator must remain.")
        assignments = []
        values: list[object] = []
        if "role" in changes:
            assignments.append("role=?"); values.append(changes["role"])
        if "active" in changes:
            assignments.append("active=?"); values.append(int(changes["active"]))
        if "name" in changes:
            assignments.append("display_name=?"); values.append(changes["name"].strip())
        values.append(user_id)
        db.execute(f"UPDATE users SET {', '.join(assignments)} WHERE user_id=?", values)
        if not next_active or next_role != target["role"]:
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        updated = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return public_user(updated)
