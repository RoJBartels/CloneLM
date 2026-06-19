/**
 * Typed API client (Phase 0b). Talks to the FastAPI backend; in dev the Vite
 * proxy forwards /api and /health to :8000. Phase 3 (Track C) fills in the
 * remaining endpoints — their typed signatures are declared here already.
 */
import type {
  Health,
  Message,
  Note,
  Notebook,
  Source,
  StudioKind,
  StudioOutput,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const notImplemented = (what: string) => {
  throw new Error(`${what} is not implemented yet (Phase 3)`);
};

export const api = {
  // --- live in Phase 0 ---
  getHealth: () => req<Health>("/health"),
  listNotebooks: () => req<Notebook[]>("/api/notebooks"),
  createNotebook: (title: string) =>
    req<Notebook>("/api/notebooks", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getNotebook: (id: string) => req<Notebook>(`/api/notebooks/${id}`),
  listSources: (notebookId: string) =>
    req<Source[]>(`/api/notebooks/${notebookId}/sources`),
  listNotes: (notebookId: string) =>
    req<Note[]>(`/api/notebooks/${notebookId}/notes`),
  listStudioOutputs: (notebookId: string) =>
    req<StudioOutput[]>(`/api/notebooks/${notebookId}/studio`),

  // --- declared for Phase 3; not wired yet ---
  addSource: (_notebookId: string): Promise<Source> => notImplemented("addSource"),
  sendChat: (_notebookId: string, _message: string): Promise<Message> =>
    notImplemented("sendChat"),
  generateStudio: (_notebookId: string, _kind: StudioKind): Promise<StudioOutput> =>
    notImplemented("generateStudio"),
};
