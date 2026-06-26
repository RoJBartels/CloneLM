import { useState } from "react";

import { api, setAuthToken } from "../api/client";
import type { AuthUser } from "../api/types";

/**
 * Full-screen auth gate for the hosted build. Users register with their own
 * Anthropic + Voyage keys (stored encrypted server-side) or log in. On success
 * the bearer token is persisted and the app is handed the authenticated user.
 */
export default function AuthView({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [voyageKey, setVoyageKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const resp =
        mode === "login"
          ? await api.login({ email: email.trim(), password })
          : await api.register({
              email: email.trim(),
              password,
              anthropic_api_key: anthropicKey.trim(),
              voyage_api_key: voyageKey.trim(),
            });
      setAuthToken(resp.access_token);
      onAuthenticated(resp.user);
    } catch (e) {
      setError(e instanceof Error ? cleanError(e.message) : "Fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    "w-full rounded-md border border-chrome-400 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-src-600";

  return (
    <div className="flex h-full items-center justify-center bg-src-100 p-4">
      <div className="w-full max-w-sm rounded-xl border border-chrome-400 bg-white p-6 shadow-xl">
        <div className="mb-1 flex items-center gap-2">
          <span className="h-7 w-7 rounded-full bg-src-400 ring-2 ring-src-600" />
          <span className="text-xl font-semibold text-src-600">CloneLM</span>
        </div>
        <h1 className="mb-4 text-sm text-chrome-600">
          {mode === "login" ? "Anmelden" : "Konto erstellen"}
        </h1>

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-chrome-900" htmlFor="email">
              E-Mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-chrome-900" htmlFor="password">
              Passwort
            </label>
            <input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls}
            />
          </div>

          {mode === "register" && (
            <>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-chrome-900" htmlFor="reg-anthropic">
                  Anthropic API-Schlüssel
                </label>
                <input
                  id="reg-anthropic"
                  type="password"
                  autoComplete="off"
                  required
                  placeholder="sk-ant-…"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  className={inputCls}
                />
                <p className="text-xs text-chrome-500">
                  Schlüssel erstellen:{" "}
                  <a
                    href="https://console.anthropic.com/settings/keys"
                    target="_blank"
                    rel="noreferrer"
                    className="text-src-600 underline hover:text-src-700"
                  >
                    console.anthropic.com/settings/keys
                  </a>
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-chrome-900" htmlFor="reg-voyage">
                  Voyage API-Schlüssel
                </label>
                <input
                  id="reg-voyage"
                  type="password"
                  autoComplete="off"
                  required
                  placeholder="pa-…"
                  value={voyageKey}
                  onChange={(e) => setVoyageKey(e.target.value)}
                  className={inputCls}
                />
                <p className="text-xs text-chrome-500">
                  Schlüssel erstellen:{" "}
                  <a
                    href="https://dash.voyageai.com"
                    target="_blank"
                    rel="noreferrer"
                    className="text-src-600 underline hover:text-src-700"
                  >
                    dash.voyageai.com
                  </a>
                </p>
              </div>
              <p className="rounded-md bg-studio-100 px-3 py-2 text-xs text-chrome-700">
                Deine Schlüssel werden verschlüsselt gespeichert und nur für deine
                eigenen Anfragen verwendet.
              </p>
            </>
          )}

          {error && (
            <p className="rounded-md bg-danger-100 px-3 py-2 text-sm text-danger-500">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-src-200 px-4 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600 disabled:opacity-60"
          >
            {busy ? "…" : mode === "login" ? "Anmelden" : "Registrieren"}
          </button>
        </form>

        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-center text-xs text-src-600 hover:underline"
        >
          {mode === "login"
            ? "Noch kein Konto? Jetzt registrieren"
            : "Bereits ein Konto? Anmelden"}
        </button>
      </div>
    </div>
  );
}

/** Strip the leading "<status> <statusText>:" from the API error for display. */
function cleanError(message: string): string {
  const idx = message.indexOf(": ");
  const tail = idx >= 0 ? message.slice(idx + 2) : message;
  try {
    const parsed = JSON.parse(tail) as { detail?: string };
    if (parsed.detail) return parsed.detail;
  } catch {
    /* not JSON */
  }
  return tail || message;
}
