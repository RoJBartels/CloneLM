"""Multi-user (deployed build) tests: registration/login, per-user key secrecy,
per-user data isolation, and per-user provider wiring.

A fixture flips the app into deployed mode (DEPLOYED=true + auth secrets) and
disables the live key probe so fake keys are accepted offline. Requires Postgres
(migrated to head, incl. 0002).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import deps
from app.config import get_settings
from app.infrastructure.persistence.db import get_sessionmaker


def _clear_caches() -> None:
    get_settings.cache_clear()
    deps.get_token_service.cache_clear()
    deps.get_cipher.cache_clear()
    deps.get_password_hasher.cache_clear()
    deps.get_llm.cache_clear()
    deps.get_embedder.cache_clear()


@pytest.fixture
def deployed_client(db_available, monkeypatch):
    monkeypatch.setenv("DEPLOYED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "test-encryption-master-key")
    monkeypatch.setenv("REGISTRATION_VERIFY_KEYS", "false")  # accept fake keys offline
    _clear_caches()
    from app.main import app

    yield TestClient(app)
    # monkeypatch restores env; clear caches so later tests see localhost again.
    _clear_caches()


def _register(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "anthropic_api_key": f"sk-ant-{email}",
            "voyage_api_key": f"pa-{email}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Config + auth flow
# --------------------------------------------------------------------------- #


def test_config_reports_deployed(deployed_client) -> None:
    assert deployed_client.get("/api/config").json() == {"deployed": True}


def test_register_login_me_flow(deployed_client) -> None:
    token = _register(deployed_client, f"a-{uuid.uuid4().hex[:8]}@x.com")
    me = deployed_client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["email"].endswith("@x.com")

    # Login with the same credentials returns a working token.
    email = me.json()["email"]
    login = deployed_client.post(
        "/api/auth/login", json={"email": email, "password": "hunter2hunter2"}
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_duplicate_email_conflicts(deployed_client) -> None:
    email = f"dup-{uuid.uuid4().hex[:8]}@x.com"
    _register(deployed_client, email)
    again = deployed_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "anthropic_api_key": "sk-ant-x",
            "voyage_api_key": "pa-x",
        },
    )
    assert again.status_code == 409


def test_login_wrong_password_rejected(deployed_client) -> None:
    email = f"pw-{uuid.uuid4().hex[:8]}@x.com"
    _register(deployed_client, email)
    bad = deployed_client.post(
        "/api/auth/login", json={"email": email, "password": "not-the-password"}
    )
    assert bad.status_code == 401


def test_protected_route_requires_token(deployed_client) -> None:
    assert deployed_client.get("/api/notebooks").status_code == 401
    assert deployed_client.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------------- #
# Secrets are stored encrypted, never echoed
# --------------------------------------------------------------------------- #


def test_keys_are_encrypted_at_rest_and_never_returned(deployed_client) -> None:
    email = f"sec-{uuid.uuid4().hex[:8]}@x.com"
    token = _register(deployed_client, email)

    # Settings reports presence only — never the key material.
    s = deployed_client.get("/api/settings", headers=_auth(token)).json()
    assert s["anthropic_api_key_set"] is True
    assert s["voyage_api_key_set"] is True
    assert "sk-ant" not in str(s) and "pa-" not in str(s)

    # In the DB the stored column is ciphertext, not the plaintext key.
    session = get_sessionmaker()()
    try:
        row = session.execute(
            text("SELECT anthropic_key_encrypted FROM app_user WHERE email = :e"),
            {"e": email},
        ).first()
    finally:
        session.close()
    assert row is not None
    assert f"sk-ant-{email}" not in row[0]


# --------------------------------------------------------------------------- #
# Per-user data isolation
# --------------------------------------------------------------------------- #


def test_users_cannot_see_or_touch_each_others_notebooks(deployed_client) -> None:
    a = _register(deployed_client, f"owner-{uuid.uuid4().hex[:8]}@x.com")
    b = _register(deployed_client, f"intruder-{uuid.uuid4().hex[:8]}@x.com")

    na = deployed_client.post("/api/notebooks", json={"title": "A"}, headers=_auth(a)).json()
    deployed_client.post("/api/notebooks", json={"title": "B"}, headers=_auth(b))

    # Each user lists only their own notebooks.
    a_ids = {n["id"] for n in deployed_client.get("/api/notebooks", headers=_auth(a)).json()}
    b_ids = {n["id"] for n in deployed_client.get("/api/notebooks", headers=_auth(b)).json()}
    assert na["id"] in a_ids
    assert na["id"] not in b_ids

    # B cannot read / mutate A's notebook — 404 (not 403), so existence doesn't leak.
    nid = na["id"]
    assert deployed_client.get(f"/api/notebooks/{nid}", headers=_auth(b)).status_code == 404
    assert deployed_client.patch(
        f"/api/notebooks/{nid}", json={"title": "hax"}, headers=_auth(b)
    ).status_code == 404
    assert deployed_client.delete(f"/api/notebooks/{nid}", headers=_auth(b)).status_code == 404

    # B cannot reach A's child resources either.
    assert deployed_client.get(f"/api/notebooks/{nid}/sources", headers=_auth(b)).status_code == 404
    assert deployed_client.post(
        f"/api/notebooks/{nid}/notes", json={"title": "x", "content": "y"}, headers=_auth(b)
    ).status_code == 404

    # A still owns it.
    assert deployed_client.get(f"/api/notebooks/{nid}", headers=_auth(a)).status_code == 200


# --------------------------------------------------------------------------- #
# Provider wiring: deployed providers are built from the user's own keys
# --------------------------------------------------------------------------- #


def test_deployed_providers_built_from_user_keys(deployed_client) -> None:
    from app.domain.models import User
    from app.infrastructure.providers.anthropic_llm import AnthropicLLMProvider
    from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
    from app.infrastructure.providers.fake_llm import FakeLLMProvider
    from app.infrastructure.providers.voyage_embeddings import VoyageEmbeddingProvider

    cipher = deps.get_cipher()
    user = User(
        id=uuid.uuid4(),
        email="wiring@x.com",
        password_hash="!",
        anthropic_key_encrypted=cipher.encrypt("sk-ant-user"),
        voyage_key_encrypted=cipher.encrypt("pa-user"),
        created_at=__import__("datetime").datetime.now(),
    )

    llm = deps.get_user_llm(user=user, local_llm=FakeLLMProvider())
    embedder = deps.get_user_embedder(user=user, local_embedder=FakeEmbeddingProvider(dim=1024))

    assert isinstance(llm, AnthropicLLMProvider)
    assert isinstance(embedder, VoyageEmbeddingProvider)
    assert embedder.model_id == get_settings().voyage_model
