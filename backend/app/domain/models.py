"""Pure domain models: entities, value objects, enums, and request/response DTOs.

No I/O, no SDKs, no SQLAlchemy. These pydantic models are the lingua franca
between layers and the shape of the public API (mirrored by the frontend's
``src/api/types.ts``). Treat this module as a FROZEN contract during a sprint
(see PLAN.md "Merge-safety rules").
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class SourceType(str, Enum):
    file = "file"
    paste = "paste"
    url = "url"


class SourceStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    error = "error"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class NoteOrigin(str, Enum):
    manual = "manual"
    chat = "chat"
    studio = "studio"


class StudioKind(str, Enum):
    summary = "summary"
    faq = "faq"
    study_guide = "study_guide"
    briefing = "briefing"
    timeline = "timeline"


class AudioStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    error = "error"


# --------------------------------------------------------------------------- #
# Entities (API-facing). `from_attributes` lets repositories build these
# directly from ORM rows via `Model.model_validate(orm_obj)`.
# --------------------------------------------------------------------------- #


class _Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Notebook(_Entity):
    id: uuid.UUID
    title: str
    created_at: datetime
    source_count: int = 0
    note_count: int = 0


class Source(_Entity):
    id: uuid.UUID
    notebook_id: uuid.UUID
    type: SourceType
    title: str
    uri: str | None = None
    status: SourceStatus = SourceStatus.processing
    error: str | None = None
    chunk_count: int = 0
    created_at: datetime


class Chunk(_Entity):
    """A retrievable unit of a source. Carries the char span back into the
    source's extracted text so citations can highlight the exact passage."""

    id: uuid.UUID
    source_id: uuid.UUID
    notebook_id: uuid.UUID
    ordinal: int
    text: str
    token_count: int = 0
    start_char: int = 0
    end_char: int = 0
    page: int | None = None
    metadata: dict = Field(default_factory=dict)


class Citation(_Entity):
    id: uuid.UUID
    message_id: uuid.UUID | None = None
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    marker: int  # the [n] index shown inline in the answer
    snippet: str  # exact supporting passage text
    start_char: int = 0
    end_char: int = 0
    page: int | None = None


class Conversation(_Entity):
    id: uuid.UUID
    notebook_id: uuid.UUID
    created_at: datetime


class Message(_Entity):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime


class Note(_Entity):
    id: uuid.UUID
    notebook_id: uuid.UUID
    title: str
    content: str
    origin: NoteOrigin = NoteOrigin.manual
    created_at: datetime
    updated_at: datetime


class StudioOutput(_Entity):
    id: uuid.UUID
    notebook_id: uuid.UUID
    kind: StudioKind
    title: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime


class AudioOverview(_Entity):
    id: uuid.UUID
    notebook_id: uuid.UUID
    status: AudioStatus
    url: str | None = None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Value objects used across ports (not persisted directly as-is)
# --------------------------------------------------------------------------- #


class RetrievedChunk(BaseModel):
    """A chunk returned by vector search, with its similarity score. This is the
    unit the grounding prompt is built from and citations are mapped against."""

    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    ordinal: int
    text: str
    score: float
    start_char: int = 0
    end_char: int = 0
    page: int | None = None


class CitationDraft(BaseModel):
    """A citation as produced by the chat/studio service before persistence
    (no id / message_id yet)."""

    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    marker: int
    snippet: str
    start_char: int = 0
    end_char: int = 0
    page: int | None = None


# --------------------------------------------------------------------------- #
# Request / response DTOs (API bodies)
# --------------------------------------------------------------------------- #


class NotebookCreate(BaseModel):
    title: str = Field(default="Unbenanntes Notebook", min_length=1, max_length=200)


class NotebookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SourceCreate(BaseModel):
    """JSON body for non-file sources (paste / url). File uploads come in as
    multipart form-data and don't use this model."""

    type: SourceType
    title: str | None = None
    content: str | None = None  # for type=paste
    url: str | None = None  # for type=url


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: uuid.UUID | None = None


class StudioRequest(BaseModel):
    kind: StudioKind


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = ""
    origin: NoteOrigin = NoteOrigin.manual
    source_ref: str | None = None  # optional pointer to originating message/output


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None


class HealthStatus(BaseModel):
    status: str
    db: str
    version: str


# --------------------------------------------------------------------------- #
# Settings (LLM provider management — never echoes the API key back)
# --------------------------------------------------------------------------- #


class LLMSettings(BaseModel):
    """Current LLM configuration as exposed to the Einstellungen UI. Secrets are
    NEVER returned — only the ``*_api_key_set`` booleans say whether one exists.
    In the deployed build these reflect the signed-in user's own stored keys."""

    llm_provider: str  # configured: anthropic | ollama
    effective_llm_provider: str  # after fallback (e.g. -> fake without a key)
    llm_model: str
    anthropic_api_key_set: bool
    voyage_api_key_set: bool = False
    ollama_base_url: str
    ollama_model: str
    ollama_available: bool
    # True in the hosted build: the UI hides the local-model (Ollama) option and
    # embeddings run on Voyage AI. See Settings.deployed.
    deployed: bool = False


class LLMSettingsUpdate(BaseModel):
    """Partial update from the UI. Omitted / null fields are left unchanged.
    An empty-string api key is ignored (use it to keep the existing key)."""

    llm_provider: str | None = Field(default=None, pattern="^(anthropic|ollama)$")
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None


# --------------------------------------------------------------------------- #
# Auth (deployed build) — accounts, per-user API keys
# --------------------------------------------------------------------------- #


class User(_Entity):
    """Internal account entity. Carries the password hash and encrypted API keys,
    so it is NEVER returned from a route directly — use UserPublic / TokenResponse.
    """

    id: uuid.UUID
    email: str
    password_hash: str
    anthropic_key_encrypted: str | None = None
    voyage_key_encrypted: str | None = None
    created_at: datetime


class UserPublic(BaseModel):
    """Safe projection of a user for API responses (no secrets)."""

    id: uuid.UUID
    email: str
    created_at: datetime


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    # The user brings their own keys. Voyage is required only when deployed
    # (localhost embeds locally with bge-m3); enforced in the route.
    anthropic_api_key: str = Field(min_length=1)
    voyage_api_key: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AppConfig(BaseModel):
    """Public, unauthenticated config so the pre-login UI knows the mode."""

    deployed: bool
