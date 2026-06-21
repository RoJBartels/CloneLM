import { useState } from "react";

import type { Note } from "../api/types";
import Modal from "./Modal";

/** Manual note create/edit modal, opened from "+ Notiz hinzufügen" or the
 * edit pencil on an existing note. */
export default function NoteModal({
  note,
  onClose,
  onSave,
}: {
  note: Note | null;
  onClose: () => void;
  onSave: (title: string, content: string) => Promise<void>;
}) {
  const [title, setTitle] = useState(note?.title ?? "");
  const [content, setContent] = useState(note?.content ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(title.trim(), content);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
      setBusy(false);
    }
  };

  return (
    <Modal title={note ? "Notiz bearbeiten" : "Notiz hinzufügen"} onClose={onClose}>
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-md bg-danger-100 px-3 py-2 text-sm text-danger-500">{error}</p>
        )}
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Titel"
          className="rounded-lg border border-chrome-300 px-3 py-2.5 text-sm"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Inhalt…"
          rows={8}
          className="rounded-lg border border-chrome-300 px-3 py-2.5 text-sm"
        />
        <button
          disabled={busy || !title.trim()}
          onClick={() => void save()}
          className="self-end rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-50"
        >
          {busy ? "Speichert…" : "Speichern"}
        </button>
      </div>
    </Modal>
  );
}
