from datetime import datetime, timedelta, timezone

import jwt

from app import config
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifies():
    hashed = hash_password("correct-horse-1")
    assert hashed != "correct-horse-1"
    assert hashed.startswith("$2")
    assert verify_password("correct-horse-1", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_gets_different_hashes():
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_token_round_trip():
    assert decode_token(create_access_token(42)) == 42


def test_token_signed_with_another_key_is_rejected():
    soon = datetime.now(timezone.utc) + timedelta(minutes=5)
    forged = jwt.encode({"sub": "1", "exp": soon}, "x" * 40, algorithm="HS256")
    assert decode_token(forged) is None


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    expired = jwt.encode({"sub": "1", "exp": past}, config.SECRET_KEY, algorithm="HS256")
    assert decode_token(expired) is None


def test_garbage_token_is_rejected():
    assert decode_token("not-a-token") is None