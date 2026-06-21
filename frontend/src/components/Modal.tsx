import type { ReactNode } from "react";

/** Minimal modal overlay shared by Add-sources and Beleg-Ansicht. */
export default function Modal({
  title,
  onClose,
  children,
  widthClass = "max-w-xl",
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  widthClass?: string;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className={`w-full ${widthClass} max-h-[85vh] overflow-y-auto rounded-xl border-2 border-studio-400 bg-white p-6 shadow-xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-chrome-900">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Schließen"
            className="text-lg text-chrome-500 hover:text-chrome-900"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
