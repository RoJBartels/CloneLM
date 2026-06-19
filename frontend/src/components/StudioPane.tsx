import type { StudioKind } from "../api/types";

const TILES: { kind: StudioKind | "audio"; label: string; cls: string }[] = [
  { kind: "summary", label: "Zusammenfassung", cls: "bg-studio-200 text-studio-600" },
  { kind: "faq", label: "FAQ", cls: "bg-[#c3fae8] text-[#0c8599]" },
  { kind: "study_guide", label: "Study Guide", cls: "bg-[#ffd8a8] text-[#e8590c]" },
  { kind: "briefing", label: "Briefing", cls: "bg-ok-100 text-ok-600" },
  { kind: "timeline", label: "Timeline", cls: "bg-src-200 text-src-600" },
  { kind: "audio", label: "Audio (Stretch)", cls: "bg-[#eebefa] text-[#ae3ec9]" },
];

/** Right pane (Track E/D). Phase 0b: tiles disabled until a source is ready. */
export default function StudioPane({ enabled }: { enabled: boolean }) {
  return (
    <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-studio-400 bg-studio-100 p-3">
      <h2 className="mb-2 text-lg font-semibold text-studio-600">Studio</h2>

      <div className="grid grid-cols-2 gap-2">
        {TILES.map((t) => (
          <button
            key={t.kind}
            disabled={!enabled}
            className={`rounded-md px-2 py-4 text-sm font-medium ring-1 ring-black/10 ${t.cls} ${
              enabled ? "" : "cursor-not-allowed opacity-45"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4 flex-1 rounded-md bg-white/70 p-3 text-xs text-chrome-600">
        {enabled
          ? "Generierte Artefakte (als Notiz speicherbar)"
          : "Hier wird die Ausgabe von Studio gespeichert. Nachdem Sie Quellen hinzugefügt haben, erstellen Sie Audio-Übersichten, Arbeitshilfen u. v. m."}
      </div>

      <button className="mt-3 rounded-md bg-white px-3 py-2 text-sm text-chrome-900 ring-1 ring-chrome-700">
        + Notiz hinzufügen
      </button>
    </aside>
  );
}
