"""Token authentication service for the e-commerce API."""

from app.auth.jwt import encode_token, decode_token
from app.repositories import db
from app.services import users as user_service


def authenticate(username: str, password: str) -> dict:
    """Verify credentials and return a signed token payload."""
    user = user_service.get_user_by_username(username)
    if user is None:
        raise ValueError("invalid credentials")
    if user.get("password_hash") != _hash_password(password):
        raise ValueError("invalid credentials")
    return {"token": encode_token({"sub": username, "role": user.get("role", "user")})}


def current_user(token: str) -> dict:
    payload = decode_token(token)
    return user_service.get_user_by_username(payload["sub"])


def _hash_password(password: str) -> str:
    import hashlib

    return hashlib.sha256(password.encode()).hexdigest()
