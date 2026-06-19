/** Middle pane (Track B data). Phase 0b: empty state + disabled input until at
 * least one source is `bereit`. */
export default function ChatPane({
  title,
  sourceCount,
  hasReadySource,
}: {
  title: string;
  sourceCount: number;
  hasReadySource: boolean;
}) {
  const today = new Date().toLocaleDateString("de-DE");

  return (
    <section className="flex flex-1 flex-col rounded-lg border border-chrome-400 bg-white p-4">
      <h2 className="mb-2 text-lg font-semibold text-chrome-700">Chat</h2>

      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="mb-4 h-10 w-11 rounded-md bg-note-100 ring-1 ring-note-500" />
        <h3 className="text-2xl font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-chrome-600">
          {sourceCount} {sourceCount === 1 ? "Quelle" : "Quellen"} · {today}
        </p>
        {!hasReadySource && (
          <div className="mt-6 rounded-lg border border-dashed border-chrome-300 bg-chrome-50 px-6 py-4 text-sm text-chrome-600">
            Fügen Sie eine Quelle hinzu, um Fragen zu stellen.
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <input
          disabled={!hasReadySource}
          placeholder="Text eingeben…"
          className="flex-1 rounded-lg border border-chrome-300 bg-chrome-50 px-3 py-2.5 text-sm placeholder:text-chrome-400 disabled:cursor-not-allowed disabled:opacity-70"
        />
        <span className="text-xs text-chrome-500">{sourceCount} Quellen</span>
        <button
          disabled={!hasReadySource}
          className="h-9 w-9 rounded-full bg-src-400 text-white disabled:bg-chrome-300"
          aria-label="Senden"
        >
          ↑
        </button>
      </div>
    </section>
  );
}
