import { useState } from "react";

import type { AddSourceInput, Source } from "../api/types";
import AddSourceModal from "./AddSourceModal";

const TYPE_LABEL: Record<Source["type"], string> = {
  file: "PDF",
  paste: "TXT",
  url: "URL",
};

/** Left pane (Track A data). Lists sources with type badge + status, lets the
 * user pick which sources scope the chat (per-source checkbox + "Alle
 * auswählen"), and opens the add-sources modal. */
export default function SourcesPane({
  sources,
  selectedIds,
  onToggleSelected,
  onToggleAll,
  onAddSource,
  loading,
  error,
}: {
  sources: Source[];
  selectedIds: Set<string>;
  onToggleSelected: (id: string) => void;
  onToggleAll: () => void;
  onAddSource: (input: AddSourceInput) => Promise<void>;
  loading: boolean;
  error: string | null;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const allSelected = sources.length > 0 && selectedIds.size === sources.length;

  return (
    <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-src-400 bg-src-100 p-3">
      <h2 className="mb-2 text-lg font-semibold text-src-600">Quellen</h2>

      <button
        onClick={() => setModalOpen(true)}
        className="mb-2 rounded-md bg-src-200 px-3 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600"
      >
        + Quellen hinzufügen
      </button>
      <button
        disabled
        title="Demnächst verfügbar"
        className="mb-4 cursor-not-allowed rounded-md bg-white px-3 py-2 text-sm text-chrome-700 opacity-60 ring-1 ring-chrome-400"
      >
        Web-Recherche
      </button>

      {error && (
        <p className="mb-2 rounded-md bg-danger-100 px-2 py-1.5 text-xs text-danger-500">
          {error}
        </p>
      )}

      {sources.length === 0 ? (
        <div className="mt-10 flex flex-1 flex-col items-center px-4 text-center">
          <div className="mb-4 h-13 w-10 rounded-md border border-chrome-400 bg-chrome-50" />
          <p className="text-sm text-chrome-700">
            Gespeicherte Quellen werden hier angezeigt
          </p>
          <p className="mt-3 text-xs text-chrome-600">
            Klicken Sie auf „Quellen hinzufügen“, um PDFs, Websites, Text, Videos
            oder Audio hinzuzufügen.
          </p>
        </div>
      ) : (
        <>
          <label className="mb-2 flex items-center gap-2 px-1 text-sm text-chrome-700">
            <input type="checkbox" checked={allSelected} onChange={onToggleAll} />
            Alle auswählen
          </label>
          <ul className="space-y-2 overflow-y-auto">
            {sources.map((s) => (
              <li
                key={s.id}
                className="flex items-center gap-2 rounded-md bg-white px-2 py-2 ring-1 ring-chrome-400"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(s.id)}
                  onChange={() => onToggleSelected(s.id)}
                />
                <span className="rounded bg-danger-100 px-1.5 py-0.5 text-xs font-semibold text-danger-500">
                  {TYPE_LABEL[s.type]}
                </span>
                <span className="flex-1 truncate text-sm" title={s.title}>
                  {s.title}
                </span>
                {s.status === "ready" && (
                  <span className="rounded bg-ok-100 px-1.5 py-0.5 text-xs text-ok-600">
                    bereit
                  </span>
                )}
                {s.status === "processing" && (
                  <span className="rounded bg-chrome-100 px-1.5 py-0.5 text-xs text-chrome-600">
                    verarbeitet…
                  </span>
                )}
                {s.status === "error" && (
                  <span
                    className="rounded bg-danger-100 px-1.5 py-0.5 text-xs text-danger-500"
                    title={s.error ?? "Fehler"}
                  >
                    Fehler
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {loading && <p className="mt-2 text-xs text-chrome-500">Lädt…</p>}

      {modalOpen && (
        <AddSourceModal onClose={() => setModalOpen(false)} onSubmit={onAddSource} />
      )}
    </aside>
  );
}
