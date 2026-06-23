import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "./api/client";
import type {
  AddSourceInput,
  AudioOverview,
  Note,
  Notebook,
  Source,
  StudioKind,
  StudioOutput,
} from "./api/types";
import ChatPane from "./components/ChatPane";
import SourcesPane from "./components/SourcesPane";
import StudioPane from "./components/StudioPane";
import TopBar from "./components/TopBar";

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 60000;

/**
 * Top-level app state: bootstraps/owns the active notebook, fetches sources /
 * notes / studio outputs for it, and wires the three panes together. Source
 * status is polled after an add-source call until every source reaches a
 * terminal state (`ready` or `error`) or the poll window times out.
 */
export default function App() {
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  const [sources, setSources] = useState<Source[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [sourcesLoading, setSourcesLoading] = useState(false);

  const [notes, setNotes] = useState<Note[]>([]);
  const [outputs, setOutputs] = useState<StudioOutput[]>([]);
  const [audios, setAudios] = useState<AudioOverview[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- bootstrap: list notebooks, create one if none exist ---
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await api.listNotebooks();
        if (!alive) return;
        if (list.length > 0) {
          setNotebooks(list);
          setNotebook(list[0]);
        } else {
          const created = await api.createNotebook("Unbenanntes Notebook");
          if (alive) {
            setNotebooks([created]);
            setNotebook(created);
          }
        }
      } catch (e) {
        if (alive) setBootError(e instanceof Error ? e.message : "Notebook konnte nicht geladen werden");
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const refreshNotebooks = useCallback(async () => {
    try {
      const list = await api.listNotebooks();
      setNotebooks(list);
      return list;
    } catch {
      // keep prior list on transient failure
      return notebooks;
    }
  }, [notebooks]);

  const refreshSources = useCallback(async (notebookId: string) => {
    try {
      const list = await api.listSources(notebookId);
      setSources(list);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const s of list) {
          if (!prev.has(s.id) && prev.size === 0) next.add(s.id);
        }
        // drop selections for sources that no longer exist
        for (const id of next) {
          if (!list.some((s) => s.id === id)) next.delete(id);
        }
        return next;
      });
      return list;
    } catch (e) {
      setSourcesError(e instanceof Error ? e.message : "Quellen konnten nicht geladen werden");
      return [];
    }
  }, []);

  const refreshNotes = useCallback(async (notebookId: string) => {
    try {
      setNotes(await api.listNotes(notebookId));
    } catch {
      // notes backend may not be ready yet; keep prior state
    }
  }, []);

  const refreshStudio = useCallback(async (notebookId: string) => {
    try {
      setOutputs(await api.listStudioOutputs(notebookId));
    } catch {
      // studio backend may not be ready yet; keep prior state
    }
  }, []);

  const refreshAudio = useCallback(async (notebookId: string) => {
    try {
      setAudios(await api.listAudio(notebookId));
    } catch {
      // audio backend may not be ready yet; keep prior state
    }
  }, []);

  // --- load notebook-scoped data once the active notebook is known ---
  useEffect(() => {
    if (!notebook) return;
    setSourcesLoading(true);
    void refreshSources(notebook.id).finally(() => setSourcesLoading(false));
    void refreshNotes(notebook.id);
    void refreshStudio(notebook.id);
    void refreshAudio(notebook.id);
  }, [notebook, refreshSources, refreshNotes, refreshStudio, refreshAudio]);

  // --- poll source status while any source is still processing ---
  const startPolling = useCallback(
    (notebookId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      const startedAt = Date.now();
      pollRef.current = setInterval(async () => {
        const list = await refreshSources(notebookId);
        const stillProcessing = list.some((s) => s.status === "processing");
        if (!stillProcessing || Date.now() - startedAt > POLL_TIMEOUT_MS) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }, POLL_INTERVAL_MS);
    },
    [refreshSources],
  );

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  // Switching notebooks clears the per-notebook panes; the data-loading effect
  // (keyed on `notebook`) then refetches sources/notes/studio/audio for the new
  // active notebook, so isolation between notebooks is preserved.
  const resetPanes = () => {
    setSources([]);
    setSelectedIds(new Set());
    setNotes([]);
    setOutputs([]);
    setAudios([]);
    setSourcesError(null);
  };

  const handleSelectNotebook = (id: string) => {
    if (id === notebook?.id) return;
    const target = notebooks.find((n) => n.id === id);
    if (!target) return;
    resetPanes();
    setNotebook(target);
  };

  const handleNewNotebook = async () => {
    try {
      const created = await api.createNotebook("Unbenanntes Notebook");
      setNotebooks((prev) => [created, ...prev]);
      resetPanes();
      setNotebook(created);
    } catch (e) {
      setBootError(e instanceof Error ? e.message : "Notebook konnte nicht erstellt werden");
    }
  };

  const handleRenameNotebook = async (id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    try {
      const updated = await api.updateNotebook(id, trimmed);
      setNotebooks((prev) => prev.map((n) => (n.id === id ? updated : n)));
      if (notebook?.id === id) setNotebook(updated);
    } catch (e) {
      setBootError(e instanceof Error ? e.message : "Notebook konnte nicht umbenannt werden");
    }
  };

  const handleDeleteNotebook = async (id: string) => {
    try {
      await api.deleteNotebook(id);
      const remaining = notebooks.filter((n) => n.id !== id);
      setNotebooks(remaining);
      // If we deleted the active notebook, switch to another — or create a
      // fresh one so the app always has an active notebook.
      if (notebook?.id === id) {
        resetPanes();
        if (remaining.length > 0) {
          setNotebook(remaining[0]);
        } else {
          const created = await api.createNotebook("Unbenanntes Notebook");
          setNotebooks([created]);
          setNotebook(created);
        }
      }
    } catch (e) {
      setBootError(e instanceof Error ? e.message : "Notebook konnte nicht gelöscht werden");
    }
  };

  const handleAddSource = async (input: AddSourceInput) => {
    if (!notebook) return;
    setSourcesError(null);
    await api.addSource(notebook.id, input);
    await refreshSources(notebook.id);
    startPolling(notebook.id);
  };

  const handleDeleteSource = async (id: string) => {
    if (!notebook) return;
    setSourcesError(null);
    try {
      await api.deleteSource(id);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      await refreshSources(notebook.id);
    } catch (e) {
      setSourcesError(e instanceof Error ? e.message : "Quelle konnte nicht gelöscht werden");
    }
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedIds((prev) =>
      prev.size === sources.length ? new Set() : new Set(sources.map((s) => s.id)),
    );
  };

  const handleGenerateStudio = async (kind: StudioKind) => {
    if (!notebook) return;
    const created = await api.generateStudio(notebook.id, kind);
    setOutputs((prev) => [created, ...prev]);
  };

  const handleGenerateAudio = async () => {
    if (!notebook) return;
    // Backend renders synchronously, so the returned overview is already in a
    // terminal (ready/error) state — no polling needed.
    const created = await api.generateAudio(notebook.id);
    setAudios((prev) => [created, ...prev]);
  };

  const handleSaveOutputAsNote = async (output: StudioOutput) => {
    if (!notebook) return;
    const created = await api.createNote(notebook.id, {
      title: output.title,
      content: output.content,
      origin: "studio",
    });
    setNotes((prev) => [created, ...prev]);
  };

  const handleCreateNote = async (title: string, content: string) => {
    if (!notebook) return;
    const created = await api.createNote(notebook.id, { title, content, origin: "manual" });
    setNotes((prev) => [created, ...prev]);
  };

  const handleUpdateNote = async (id: string, title: string, content: string) => {
    const updated = await api.updateNote(id, { title, content });
    setNotes((prev) => prev.map((n) => (n.id === id ? updated : n)));
  };

  const handleDeleteNote = async (id: string) => {
    await api.deleteNote(id);
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  const notebookTitle = notebook?.title ?? "Unbenanntes Notebook";
  const hasReadySource = sources.some((s) => s.status === "ready");
  const selectedSourceIds = Array.from(selectedIds);

  return (
    <div className="flex h-full flex-col bg-white">
      <TopBar
        notebooks={notebooks}
        activeNotebookId={notebook?.id ?? null}
        notebookTitle={notebookTitle}
        onSelectNotebook={handleSelectNotebook}
        onNewNotebook={() => void handleNewNotebook()}
        onRenameNotebook={(id, title) => void handleRenameNotebook(id, title)}
        onDeleteNotebook={(id) => void handleDeleteNotebook(id)}
        onOpenLibrary={() => void refreshNotebooks()}
      />
      {bootError && (
        <p className="bg-danger-100 px-4 py-2 text-sm text-danger-500">{bootError}</p>
      )}
      <main className="flex flex-1 gap-3 overflow-hidden p-3">
        <SourcesPane
          sources={sources}
          selectedIds={selectedIds}
          onToggleSelected={toggleSelected}
          onToggleAll={toggleAll}
          onAddSource={handleAddSource}
          onDeleteSource={handleDeleteSource}
          loading={sourcesLoading}
          error={sourcesError}
        />
        <ChatPane
          notebookId={notebook?.id ?? null}
          title={notebookTitle}
          sourceCount={sources.length}
          hasReadySource={hasReadySource}
          selectedSourceIds={selectedSourceIds}
          onSavedNote={() => notebook && void refreshNotes(notebook.id)}
        />
        <StudioPane
          enabled={hasReadySource}
          notebookId={notebook?.id ?? null}
          outputs={outputs}
          audios={audios}
          notes={notes}
          onGenerate={handleGenerateStudio}
          onGenerateAudio={handleGenerateAudio}
          onSaveOutputAsNote={handleSaveOutputAsNote}
          onCreateNote={handleCreateNote}
          onUpdateNote={handleUpdateNote}
          onDeleteNote={handleDeleteNote}
        />
      </main>
    </div>
  );
}
