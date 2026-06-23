/**
 * TypeScript mirror of the backend JSON contract (Phase 0a).
 * The wire format is snake_case — these interfaces match it exactly so the
 * typed client can pass payloads through without remapping.
 */

export interface Notebook {
  id: string;
  title: string;
  created_at: string;
  source_count: number;
  note_count: number;
}

export type SourceType = "file" | "paste" | "url";
export type SourceStatus = "processing" | "ready" | "error";

export interface Source {
  id: string;
  notebook_id: string;
  type: SourceType;
  title: string;
  uri: string | null;
  status: SourceStatus;
  error: string | null;
  chunk_count: number;
  created_at: string;
}

export interface Citation {
  id: string;
  message_id: string;
  chunk_id: string;
  source_id: string;
  source_title: string;
  marker: number;
  snippet: string;
  start_char: number;
  end_char: number;
  page: number | null;
}

export interface Conversation {
  id: string;
  notebook_id: string;
  created_at: string;
}

export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  created_at: string;
}

export type StudioKind =
  | "summary"
  | "faq"
  | "study_guide"
  | "briefing"
  | "timeline";

export interface StudioOutput {
  id: string;
  notebook_id: string;
  kind: StudioKind;
  title: string;
  content: string;
  citations: Citation[];
  created_at: string;
}

export type AudioStatus = "processing" | "ready" | "error";

export interface AudioOverview {
  id: string;
  notebook_id: string;
  status: AudioStatus;
  url: string | null;
  created_at: string;
}

export type NoteOrigin = "manual" | "chat" | "studio";

export interface Note {
  id: string;
  notebook_id: string;
  title: string;
  content: string;
  origin: NoteOrigin;
  created_at: string;
  updated_at: string;
}

export interface NoteCreate {
  title: string;
  content?: string;
  origin?: NoteOrigin;
  source_ref?: string | null;
}

export interface NoteUpdate {
  title?: string;
  content?: string;
}

export interface Health {
  status: string;
  db: string;
  version: string;
}

// --- settings (LLM provider management) ---

export type LLMProviderChoice = "anthropic" | "ollama";

export interface LLMSettings {
  llm_provider: LLMProviderChoice;
  /** Provider actually in use after fallback (e.g. "fake" when Anthropic is
   * selected but no key is set). */
  effective_llm_provider: string;
  llm_model: string;
  /** Whether an Anthropic key is stored. The key itself is never returned. */
  anthropic_api_key_set: boolean;
  ollama_base_url: string;
  ollama_model: string;
  ollama_available: boolean;
}

export interface LLMSettingsUpdate {
  llm_provider?: LLMProviderChoice;
  /** Send a non-empty value to set/replace the key; omit/blank to keep it. */
  anthropic_api_key?: string;
  ollama_base_url?: string;
  ollama_model?: string;
}

// --- chat (SSE) ---

export interface ChatRequest {
  message: string;
  conversation_id?: string | null;
  source_ids?: string[] | null;
}

export interface ChatMetaEvent {
  conversation_id: string;
  user_message_id: string;
}

export interface ChatDoneEvent {
  message_id: string;
  conversation_id: string;
  refused: boolean;
}

export interface ChatErrorEvent {
  message: string;
}

export interface ChatTokenEvent {
  text: string;
}

export type ChatStreamHandlers = {
  onMeta?: (meta: ChatMetaEvent) => void;
  onToken?: (token: ChatTokenEvent) => void;
  onCitation?: (citation: Citation) => void;
  onDone?: (done: ChatDoneEvent) => void;
  onError?: (error: ChatErrorEvent) => void;
};

// --- source creation (multipart) ---

export interface AddSourcePasteInput {
  type: "paste";
  title?: string;
  content: string;
}

export interface AddSourceUrlInput {
  type: "url";
  title?: string;
  url: string;
}

export interface AddSourceFileInput {
  type: "file";
  title?: string;
  file: File;
}

export type AddSourceInput =
  | AddSourcePasteInput
  | AddSourceUrlInput
  | AddSourceFileInput;
