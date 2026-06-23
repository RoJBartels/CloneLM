import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { LLMProviderChoice, LLMSettings, LLMSettingsUpdate } from "../api/types";
import Modal from "./Modal";

/**
 * Einstellungen — manage the LLM provider. Pick Anthropic (Claude) and store
 * the API key, or switch to a local open-source model via Ollama. The key is
 * write-only: the backend reports only whether one is set, never the value.
 */
export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [provider, setProvider] = useState<LLMProviderChoice>("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = (probe = false) =>
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        if (!probe) {
          setProvider(s.llm_provider);
          setOllamaUrl(s.ollama_base_url);
          setOllamaModel(s.ollama_model);
        }
      })
      .catch((e) =>
        setLoadError(e instanceof Error ? e.message : "Einstellungen konnten nicht geladen werden"),
      );

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const body: LLMSettingsUpdate = { llm_provider: provider };
      if (provider === "anthropic" && apiKey.trim()) body.anthropic_api_key = apiKey.trim();
      if (provider === "ollama") {
        body.ollama_base_url = ollamaUrl.trim();
        body.ollama_model = ollamaModel.trim();
      }
      const updated = await api.updateSettings(body);
      setSettings(updated);
      setApiKey("");
      setSaved(true);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  const usingFakeFallback =
    settings?.llm_provider === "anthropic" &&
    settings?.effective_llm_provider === "fake";

  return (
    <Modal title="Einstellungen — KI-Modell" onClose={onClose}>
      {loadError && (
        <p className="mb-3 rounded-md bg-danger-100 px-3 py-2 text-sm text-danger-500">{loadError}</p>
      )}
      {!settings && !loadError && <p className="text-sm text-chrome-600">Lädt…</p>}

      {settings && (
        <div className="space-y-5">
          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-semibold text-chrome-900">LLM-Anbieter</legend>

            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-chrome-400 p-3 hover:bg-chrome-50">
              <input
                type="radio"
                name="provider"
                className="mt-1"
                checked={provider === "anthropic"}
                onChange={() => setProvider("anthropic")}
              />
              <span>
                <span className="block text-sm font-medium text-chrome-900">Anthropic (Claude)</span>
                <span className="block text-xs text-chrome-600">
                  Gehostetes Modell ({settings.llm_model}). Benötigt einen API-Schlüssel.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-chrome-400 p-3 hover:bg-chrome-50">
              <input
                type="radio"
                name="provider"
                className="mt-1"
                checked={provider === "ollama"}
                onChange={() => setProvider("ollama")}
              />
              <span>
                <span className="block text-sm font-medium text-chrome-900">
                  Open Source (Ollama, lokal)
                </span>
                <span className="block text-xs text-chrome-600">
                  Läuft offline auf deinem Rechner. Kein API-Schlüssel nötig.
                </span>
              </span>
            </label>
          </fieldset>

          {provider === "anthropic" ? (
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-chrome-900" htmlFor="api-key">
                Anthropic API-Schlüssel
              </label>
              <input
                id="api-key"
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  settings.anthropic_api_key_set
                    ? "•••••••••• (gespeichert — leer lassen zum Beibehalten)"
                    : "sk-ant-…"
                }
                className="w-full rounded-md border border-chrome-400 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-src-600"
              />
              <p className="text-xs text-chrome-500">
                {settings.anthropic_api_key_set
                  ? "Ein Schlüssel ist gespeichert. Gib einen neuen ein, um ihn zu ersetzen."
                  : "Noch kein Schlüssel gespeichert."}
              </p>
              {usingFakeFallback && (
                <p className="rounded-md bg-studio-100 px-3 py-2 text-xs text-chrome-700">
                  ⚠ Ohne Schlüssel nutzt die App das Demo-LLM (Fake-Antworten). Speichere einen
                  Schlüssel, um echte Claude-Antworten zu erhalten.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-chrome-900" htmlFor="ollama-url">
                  Ollama-Server-URL
                </label>
                <input
                  id="ollama-url"
                  type="text"
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-full rounded-md border border-chrome-400 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-src-600"
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-chrome-900" htmlFor="ollama-model">
                  Modell
                </label>
                <input
                  id="ollama-model"
                  type="text"
                  value={ollamaModel}
                  onChange={(e) => setOllamaModel(e.target.value)}
                  placeholder="llama3.1"
                  className="w-full rounded-md border border-chrome-400 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-src-600"
                />
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span
                  className={`h-2 w-2 rounded-full ${
                    settings.ollama_available ? "bg-ok-600" : "bg-danger-500"
                  }`}
                />
                <span className="text-chrome-700">
                  {settings.ollama_available ? "Ollama erreichbar" : "Ollama nicht erreichbar"}
                </span>
                <button
                  type="button"
                  onClick={() => void load(true)}
                  className="ml-1 rounded px-2 py-0.5 text-src-600 ring-1 ring-chrome-400 hover:bg-chrome-50"
                >
                  Erneut prüfen
                </button>
              </div>
              {!settings.ollama_available && (
                <p className="rounded-md bg-studio-100 px-3 py-2 text-xs text-chrome-700">
                  Kein Ollama-Server gefunden. Starte ihn mit{" "}
                  <code className="rounded bg-white px-1">ollama serve</code> und lade ein Modell, z. B.{" "}
                  <code className="rounded bg-white px-1">ollama pull llama3.1</code>.
                </p>
              )}
            </div>
          )}

          {saveError && (
            <p className="rounded-md bg-danger-100 px-3 py-2 text-sm text-danger-500">{saveError}</p>
          )}
          {saved && !saveError && (
            <p className="rounded-md bg-ok-100 px-3 py-2 text-sm text-ok-600">
              Gespeichert. Aktiver Anbieter: {settings.effective_llm_provider}.
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={onClose}
              className="rounded-md bg-white px-4 py-2 text-sm text-chrome-700 ring-1 ring-chrome-400 hover:bg-chrome-50"
            >
              Schließen
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-60"
            >
              {saving ? "Speichert…" : "Speichern"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
