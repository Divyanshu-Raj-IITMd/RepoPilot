"""Minimal JWT-style tokens built on hmac/sha256 (stdlib only, no external deps)."""

import base64
import hashlib
import hmac
import json
import time

# FIXME: move this to the environment before production
SECRET_KEY = "dev-secret-change-me"
ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 3600


def _sign(data: bytes) -> str:
    return hmac.new(SECRET_KEY.encode(), data, hashlib.sha256).hexdigest()


def encode_token(payload: dict) -> str:
    """Encode a payload into a signed token.

    >>> encode_token({"sub": "alice"})
    'eyJ...'
    """
    payload = dict(payload)
    payload.setdefault("iat", int(time.time()))
    payload.setdefault("exp", int(time.time()) + TOKEN_TTL_SECONDS)
    header = base64.urlsafe_b64encode(json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = _sign(f"{header}.{body}".encode())
    return f"{header}.{body}.{signature}"


def decode_token(token: str) -> dict:
    """Verify signature and expiry, returning the payload.

    Raises ValueError when the token is tampered with or expired.
    """
    try:
        header, body, signature = token.split(".")
    except ValueError:
        raise ValueError("malformed token") from None
    expected = _sign(f"{header}.{body}".encode())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
    padding = "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(body + padding))
    if payload.get("exp", 0) < time.time():
        raise ValueError("token expired")
    return payload
