import type { Source } from "../api/types";

/** Left pane (Track A data). Phase 0b shows the empty state from the design. */
export default function SourcesPane({ sources }: { sources: Source[] }) {
  return (
    <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-src-400 bg-src-100 p-3">
      <h2 className="mb-2 text-lg font-semibold text-src-600">Quellen</h2>

      <button className="mb-2 rounded-md bg-src-200 px-3 py-2 text-sm font-medium text-src-600 ring-1 ring-src-600">
        + Quellen hinzufügen
      </button>
      <button className="mb-4 rounded-md bg-white px-3 py-2 text-sm text-chrome-700 ring-1 ring-chrome-400">
        Web-Recherche
      </button>

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
        <ul className="space-y-2 overflow-y-auto">
          {sources.map((s) => (
            <li
              key={s.id}
              className="flex items-center gap-2 rounded-md bg-white px-2 py-2 ring-1 ring-chrome-400"
            >
              <span className="rounded bg-danger-100 px-1.5 py-0.5 text-xs font-semibold text-danger-500">
                {s.type.toUpperCase()}
              </span>
              <span className="flex-1 truncate text-sm">{s.title}</span>
              {s.status === "ready" && (
                <span className="rounded bg-ok-100 px-1.5 py-0.5 text-xs text-ok-600">
                  bereit
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
