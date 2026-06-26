"""Chat router (Track B · Retrieval+Chat, Phase 2 · CORE).

POST streams a grounded, cited answer over Server-Sent Events. The handler
composes the reusable grounded-generation core (retrieval -> grounding prompt ->
LLM structured citations -> citation mapping -> refusal) from injected deps,
persists the user + assistant turns, and emits the agreed SSE contract that
Track C (frontend) consumes:

    event: meta      data: {"conversation_id", "user_message_id"}
    event: token     data: {"text"}                       (repeated)
    event: citation  data: <Citation as JSON>             (repeated, after answer)
    event: done      data: {"message_id", "conversation_id", "refused"}
    event: error     data: {"message"}

We compute the full grounded (structured/cited) answer first, then "stream" the
resulting text token-by-token followed by citation/done events. This keeps
citation mapping reliable — correctness of citations comes before a true token
stream.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.api.deps import (
    assert_notebook_owner,
    get_conversation_repo,
    get_current_user,
    get_message_repo,
    get_notebook_repo,
    get_user_embedder,
    get_user_llm,
    get_vector_store,
)
from app.config import get_settings
from app.domain.models import (
    ChatRequest,
    Conversation,
    Message,
    MessageRole,
    User,
)
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.repositories import (
    ConversationRepository,
    MessageRepository,
    NotebookRepository,
)
from app.domain.ports.vector_store import VectorStore
from app.services.chat import GroundedGenerator

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/notebooks/{notebook_id}/chat")
def chat(
    notebook_id: uuid.UUID,
    body: ChatRequest,
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_user_embedder),
    llm: LLMProvider = Depends(get_user_llm),
    user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """Stream a grounded answer (SSE: meta / token / citation / done / error)."""
    assert_notebook_owner(notebook_repo, notebook_id, user)

    # Get-or-create the conversation, scoped to this notebook.
    conversation = _resolve_conversation(
        conversation_repo, notebook_id, body.conversation_id
    )

    # Persist the user turn up-front so it survives even if generation fails.
    user_message = message_repo.add(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=body.message,
    )

    settings = get_settings()
    generator = GroundedGenerator(
        vector_store,
        embedder,
        llm,
        default_top_k=settings.retrieval_top_k,
        max_tokens=settings.llm_max_tokens,
    )

    event_stream = _stream_chat(
        generator=generator,
        message_repo=message_repo,
        notebook_id=notebook_id,
        conversation=conversation,
        user_message=user_message,
        query=body.message,
    )
    return EventSourceResponse(event_stream)


def _resolve_conversation(
    repo: ConversationRepository,
    notebook_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
) -> Conversation:
    """Return the requested conversation (validated for this notebook) or a new one."""
    if conversation_id is not None:
        existing = repo.get(conversation_id)
        if existing is not None and existing.notebook_id == notebook_id:
            return existing
        # Unknown id or cross-notebook id -> start a fresh conversation rather
        # than leaking another notebook's thread (notebook isolation).
    return repo.create(notebook_id)


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


def _stream_chat(
    *,
    generator: GroundedGenerator,
    message_repo: MessageRepository,
    notebook_id: uuid.UUID,
    conversation: Conversation,
    user_message: Message,
    query: str,
) -> Iterator[dict]:
    """Generate the grounded answer, persist it, and emit the SSE event sequence."""
    yield _sse(
        "meta",
        {
            "conversation_id": str(conversation.id),
            "user_message_id": str(user_message.id),
        },
    )

    try:
        result = generator.generate(notebook_id=notebook_id, query=query)
    except Exception as exc:  # noqa: BLE001 — surface any failure as an SSE error
        yield _sse("error", {"message": f"Generierung fehlgeschlagen: {exc}"})
        return

    # Persist the assistant turn + its citations atomically.
    assistant_message = message_repo.add(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=result.text,
        citations=result.citations,
    )

    # "Stream" the answer text token-by-token (whitespace-preserving split).
    for token in _tokenize(result.text):
        yield _sse("token", {"text": token})

    # Emit each persisted citation (with the assistant message id).
    for citation in assistant_message.citations:
        yield _sse("citation", citation.model_dump(mode="json"))

    yield _sse(
        "done",
        {
            "message_id": str(assistant_message.id),
            "conversation_id": str(conversation.id),
            "refused": result.refused,
        },
    )


def _tokenize(text: str) -> Iterator[str]:
    """Split into whitespace-preserving chunks so reassembly is lossless."""
    if not text:
        return
    buf = ""
    for ch in text:
        buf += ch
        if ch == " ":
            yield buf
            buf = ""
    if buf:
        yield buf


@router.get("/notebooks/{notebook_id}/conversations", response_model=list[Conversation])
def list_conversations(
    notebook_id: uuid.UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    return repo.list_for_notebook(notebook_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[Message])
def list_messages(
    conversation_id: uuid.UUID,
    repo: MessageRepository = Depends(get_message_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[Message]:
    conversation = conversation_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    assert_notebook_owner(notebook_repo, conversation.notebook_id, user)
    return repo.list_for_conversation(conversation_id)
