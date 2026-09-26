"""Round-trip tests for the token helpers."""

from app.auth.jwt import decode_token, encode_token


def test_roundtrip():
    token = encode_token({"sub": "alice"})
    assert decode_token(token)["sub"] == "alice"


def test_tampered_token_rejected():
    token = encode_token({"sub": "alice"})
    try:
        decode_token(token + "x")
        assert False, "expected ValueError"
    except ValueError:
        pass
