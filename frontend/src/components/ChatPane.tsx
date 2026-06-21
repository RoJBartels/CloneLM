import { useRef, useState } from "react";

import { api } from "../api/client";
import type { Citation } from "../api/types";
import BelegModal from "./BelegModal";

interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  refused?: boolean;
  streaming?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "Was sind die wichtigsten Punkte der Quellen?",
  "Fasse den Inhalt kurz zusammen.",
];

/** Renders assistant text with inline [n] citation chips clickable to open the
 * Beleg modal. Citation markers are matched literally as "[n]" in the text. */
function AnswerText({
  text,
  citations,
  onCiteClick,
}: {
  text: string;
  citations: Citation[];
  onCiteClick: (c: Citation) => void;
}) {
  const byMarker = new Map(citations.map((c) => [c.marker, c]));
  const parts = text.split(/(\[\d+\])/g);
  const inlineMarkers = new Set(
    Array.from(text.matchAll(/\[(\d+)\]/g), (m) => Number(m[1])),
  );
  // Citations the model did not reference inline still need a click-through to
  // their source span; surface them in a footer so no evidence is unreachable.
  const orphanCitations = citations.filter((c) => !inlineMarkers.has(c.marker));
  return (
    <div>
      <p className="whitespace-pre-wrap text-sm text-chrome-900">
        {parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (m) {
            const marker = Number(m[1]);
            const citation = byMarker.get(marker);
            if (citation) {
              return (
                <button
                  key={i}
                  onClick={() => onCiteClick(citation)}
                  className="mx-0.5 inline rounded bg-note-100 px-1.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-note-500 hover:bg-amber-200"
                >
                  [{marker}]
                </button>
              );
            }
          }
          return <span key={i}>{part}</span>;
        })}
      </p>
      {orphanCitations.length > 0 && (
        <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-chrome-500">
          <span>Belege:</span>
          {orphanCitations.map((c) => (
            <button
              key={c.id}
              onClick={() => onCiteClick(c)}
              className="rounded bg-note-100 px-1.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-note-500 hover:bg-amber-200"
            >
              [{c.marker}]
            </button>
          ))}
        </p>
      )}
    </div>
  );
}

