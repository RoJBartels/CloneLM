import { useRef, useState } from "react";

import type { AddSourceInput } from "../api/types";
import Modal from "./Modal";

type Tab = "upload" | "url" | "drive" | "paste";

/**
 * Quellen-hinzufügen modal: Hochladen · Websites · Drive (disabled) ·
 * Text einfügen. Supports file drop + paste + URL, per the design.
 */
export default function AddSourceModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (input: AddSourceInput) => Promise<void>;
}) {
  const [tab, setTab] = useState<Tab>("upload");
  const [url, setUrl] = useState("");
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteContent, setPasteContent] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submitFile = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ type: "file", title: file.name, file });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hochladen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const submitUrl = async () => {
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ type: "url", url: url.trim() });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "URL konnte nicht hinzugefügt werden");
    } finally {
      setBusy(false);
    }
  };

  const submitPaste = async () => {
    if (!pasteContent.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        type: "paste",
        title: pasteTitle.trim() || undefined,
        content: pasteContent.trim(),
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Text konnte nicht hinzugefügt werden");
    } finally {
      setBusy(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "upload", label: "Hochladen" },
    { key: "url", label: "Websites" },
    { key: "drive", label: "Drive" },
    { key: "paste", label: "Text einfügen" },
  ];

  return (
    <Modal title="Quellen hinzufügen" onClose={onClose} widthClass="max-w-2xl">
      <div className="mb-4 flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            disabled={t.key === "drive"}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-2 text-sm font-medium ring-1 ${
              tab === t.key
                ? "bg-src-200 text-src-600 ring-src-600"
                : "bg-white text-chrome-700 ring-chrome-400"
            } ${t.key === "drive" ? "cursor-not-allowed opacity-45" : ""}`}
            title={t.key === "drive" ? "Demnächst verfügbar" : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-3 rounded-md bg-danger-100 px-3 py-2 text-sm text-danger-500">
          {error}
        </p>
      )}

      {tab === "upload" && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const file = e.dataTransfer.files?.[0];
            if (file) void submitFile(file);
          }}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 text-center ${
            dragOver ? "border-src-400 bg-src-100" : "border-chrome-400 bg-chrome-50"
          }`}
        >
          <p className="text-sm font-medium text-chrome-700">
            Dateien hierher ziehen oder hochladen
          </p>
          <p className="mt-1 text-xs text-chrome-600">PDF · Bilder · Dokumente · Audio · Text</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void submitFile(file);
            }}
          />
          <button
            disabled={busy}
            onClick={() => fileInputRef.current?.click()}
            className="mt-4 rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-60"
          >
            {busy ? "Lädt hoch…" : "Datei auswählen"}
          </button>
        </div>
      )}

      {tab === "url" && (
        <div className="flex flex-col gap-3">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            className="rounded-lg border border-chrome-300 px-3 py-2.5 text-sm"
          />
          <button
            disabled={busy || !url.trim()}
            onClick={() => void submitUrl()}
            className="self-end rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-50"
          >
            {busy ? "Wird hinzugefügt…" : "Hinzufügen"}
          </button>
        </div>
      )}

      {tab === "drive" && (
        <p className="rounded-md bg-chrome-50 px-4 py-6 text-center text-sm text-chrome-600">
          Drive-Anbindung ist demnächst verfügbar.
        </p>
      )}

      {tab === "paste" && (
        <div className="flex flex-col gap-3">
          <input
            value={pasteTitle}
            onChange={(e) => setPasteTitle(e.target.value)}
            placeholder="Titel (optional)"
            className="rounded-lg border border-chrome-300 px-3 py-2.5 text-sm"
          />
          <textarea
            value={pasteContent}
            onChange={(e) => setPasteContent(e.target.value)}
            placeholder="Text einfügen…"
            rows={8}
            className="rounded-lg border border-chrome-300 px-3 py-2.5 text-sm"
          />
          <button
            disabled={busy || !pasteContent.trim()}
            onClick={() => void submitPaste()}
            className="self-end rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-50"
          >
            {busy ? "Wird hinzugefügt…" : "Hinzufügen"}
          </button>
        </div>
      )}
    </Modal>
  );
}
