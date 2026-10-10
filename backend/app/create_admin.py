"""Interactively bootstrap the first UrbanLens administrator (no password arguments)."""

from __future__ import annotations

import getpass
import sqlite3

from app.security import create_user, database, initialize_auth_store


def main() -> None:
    initialize_auth_store()
    with database() as db:
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
            raise SystemExit("An account already exists. Ask an administrator to create or promote accounts.")
    email = input("Administrator email: ").strip()
    name = input("Administrator display name: ").strip()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    try:
        user = create_user(email, name, "administrator", password)
    except (sqlite3.IntegrityError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Created development/local administrator {user['email']} ({user['id']}).")


if __name__ == "__main__":
    main()
