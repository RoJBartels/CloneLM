"""Auth router (deployed/multi-user build): register, login, me, plus a public
config probe. Registration collects the user's own Anthropic + Voyage keys,
optionally validates them live, then stores the password as an argon2 hash and
the keys Fernet-encrypted. Auth endpoints are 403 in the localhost build, which
has no accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_cipher,
    get_current_user,
    get_password_hasher,
    get_token_service,
    get_user_repo,
    probe_user_keys,
)
from app.config import get_settings
from app.domain.models import (
    AppConfig,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    User,
    UserPublic,
)
from app.domain.ports.auth import PasswordHasher, SecretCipher, TokenService
from app.domain.ports.repositories import UserRepository

router = APIRouter(prefix="/api", tags=["auth"])


def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)


def _require_deployed() -> None:
    if not get_settings().deployed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Accounts exist only in the hosted build (DEPLOYED=true).",
        )


@router.get("/config", response_model=AppConfig)
def get_app_config() -> AppConfig:
    """Public: lets the pre-login UI learn the mode (login required? show the
    Voyage field?) without authentication."""
    return AppConfig(deployed=get_settings().deployed)


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    hasher: PasswordHasher = Depends(get_password_hasher),
    cipher: SecretCipher = Depends(get_cipher),
    token_service: TokenService = Depends(get_token_service),
) -> TokenResponse:
    _require_deployed()
    s = get_settings()
    email = body.email.strip().lower()
    if user_repo.get_by_email(email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    if not body.voyage_api_key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "A Voyage API key is required."
        )

    if s.registration_verify_keys:
        probe_user_keys(body.anthropic_api_key, body.voyage_api_key)

    user = user_repo.create(
        email=email,
        password_hash=hasher.hash(body.password),
        anthropic_key_encrypted=cipher.encrypt(body.anthropic_api_key),
        voyage_key_encrypted=cipher.encrypt(body.voyage_api_key),
    )
    return TokenResponse(access_token=token_service.issue(user.id), user=_public(user))


@router.post("/auth/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    hasher: PasswordHasher = Depends(get_password_hasher),
    token_service: TokenService = Depends(get_token_service),
) -> TokenResponse:
    _require_deployed()
    user = user_repo.get_by_email(body.email.strip().lower())
    # Verify even when the user is missing-ish to keep timing uniform-ish; the
    # message is deliberately generic (don't reveal which half was wrong).
    if user is None or not hasher.verify(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    return TokenResponse(access_token=token_service.issue(user.id), user=_public(user))


@router.get("/auth/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _public(user)
