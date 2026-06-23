import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { Notebook } from "../api/types";
import SettingsModal from "./SettingsModal";

type HealthState = "checking" | "online" | "offline";

/** App top bar: logo + notebook library switcher + backend status + actions. */
export default function TopBar({
  notebooks,
  activeNotebookId,
  notebookTitle,
  onSelectNotebook,
  onNewNotebook,
  onRenameNotebook,
  onDeleteNotebook,
  onOpenLibrary,
}: {
  notebooks: Notebook[];
  activeNotebookId: string | null;
  notebookTitle: string;
  onSelectNotebook: (id: string) => void;
  onNewNotebook: () => void;
  onRenameNotebook: (id: string, title: string) => void;
  onDeleteNotebook: (id: string) => void;
  onOpenLibrary: () => void;
}) {
  const [health, setHealth] = useState<HealthState>("checking");
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .getHealth()
      .then(() => alive && setHealth("online"))
      .catch(() => alive && setHealth("offline"));
    return () => {
      alive = false;
    };
  }, []);

  const dot =
    health === "online"
      ? "bg-ok-600"
      : health === "offline"
        ? "bg-danger-500"
        : "bg-chrome-400";
  const label =
    health === "online" ? "Verbunden" : health === "offline" ? "Offline" : "…";

  return (
    <header className="flex h-13 items-center gap-3 border-b border-chrome-400 bg-src-100 px-4 py-2">
      <span className="h-7 w-7 rounded-full bg-src-400 ring-2 ring-src-600" />
      <span className="text-xl font-semibold text-src-600">CloneLM</span>

      <NotebookLibrary
        notebooks={notebooks}
        activeNotebookId={activeNotebookId}
        notebookTitle={notebookTitle}
        onSelectNotebook={onSelectNotebook}
        onNewNotebook={onNewNotebook}
        onRenameNotebook={onRenameNotebook}
        onDeleteNotebook={onDeleteNotebook}
        onOpen={onOpenLibrary}
      />

      <span className="ml-3 flex items-center gap-1.5 text-xs text-chrome-600">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {label}
      </span>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={onNewNotebook}
          className="rounded-md bg-src-200 px-3 py-1.5 text-sm text-src-600 ring-1 ring-src-600"
        >
          + Neues Notebook
        </button>
        <button
          onClick={() => setSettingsOpen(true)}
          title="KI-Modell verwalten"
          className="rounded-md bg-white px-3 py-1.5 text-sm text-chrome-700 ring-1 ring-chrome-400 hover:bg-chrome-50"
        >
          Einstellungen
        </button>
      </div>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </header>
  );
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
}

/**
 * Notebook library: the active title is a dropdown trigger. Opening it lists
 * every notebook (so switching back is possible — creating a new notebook no
 * longer "loses" the old ones) with switch, inline rename, and delete.
 */
function NotebookLibrary({
  notebooks,
  activeNotebookId,
  notebookTitle,
  onSelectNotebook,
  onNewNotebook,
  onRenameNotebook,
  onDeleteNotebook,
  onOpen,
}: {
  notebooks: Notebook[];
  activeNotebookId: string | null;
  notebookTitle: string;
  onSelectNotebook: (id: string) => void;
  onNewNotebook: () => void;
  onRenameNotebook: (id: string, title: string) => void;
  onDeleteNotebook: (id: string) => void;
  onOpen: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setEditingId(null);
      }
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setEditingId(null);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      if (next) onOpen();
      return next;
    });
    setEditingId(null);
  };

  const startRename = (nb: Notebook) => {
    setEditingId(nb.id);
    setDraft(nb.title);
  };

  const commitRename = (id: string) => {
    if (draft.trim()) onRenameNotebook(id, draft);
    setEditingId(null);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={toggle}
        title="Notebook-Bibliothek"
        className="flex items-center gap-1 rounded-md px-1.5 py-1 text-sm text-chrome-700 hover:bg-src-200"
      >
        <span className="max-w-[16rem] truncate">· {notebookTitle}</span>
        <span className="text-[10px] text-chrome-500">▾</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-80 rounded-lg border border-chrome-400 bg-white shadow-xl">
          <div className="border-b border-chrome-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-chrome-600">
            Bibliothek · {notebooks.length} Notebook{notebooks.length === 1 ? "" : "s"}
          </div>

          <ul className="max-h-80 overflow-y-auto py-1">
            {notebooks.map((nb) => {
              const active = nb.id === activeNotebookId;
              return (
                <li key={nb.id} className="group">
                  {editingId === nb.id ? (
                    <div className="flex items-center gap-1 px-2 py-1.5">
                      <input
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitRename(nb.id);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        className="flex-1 rounded border border-src-400 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-src-600"
                      />
                      <button
                        onClick={() => commitRename(nb.id)}
                        className="rounded px-1.5 py-1 text-xs text-src-600 hover:bg-src-100"
                      >
                        OK
                      </button>
                    </div>
                  ) : (
                    <div
                      className={`flex items-center gap-2 px-2 py-1.5 ${
                        active ? "bg-src-100" : "hover:bg-chrome-50"
                      }`}
                    >
                      <button
                        onClick={() => {
                          onSelectNotebook(nb.id);
                          setOpen(false);
                        }}
                        className="flex min-w-0 flex-1 flex-col items-start text-left"
                      >
                        <span
                          className={`flex w-full items-center gap-1.5 truncate text-sm ${
                            active ? "font-semibold text-src-600" : "text-chrome-900"
                          }`}
                        >
                          {active && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-src-600" />}
                          <span className="truncate">{nb.title}</span>
                        </span>
                        <span className="text-[11px] text-chrome-500">
                          {nb.source_count} Quelle{nb.source_count === 1 ? "" : "n"} ·{" "}
                          {nb.note_count} Notiz{nb.note_count === 1 ? "" : "en"} · {fmtDate(nb.created_at)}
                        </span>
                      </button>
                      <button
                        onClick={() => startRename(nb)}
                        title="Umbenennen"
                        aria-label="Notebook umbenennen"
                        className="rounded p-1 text-chrome-400 opacity-0 hover:bg-chrome-100 hover:text-chrome-700 group-hover:opacity-100"
                      >
                        ✎
                      </button>
                      <button
                        onClick={() => {
                          if (
                            window.confirm(
                              `Notebook „${nb.title}“ und alle zugehörigen Quellen, Notizen und Chats löschen?`,
                            )
                          ) {
                            onDeleteNotebook(nb.id);
                          }
                        }}
                        title="Löschen"
                        aria-label="Notebook löschen"
                        className="rounded p-1 text-chrome-400 opacity-0 hover:bg-danger-100 hover:text-danger-500 group-hover:opacity-100"
                      >
                        🗑
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
            {notebooks.length === 0 && (
              <li className="px-3 py-3 text-sm text-chrome-500">Noch keine Notebooks.</li>
            )}
          </ul>

          <button
            onClick={() => {
              onNewNotebook();
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 border-t border-chrome-200 px-3 py-2.5 text-sm font-medium text-src-600 hover:bg-src-100"
          >
            + Neues Notebook
          </button>
        </div>
      )}
    </div>
  );
}
