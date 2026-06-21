import type { Citation } from "../api/types";
import Modal from "./Modal";

/**
 * Beleg-Ansicht (evidence view): shows the source title, page/section, and the
 * exact supporting passage highlighted. This is the faithfulness payoff —
 * every citation must be traceable to a literal span in the source.
 *
 * We highlight using the citation's snippet (the exact passage text the
 * backend extracted via start_char/end_char) rather than re-deriving it from
 * raw source text, since the frontend doesn't have the full source body.
 */
export default function BelegModal({
  citation,
  onClose,
}: {
  citation: Citation;
  onClose: () => void;
}) {
  return (
    <Modal title="Beleg-Ansicht" onClose={onClose} widthClass="max-w-lg">
      <p className="mb-1 text-sm text-chrome-600">
        {citation.source_title}
        {citation.page != null ? ` · Seite ${citation.page}` : ""}
      </p>
      <p className="mb-4 text-xs text-chrome-500">
        Zeichen {citation.start_char}–{citation.end_char}
      </p>

      <div className="rounded-lg border border-chrome-300 bg-white p-4">
        <div className="rounded-md bg-note-100 px-3 py-2 text-sm text-chrome-900 ring-1 ring-note-500">
          „{citation.snippet}“ <span className="font-semibold">[{citation.marker}]</span>
        </div>
      </div>

      <p className="mt-4 text-xs text-chrome-500">
        Diese Passage stammt direkt aus der Quelle und stützt die zitierte Aussage im Chat.
      </p>
    </Modal>
  );
}
