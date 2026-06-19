import type { Source } from "./api/types";
import ChatPane from "./components/ChatPane";
import SourcesPane from "./components/SourcesPane";
import StudioPane from "./components/StudioPane";
import TopBar from "./components/TopBar";

/**
 * Phase 0b shell. Renders the designed three-pane layout in its empty/cold-start
 * state (0 sources → chat input + Studio tiles disabled). Phase 3 (Track C)
 * replaces the static state with live data from the typed API client.
 */
export default function App() {
  const notebookTitle = "Unbenanntes Notebook";
  const sources: Source[] = []; // empty state by default
  const hasReadySource = sources.some((s) => s.status === "ready");

  return (
    <div className="flex h-full flex-col bg-white">
      <TopBar notebookTitle={notebookTitle} />
      <main className="flex flex-1 gap-3 overflow-hidden p-3">
        <SourcesPane sources={sources} />
        <ChatPane
          title={notebookTitle}
          sourceCount={sources.length}
          hasReadySource={hasReadySource}
        />
        <StudioPane enabled={hasReadySource} />
      </main>
    </div>
  );
}
