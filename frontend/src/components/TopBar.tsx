import { useEffect, useState } from "react";

import { api } from "../api/client";

type HealthState = "checking" | "online" | "offline";

/** App top bar: logo + notebook title + backend status + actions. */
export default function TopBar({ notebookTitle }: { notebookTitle: string }) {
  const [health, setHealth] = useState<HealthState>("checking");

  useEffect(() => {
    let alive = true;
    api
      .getHealth()
      .then(() => alive && setHealth("online"))
      .catch(() => alive && setHealth("offline"));
    return () => {
      alive = false;
    };
  }, []);

  const dot =
    health === "online"
      ? "bg-ok-600"
      : health === "offline"
        ? "bg-danger-500"
        : "bg-chrome-400";
  const label =
    health === "online" ? "Verbunden" : health === "offline" ? "Offline" : "…";

  return (
    <header className="flex h-13 items-center gap-3 border-b border-chrome-400 bg-src-100 px-4 py-2">
      <span className="h-7 w-7 rounded-full bg-src-400 ring-2 ring-src-600" />
      <span className="text-xl font-semibold text-src-600">CloneLM</span>
      <span className="text-sm text-chrome-700">· {notebookTitle}</span>

      <span className="ml-3 flex items-center gap-1.5 text-xs text-chrome-600">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {label}
      </span>

      <div className="ml-auto flex items-center gap-2">
        <button className="rounded-md bg-src-200 px-3 py-1.5 text-sm text-src-600 ring-1 ring-src-600">
          + Neues Notebook
        </button>
        <button className="rounded-md bg-white px-3 py-1.5 text-sm text-chrome-700 ring-1 ring-chrome-400">
          Teilen
        </button>
        <button className="rounded-md bg-white px-3 py-1.5 text-sm text-chrome-700 ring-1 ring-chrome-400">
          Einstellungen
        </button>
      </div>
    </header>
  );
}
