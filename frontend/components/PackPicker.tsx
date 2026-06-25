"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getPack, listPacks } from "@/lib/packs";
import { PackMode, PackSummary } from "@/lib/types";

// Multi-pack selector for the host. Pick one or several packs (themes) of the
// active mode; their questions are merged (and shuffled at start by the host).
// Replaces the old inline question editors — questions are authored only in the
// pack editor now.
export default function PackPicker({
  mode,
  onItemsChange,
}: {
  mode: PackMode;
  onItemsChange: (items: unknown[]) => void;
}) {
  const [packs, setPacks] = useState<PackSummary[] | null>(null); // null = still loading
  const [selected, setSelected] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Cache pack items so re-emitting the merged list never re-fetches.
  const itemsRef = useRef<Record<string, unknown[]>>({});

  const refresh = useCallback(() => {
    listPacks()
      .then((all) => setPacks(all.filter((p) => p.mode === mode)))
      .catch(() => setLoadError("Impossible de charger les packs (serveur ?)."));
  }, [mode]);

  useEffect(() => refresh(), [refresh]);

  // Reset the selection whenever the mode changes (packs are mode-specific).
  useEffect(() => {
    setSelected([]);
    itemsRef.current = {};
    onItemsChange([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  function emit(order: string[]) {
    const combined: unknown[] = [];
    for (const id of order) combined.push(...(itemsRef.current[id] ?? []));
    onItemsChange(combined);
  }

  async function toggle(id: string) {
    if (selected.includes(id)) {
      const next = selected.filter((x) => x !== id);
      setSelected(next);
      emit(next);
      return;
    }
    if (!itemsRef.current[id]) {
      try {
        const pack = await getPack(id);
        itemsRef.current[id] = pack.items;
      } catch {
        itemsRef.current[id] = [];
      }
    }
    const next = [...selected, id];
    setSelected(next);
    emit(next);
  }

  function clearAll() {
    setSelected([]);
    onItemsChange([]);
  }

  const builtins = (packs ?? []).filter((p) => p.builtin);
  const mine = (packs ?? []).filter((p) => !p.builtin);
  const selectedCount = selected.reduce(
    (n, id) => n + ((packs ?? []).find((p) => p.id === id)?.count ?? 0),
    0,
  );

  function renderRow(p: PackSummary) {
    const on = selected.includes(p.id);
    return (
      <button
        key={p.id}
        onClick={() => toggle(p.id)}
        aria-pressed={on}
        className={`flex min-h-[44px] items-center gap-3 rounded-xl border px-3 py-2 text-left transition ${
          on ? "border-volt bg-volt/10" : "border-panel2 hover:border-muted"
        }`}
      >
        <span
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${
            on ? "border-volt bg-volt text-ink" : "border-muted text-transparent"
          }`}
        >
          ✓
        </span>
        <span className="min-w-0 flex-1 truncate text-sm">{p.name}</span>
        <span className="font-mono text-xs text-muted">{p.count}</span>
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs text-muted">
        <span>
          {selected.length > 0
            ? `${selected.length} pack${selected.length > 1 ? "s" : ""} · ${selectedCount} question${selectedCount > 1 ? "s" : ""}`
            : "Choisis un ou plusieurs packs"}
        </span>
        <span className="flex items-center gap-3">
          {selected.length > 0 && (
            <button onClick={clearAll} className="hover:text-buzz">
              Tout désélectionner
            </button>
          )}
          <a href="/editor" className="underline hover:text-cream">
            éditeur ↗
          </a>
        </span>
      </div>

      {loadError && <p className="font-mono text-xs text-buzz">{loadError}</p>}

      {packs === null && !loadError ? (
        <p className="rounded-xl border border-dashed border-panel2 px-4 py-3 font-mono text-sm text-muted">
          Chargement des packs…
        </p>
      ) : packs !== null && packs.length === 0 && !loadError ? (
        <p className="rounded-xl border border-dashed border-panel2 px-4 py-3 font-mono text-sm text-muted">
          Aucun pack pour ce mode. Crée-en un dans l&apos;éditeur ↗
        </p>
      ) : (
        <>
          {builtins.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Prêts à jouer</span>
              {builtins.map(renderRow)}
            </div>
          )}
          {mine.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Mes packs</span>
              {mine.map(renderRow)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