export default function ChatPane({
  notebookId,
  title,
  sourceCount,
  hasReadySource,
  selectedSourceIds,
  onSavedNote,
}: {
  notebookId: string | null;
  title: string;
  sourceCount: number;
  hasReadySource: boolean;
  selectedSourceIds: string[];
  onSavedNote: () => void;
}) {
  const today = new Date().toLocaleDateString("de-DE");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [belegCitation, setBelegCitation] = useState<Citation | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const send = async (message: string) => {
    if (!notebookId || !message.trim() || sending) return;
    setError(null);
    setSending(true);

    const userTurn: ChatTurn = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: message,
      citations: [],
    };
    const assistantId = `local-assistant-${Date.now()}`;
    const assistantTurn: ChatTurn = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: [],
      streaming: true,
    };
    setTurns((t) => [...t, userTurn, assistantTurn]);
    setInput("");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await api.streamChat(
        notebookId,
        {
          message,
          conversation_id: conversationId,
          source_ids: selectedSourceIds.length > 0 ? selectedSourceIds : undefined,
        },
        {
          onMeta: (meta) => setConversationId(meta.conversation_id),
          onToken: (tok) =>
            setTurns((cur) =>
              cur.map((t) =>
                t.id === assistantId ? { ...t, content: t.content + tok.text } : t,
              ),
            ),
          onCitation: (citation) =>
            setTurns((cur) =>
              cur.map((t) =>
                t.id === assistantId
                  ? { ...t, citations: [...t.citations, citation] }
                  : t,
              ),
            ),
          onDone: (done) =>
            setTurns((cur) =>
              cur.map((t) =>
                t.id === assistantId
                  ? { ...t, streaming: false, refused: done.refused }
                  : t,
              ),
            ),
          onError: (err) => {
            setError(err.message);
            setTurns((cur) =>
              cur.map((t) =>
                t.id === assistantId ? { ...t, streaming: false } : t,
              ),
            );
          },
        },
        controller.signal,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Senden fehlgeschlagen");
      setTurns((cur) =>
        cur.map((t) => (t.id === assistantId ? { ...t, streaming: false } : t)),
      );
    } finally {
      setSending(false);
    }
  };

  const saveAsNote = async (turn: ChatTurn) => {
    if (!notebookId) return;
    try {
      await api.createNote(notebookId, {
        title: turn.content.slice(0, 60) || "Notiz aus Chat",
        content: turn.content,
        origin: "chat",
      });
      onSavedNote();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Notiz konnte nicht gespeichert werden");
    }
  };

  const showEmpty = turns.length === 0;

  return (
    <section className="flex flex-1 flex-col rounded-lg border border-chrome-400 bg-white p-4">
      <h2 className="mb-2 text-lg font-semibold text-chrome-700">Chat</h2>

      {showEmpty ? (
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="mb-4 h-10 w-11 rounded-md bg-note-100 ring-1 ring-note-500" />
          <h3 className="text-2xl font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-chrome-600">
            {sourceCount} {sourceCount === 1 ? "Quelle" : "Quellen"} · {today}
          </p>
          {!hasReadySource && (
            <div className="mt-6 rounded-lg border border-dashed border-chrome-300 bg-chrome-50 px-6 py-4 text-sm text-chrome-600">
              Fügen Sie eine Quelle hinzu, um Fragen zu stellen.
            </div>
          )}
          {hasReadySource && (
            <div className="mt-6 flex w-full max-w-md flex-col gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => void send(q)}
                  className="rounded-lg bg-chrome-100 px-4 py-2 text-left text-sm text-chrome-900 ring-1 ring-chrome-300 hover:bg-chrome-200"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 space-y-3 overflow-y-auto pb-2">
          {turns.map((t) => (
            <div
              key={t.id}
              className={
                t.role === "user"
                  ? "ml-auto max-w-[85%] rounded-lg bg-src-100 px-3 py-2"
                  : "max-w-[95%] rounded-lg bg-chrome-100 px-3 py-2 ring-1 ring-chrome-300"
              }
            >
              {t.role === "user" ? (
                <p className="text-sm text-chrome-900">{t.content}</p>
              ) : (
                <>
                  {t.refused && (
                    <p className="mb-1 text-xs font-semibold text-danger-500">
                      Keine Antwort aus den Quellen ableitbar
                    </p>
                  )}
                  <AnswerText
                    text={t.content || (t.streaming ? "…" : "")}
                    citations={t.citations}
                    onCiteClick={setBelegCitation}
                  />
                  {!t.streaming && t.content && (
                    <button
                      onClick={() => void saveAsNote(t)}
                      className="mt-2 rounded-md bg-white px-3 py-1.5 text-xs text-chrome-700 ring-1 ring-chrome-400"
                    >
                      In Notiz speichern
                    </button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="mb-2 rounded-md bg-danger-100 px-3 py-2 text-xs text-danger-500">
          {error}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2">
        <input
          disabled={!hasReadySource || sending}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
          placeholder="Text eingeben…"
          className="flex-1 rounded-lg border border-chrome-300 bg-chrome-50 px-3 py-2.5 text-sm placeholder:text-chrome-400 disabled:cursor-not-allowed disabled:opacity-70"
        />
        <span className="text-xs text-chrome-500">
          {selectedSourceIds.length > 0 ? selectedSourceIds.length : sourceCount} Quellen
        </span>
        <button
          disabled={!hasReadySource || sending || !input.trim()}
          onClick={() => void send(input)}
          className="h-9 w-9 rounded-full bg-src-400 text-white disabled:bg-chrome-300"
          aria-label="Senden"
        >
          ↑
        </button>
      </div>

      {belegCitation && (
        <BelegModal citation={belegCitation} onClose={() => setBelegCitation(null)} />
      )}
    </section>
  );
}
