"""Chat router — CONTRACT STUB (Track B · Retrieval+Chat, Phase 2 · CORE).

POST streams a grounded, cited answer over SSE. Track B implements retrieval ->
grounding prompt -> LLM with structured citations -> citation mapping -> refusal,
and publishes the reusable grounded-generation core that Studio (Track E) reuses.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_conversation_repo, get_message_repo
from app.domain.models import ChatRequest, Conversation, Message
from app.domain.ports.repositories import ConversationRepository, MessageRepository

router = APIRouter(prefix="/api", tags=["chat"])

_TODO = "Not implemented yet — Track B (Retrieval+Chat, Phase 2)."


@router.post("/notebooks/{notebook_id}/chat")
def chat(notebook_id: uuid.UUID, body: ChatRequest):
    """Stream a grounded answer (SSE: token / citation / done / error events)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.get("/notebooks/{notebook_id}/conversations", response_model=list[Conversation])
def list_conversations(
    notebook_id: uuid.UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> list[Conversation]:
    return repo.list_for_notebook(notebook_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[Message])
def list_messages(
    conversation_id: uuid.UUID, repo: MessageRepository = Depends(get_message_repo)
) -> list[Message]:
    return repo.list_for_conversation(conversation_id)
