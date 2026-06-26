"""Unit tests for the auth adapters (no DB, no app): password hashing, API-key
encryption, and JWT issuing/verification."""
from __future__ import annotations

import uuid

from app.infrastructure.security import (
    Argon2PasswordHasher,
    FernetCipher,
    JwtTokenService,
)


def test_password_is_hashed_one_way_and_verifies() -> None:
    hasher = Argon2PasswordHasher()
    h = hasher.hash("correct horse battery staple")

    assert h != "correct horse battery staple"  # not stored in the clear
    assert hasher.verify("correct horse battery staple", h) is True
    assert hasher.verify("wrong password", h) is False


def test_verify_fails_closed_on_garbage_hash() -> None:
    # The seeded local user's "!" sentinel must never verify.
    assert Argon2PasswordHasher().verify("anything", "!") is False


def test_api_key_encryption_roundtrips_and_hides_plaintext() -> None:
    cipher = FernetCipher("a-test-master-secret")
    token = cipher.encrypt("sk-ant-secret-key")

    assert token != "sk-ant-secret-key"  # ciphertext, not plaintext
    assert "sk-ant-secret-key" not in token
    assert cipher.decrypt(token) == "sk-ant-secret-key"


def test_decrypt_with_wrong_master_key_fails() -> None:
    token = FernetCipher("master-one").encrypt("secret")
    try:
        FernetCipher("master-two").decrypt(token)
    except ValueError:
        return
    raise AssertionError("decrypt with the wrong key should raise")


def test_jwt_roundtrip_and_rejects_tampering() -> None:
    svc = JwtTokenService(secret="signing-secret", expire_minutes=60)
    uid = uuid.uuid4()
    token = svc.issue(uid)

    assert svc.verify(token) == uid
    assert svc.verify(token + "x") is None  # tampered
    assert JwtTokenService("different-secret", 60).verify(token) is None  # wrong key
