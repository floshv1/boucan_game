"use client";

import { ReactNode, useEffect } from "react";

// Lightweight reusable popup. Closes on overlay click or Escape. Renders nothing
// when `open` is false. No portal — the fixed overlay covers the viewport, which
// is enough for the app's single-page flows.
export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-panel2 bg-panel p-6 shadow-[0_12px_40px_-8px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          {title && <h2 className="font-display text-2xl">{title}</h2>}
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="ml-auto min-h-[32px] rounded-lg px-2 font-mono text-sm text-muted hover:text-cream"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
