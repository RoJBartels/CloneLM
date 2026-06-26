/**
 * Typed API client. Talks to the FastAPI backend; in dev the Vite proxy
 * forwards /api and /health to :8000. Phase 3 (Track C) fills in the
 * remaining endpoints — multipart source upload, SSE chat streaming, and
 * notes/studio CRUD.
 */
import type {
  AddSourceInput,
  AppConfig,
  AudioOverview,
  AuthResponse,
  AuthUser,
  ChatRequest,
  ChatStreamHandlers,
  Conversation,
  Health,
  LLMSettings,
  LLMSettingsUpdate,
  LoginInput,
  Message,
  Note,
  NoteCreate,
  NoteUpdate,
  Notebook,
  RegisterInput,
  Source,
  StudioKind,
  StudioOutput,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";
const TOKEN_KEY = "clonelm.token";

// --- Auth token (deployed build) -----------------------------------------
// Bearer token in localStorage, attached to every request. On a 401 we clear
// it and notify the app so it can drop back to the login screen.
let _onUnauthorized: (() => void) | null = null;

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
export function onUnauthorized(cb: () => void): void {
  _onUnauthorized = cb;
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAuthToken();
  return token ? { ...(extra ?? {}), Authorization: `Bearer ${token}` } : (extra ?? {});
}

function handleUnauthorized(status: number): void {
  if (status === 401) {
    clearAuthToken();
    _onUnauthorized?.();
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: authHeaders({ "Content-Type": "application/json", ...(init?.headers ?? {}) }),
    ...init,
  });
  if (!res.ok) {
    handleUnauthorized(res.status);
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Multipart requests must NOT set Content-Type manually — the browser sets
 * the correct boundary. */
async function reqForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    body: form,
    headers: authHeaders(init?.headers),
    ...init,
  });
  if (!res.ok) {
    handleUnauthorized(res.status);
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function addSourceForm(input: AddSourceInput): FormData {
  const form = new FormData();
  form.append("type", input.type);
  if (input.title) form.append("title", input.title);
  if (input.type === "paste") form.append("content", input.content);
  if (input.type === "url") form.append("url", input.url);
  if (input.type === "file") form.append("file", input.file);
  return form;
}

/**
 * Consume the chat SSE stream. Uses fetch + ReadableStream reader (not
 * EventSource, since EventSource cannot POST). Parses `event: <name>` /
 * `data: <json>` blocks separated by blank lines per the SSE wire format and
 * dispatches to the matching handler.
 */
async function streamChat(
  notebookId: string,
  body: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/notebooks/${notebookId}/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    handleUnauthorized(res.status);
    const detail = await res.text().catch(() => "");
    const message = `${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`;
    handlers.onError?.({ message });
    throw new Error(message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (eventName: string, data: string) => {
    if (!data) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }
    switch (eventName) {
      case "meta":
        handlers.onMeta?.(parsed as Parameters<NonNullable<ChatStreamHandlers["onMeta"]>>[0]);
        break;
      case "token":
        handlers.onToken?.(parsed as Parameters<NonNullable<ChatStreamHandlers["onToken"]>>[0]);
        break;
      case "citation":
        handlers.onCitation?.(
          parsed as Parameters<NonNullable<ChatStreamHandlers["onCitation"]>>[0],
        );
        break;
      case "done":
        handlers.onDone?.(parsed as Parameters<NonNullable<ChatStreamHandlers["onDone"]>>[0]);
        break;
      case "error":
        handlers.onError?.(parsed as Parameters<NonNullable<ChatStreamHandlers["onError"]>>[0]);
        break;
      default:
        break;
    }
  };

  const processBuffer = () => {
    // SSE events are separated by a blank line; each event may have multiple
    // "field: value" lines. We only care about "event:" and "data:".
    //
    // Per the SSE spec a line may end with CRLF, CR, or LF. sse-starlette emits
    // CRLF (so events are delimited by "\r\n\r\n"), which contains no "\n\n" —
    // splitting on "\n\n" alone would never match and no event would ever be
    // dispatched. Normalize all line endings to LF before parsing. A trailing
    // lone "\r" is held back (it may be the first half of a CRLF split across
    // two reads) so we never turn one CRLF into a spurious blank line.
    let trailingCR = "";
    if (buffer.endsWith("\r")) {
      trailingCR = "\r";
      buffer = buffer.slice(0, -1);
    }
    buffer = buffer.replace(/\r\n|\r/g, "\n") + trailingCR;
    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      dispatch(eventName, dataLines.join("\n"));
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      processBuffer();
    }
    buffer += decoder.decode();
    processBuffer();
  } finally {
    reader.releaseLock();
  }
}

