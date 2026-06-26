"""Auth ports. Implemented by infrastructure adapters (argon2 hasher, JWT token
service, Fernet cipher). Like the LLM/embedding ports, these keep the external
crypto libraries out of the services/domain layers — never import them here."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str:
        """Return a one-way hash suitable for storage."""

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool:
        """True iff ``password`` matches ``password_hash``. Never raises."""


class TokenService(ABC):
    @abstractmethod
    def issue(self, user_id: uuid.UUID) -> str:
        """Issue a signed access token carrying the user id."""

    @abstractmethod
    def verify(self, token: str) -> uuid.UUID | None:
        """Return the user id if the token is valid and unexpired, else None."""


class SecretCipher(ABC):
    """Reversible authenticated encryption for secrets that must be used later
    (API keys), as opposed to passwords which are one-way hashed."""

    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, token: str) -> str: ...
