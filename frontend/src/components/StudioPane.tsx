import { useState } from "react";

import type { Citation, Note, StudioKind, StudioOutput } from "../api/types";
import BelegModal from "./BelegModal";
import NoteModal from "./NoteModal";

const TILES: { kind: StudioKind | "audio"; label: string; cls: string }[] = [
  { kind: "summary", label: "Zusammenfassung", cls: "bg-studio-200 text-studio-600" },
  { kind: "faq", label: "FAQ", cls: "bg-[#c3fae8] text-[#0c8599]" },
  { kind: "study_guide", label: "Study Guide", cls: "bg-[#ffd8a8] text-[#e8590c]" },
  { kind: "briefing", label: "Briefing", cls: "bg-ok-100 text-ok-600" },
  { kind: "timeline", label: "Timeline", cls: "bg-src-200 text-src-600" },
  { kind: "audio", label: "Audio (Stretch)", cls: "bg-[#eebefa] text-[#ae3ec9]" },
];

/** Renders artifact text with inline [n] citation chips, same convention as
 * the chat pane's answer rendering. */
function ArtifactText({
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
  return (
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
  );
}

/** Right pane (Track E/D). Tiles generate grounded artifacts; disabled until a
 * source is ready. Artifacts and manual notes are both manageable here. */
export default function StudioPane({
  enabled,
  notebookId,
  outputs,
  notes,
  onGenerate,
  onSaveOutputAsNote,
  onCreateNote,
  onUpdateNote,
  onDeleteNote,
}: {
  enabled: boolean;
  notebookId: string | null;
  outputs: StudioOutput[];
  notes: Note[];
  onGenerate: (kind: StudioKind) => Promise<void>;
  onSaveOutputAsNote: (output: StudioOutput) => Promise<void>;
  onCreateNote: (title: string, content: string) => Promise<void>;
  onUpdateNote: (id: string, title: string, content: string) => Promise<void>;
  onDeleteNote: (id: string) => Promise<void>;
}) {
  const [pending, setPending] = useState<StudioKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [belegCitation, setBelegCitation] = useState<Citation | null>(null);
  const [noteModalOpen, setNoteModalOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<Note | null>(null);

  const generate = async (kind: StudioKind | "audio") => {
    if (kind === "audio" || !enabled || !notebookId) return;
    setError(null);
    setPending(kind);
    try {
      await onGenerate(kind);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generierung fehlgeschlagen");
    } finally {
      setPending(null);
    }
  };

  return (
    <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-studio-400 bg-studio-100 p-3">
      <h2 className="mb-2 text-lg font-semibold text-studio-600">Studio</h2>

      <div className="grid grid-cols-2 gap-2">
        {TILES.map((t) => (
          <button
            key={t.kind}
            disabled={!enabled || t.kind === "audio" || pending !== null}
            onClick={() => void generate(t.kind)}
            className={`rounded-md px-2 py-4 text-sm font-medium ring-1 ring-black/10 ${t.cls} ${
              !enabled || t.kind === "audio" ? "cursor-not-allowed opacity-45" : ""
            }`}
          >
            {pending === t.kind ? "…" : t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mt-2 rounded-md bg-danger-100 px-2 py-1.5 text-xs text-danger-500">
          {error}
        </p>
      )}

      <div className="mt-4 flex-1 overflow-y-auto rounded-md bg-white/70 p-3 text-xs text-chrome-600">
        {!enabled ? (
          "Hier wird die Ausgabe von Studio gespeichert. Nachdem Sie Quellen hinzugefügt haben, erstellen Sie Audio-Übersichten, Arbeitshilfen u. v. m."
        ) : (
          <>
            <p className="mb-2 font-medium text-chrome-700">
              Generierte Artefakte (als Notiz speicherbar)
            </p>
            {outputs.length === 0 && notes.length === 0 && (
              <p className="text-chrome-500">Noch keine Artefakte oder Notizen.</p>
            )}
            <ul className="space-y-2">
              {outputs.map((o) => (
                <li key={o.id} className="rounded-md bg-white p-2 ring-1 ring-chrome-300">
                  <p className="mb-1 text-xs font-semibold text-studio-600">{o.title}</p>
                  <ArtifactText
                    text={o.content}
                    citations={o.citations}
                    onCiteClick={setBelegCitation}
                  />
                  <button
                    onClick={() => void onSaveOutputAsNote(o)}
                    className="mt-1 rounded-md bg-white px-2 py-1 text-xs text-chrome-700 ring-1 ring-chrome-400"
                  >
                    In Notiz speichern
                  </button>
                </li>
              ))}
              {notes.map((n) => (
                <li key={n.id} className="rounded-md bg-white p-2 ring-1 ring-chrome-300">
                  <div className="mb-1 flex items-center justify-between">
                    <p className="text-xs font-semibold text-chrome-700">{n.title}</p>
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          setEditingNote(n);
                          setNoteModalOpen(true);
                        }}
                        className="text-xs text-chrome-500 hover:text-chrome-900"
                        aria-label="Bearbeiten"
                      >
                        ✎
                      </button>
                      <button
                        onClick={() => void onDeleteNote(n.id)}
                        className="text-xs text-chrome-500 hover:text-danger-500"
                        aria-label="Löschen"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <p className="whitespace-pre-wrap text-chrome-900">{n.content}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <button
        onClick={() => {
          setEditingNote(null);
          setNoteModalOpen(true);
        }}
        className="mt-3 rounded-md bg-white px-3 py-2 text-sm text-chrome-900 ring-1 ring-chrome-700"
      >
        + Notiz hinzufügen
      </button>

      {belegCitation && (
        <BelegModal citation={belegCitation} onClose={() => setBelegCitation(null)} />
      )}

      {noteModalOpen && (
        <NoteModal
          note={editingNote}
          onClose={() => setNoteModalOpen(false)}
          onSave={async (titleVal, contentVal) => {
            if (editingNote) {
              await onUpdateNote(editingNote.id, titleVal, contentVal);
            } else {
              await onCreateNote(titleVal, contentVal);
            }
            setNoteModalOpen(false);
          }}
        />
      )}
    </aside>
  );
}
