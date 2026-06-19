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

export interface Health {
  status: string;
  db: string;
  version: string;
}
