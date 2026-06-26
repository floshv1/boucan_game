"use client";

import { ReactNode } from "react";

// Presentational collapsible card used by the editors so long question/track lists
// can be folded — no more scrolling to the bottom to reach the "+ Ajouter" button.
// Open/collapse state is owned by the parent (keyed by index) so "collapse all" works.
export default function Collapsible({
  title,
  subtitle,
  open,
  onToggle,
  onRemove,
  children,
}: {
  title: string;
  subtitle?: string;
  open: boolean;
  onToggle: () => void;
  onRemove?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-panel2 bg-ink/40">
      <div className="flex items-center gap-2 p-3">
        <button onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span className={`font-mono text-muted transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
          <span className="shrink-0 font-mono text-xs uppercase tracking-widest text-muted">{title}</span>
          {subtitle && <span className="truncate text-sm text-cream/80">{subtitle}</span>}
        </button>
        {onRemove && (
          <button onClick={onRemove} className="shrink-0 font-mono text-xs text-muted hover:text-buzz">
            retirer ✕
          </button>
        )}
      </div>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

// Small helper hook-free utilities for parents managing a collapsed Set<number>.
export function toggleInSet(set: Set<number>, i: number): Set<number> {
  const next = new Set(set);
  if (next.has(i)) next.delete(i);
  else next.add(i);
  return next;
}
