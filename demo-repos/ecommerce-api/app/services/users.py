"""User service: business logic for users."""

from typing import Optional

from app.repositories import db

USER_COLUMNS = "id, username, email, password_hash, role, is_active"


def get_users() -> list[dict]:
    rows = db.query_all(f"SELECT {USER_COLUMNS} FROM users ORDER BY id")
    return [_to_user(r) for r in rows]


def get_user_by_username(username: str) -> Optional[dict]:
    row = db.query_one(
        f"SELECT {USER_COLUMNS} FROM users WHERE username = ?", (username,)
    )
    if row is None:
        return None
    return _to_user(row)


def create_user(username: str, email: str, password: str) -> dict:
    from app.auth.service import _hash_password

    existing = get_user_by_username(username)
    if existing is not None:
        raise ValueError(f"username already taken: {username}")
    password_hash = _hash_password(password)
    cursor = db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    return {"id": cursor.lastrowid, "username": username, "email": email}


def _to_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "password_hash": row.get("password_hash", ""),
        "role": row.get("role", "user"),
        "is_active": bool(row.get("is_active", 1)),
    }
