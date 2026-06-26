"""Auth adapters: the only place argon2 / PyJWT / cryptography are imported.

- Passwords  -> argon2id one-way hash (not reversible).
- API keys   -> Fernet authenticated symmetric encryption (reversible: the
               server must decrypt to call Anthropic/Voyage). Master key from
               config (SECRET_ENCRYPTION_KEY), never persisted in the DB.
- Sessions   -> short-lived HS256 JWT carrying the user id.
"""
from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher as _Argon2
from cryptography.fernet import Fernet, InvalidToken

from app.domain.ports.auth import PasswordHasher, SecretCipher, TokenService


class Argon2PasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self._ph = _Argon2()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        # argon2 raises on mismatch AND on a malformed hash (e.g. the local
        # user's "!" sentinel) — both mean "no match".
        try:
            return self._ph.verify(password_hash, password)
        except Exception:  # noqa: BLE001 - any failure = authentication fails closed
            return False


class JwtTokenService(TokenService):
    _ALGO = "HS256"

    def __init__(self, secret: str, expire_minutes: int) -> None:
        self._secret = secret
        self._expire_minutes = expire_minutes

    def issue(self, user_id: uuid.UUID) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=self._ALGO)

    def verify(self, token: str) -> uuid.UUID | None:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._ALGO])
            return uuid.UUID(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return None


class FernetCipher(SecretCipher):
    def __init__(self, master_key: str) -> None:
        self._fernet = Fernet(_coerce_fernet_key(master_key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:  # pragma: no cover - signals key/data mismatch
            raise ValueError("Could not decrypt secret (wrong SECRET_ENCRYPTION_KEY?)") from exc


def _coerce_fernet_key(master_key: str) -> bytes:
    """Accept either a proper Fernet key (urlsafe-base64 32 bytes) or any
    passphrase. A passphrase is folded into a valid 32-byte key via SHA-256 so
    operators can set an arbitrary secret string without generating a Fernet key
    — though a real Fernet key (see RAILWAY.md) is preferred."""
    raw = master_key.encode()
    try:
        if len(base64.urlsafe_b64decode(raw)) == 32:
            return raw
    except Exception:  # noqa: BLE001 - not a valid Fernet key; derive one below
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