export const api = {
  // --- auth / config (deployed build) ---
  getConfig: () => req<AppConfig>("/api/config"),
  register: (body: RegisterInput) =>
    req<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: LoginInput) =>
    req<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => req<AuthUser>("/api/auth/me"),

  // --- settings (LLM provider / per-user key management) ---
  getSettings: () => req<LLMSettings>("/api/settings"),
  updateSettings: (body: LLMSettingsUpdate) =>
    req<LLMSettings>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),

  // --- notebooks ---
  getHealth: () => req<Health>("/health"),
  listNotebooks: () => req<Notebook[]>("/api/notebooks"),
  createNotebook: (title: string) =>
    req<Notebook>("/api/notebooks", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getNotebook: (id: string) => req<Notebook>(`/api/notebooks/${id}`),
  updateNotebook: (id: string, title: string) =>
    req<Notebook>(`/api/notebooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteNotebook: (id: string) =>
    req<void>(`/api/notebooks/${id}`, { method: "DELETE" }),

  // --- sources ---
  listSources: (notebookId: string) =>
    req<Source[]>(`/api/notebooks/${notebookId}/sources`),
  getSource: (id: string) => req<Source>(`/api/sources/${id}`),
  deleteSource: (id: string) => req<void>(`/api/sources/${id}`, { method: "DELETE" }),
  addSource: (notebookId: string, input: AddSourceInput) =>
    reqForm<Source>(`/api/notebooks/${notebookId}/sources`, addSourceForm(input)),

  // --- chat ---
  streamChat,
  listConversations: (notebookId: string) =>
    req<Conversation[]>(`/api/notebooks/${notebookId}/conversations`),
  listMessages: (conversationId: string) =>
    req<Message[]>(`/api/conversations/${conversationId}/messages`),

  // --- notes ---
  listNotes: (notebookId: string) =>
    req<Note[]>(`/api/notebooks/${notebookId}/notes`),
  createNote: (notebookId: string, body: NoteCreate) =>
    req<Note>(`/api/notebooks/${notebookId}/notes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateNote: (id: string, body: NoteUpdate) =>
    req<Note>(`/api/notes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteNote: (id: string) => req<void>(`/api/notes/${id}`, { method: "DELETE" }),

  // --- studio ---
  listStudioOutputs: (notebookId: string) =>
    req<StudioOutput[]>(`/api/notebooks/${notebookId}/studio`),
  getStudioOutput: (id: string) => req<StudioOutput>(`/api/studio/${id}`),
  generateStudio: (notebookId: string, kind: StudioKind) =>
    req<StudioOutput>(`/api/notebooks/${notebookId}/studio`, {
      method: "POST",
      body: JSON.stringify({ kind }),
    }),

  // --- audio overview (Track F · stretch) ---
  listAudio: (notebookId: string) =>
    req<AudioOverview[]>(`/api/notebooks/${notebookId}/audio`),
  generateAudio: (notebookId: string) =>
    req<AudioOverview>(`/api/notebooks/${notebookId}/audio`, { method: "POST" }),
  /** Absolute src for an audio overview's file, honoring the configured API
   * base (the backend `url` field is a base-relative `/api/...` path). */
  audioFileSrc: (audio: AudioOverview) => (audio.url ? BASE + audio.url : null),
};
