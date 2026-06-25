"use client";

import { useCallback, useEffect, useState } from "react";

import { getPack, listPacks, savePack } from "@/lib/packs";
import { Pack, PackMode, PackSummary } from "@/lib/types";

// Additive host-side bar: load a saved pack into the current inline editor, or
// save the current draft as a new pack. Filtered to the active mode.
export default function PackBar({
  mode,
  onLoad,
  getItems,
}: {
  mode: PackMode;
  onLoad: (pack: Pack) => void;
  getItems: () => unknown[];
}) {
  const [packs, setPacks] = useState<PackSummary[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    listPacks()
      .then((all) => setPacks(all.filter((p) => p.mode === mode)))
      .catch(() => setPacks([]));
  }, [mode]);

  useEffect(() => refresh(), [refresh]);

  async function load(id: string) {
    if (!id) return;
    try {
      onLoad(await getPack(id));
    } catch {
      /* ignore — server may be down */
    }
  }

  async function saveAs() {
    const name = prompt("Nom du pack ?");
    if (!name?.trim()) return;
    setBusy(true);
    try {
      await savePack({ name: name.trim(), mode, items: getItems() });
      refresh();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  const builtins = packs.filter((p) => p.builtin);
  const mine = packs.filter((p) => !p.builtin);

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-panel2 bg-ink/20 px-3 py-2 font-mono text-xs text-muted">
      <span>Pack :</span>
      <select
        onChange={(e) => load(e.target.value)}
        defaultValue=""
        className="min-h-[36px] rounded bg-ink/60 px-2 py-1 text-cream outline-none"
        aria-label="Charger un pack"
      >
        <option value="">Charger un pack…</option>
        {builtins.length > 0 && (
          <optgroup label="▶ Prêts à jouer">
            {builtins.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.count})
              </option>
            ))}
          </optgroup>
        )}
        {mine.length > 0 && (
          <optgroup label="Mes packs">
            {mine.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.count})
              </option>
            ))}
          </optgroup>
        )}
      </select>
      <button onClick={saveAs} disabled={busy} className="min-h-[36px] hover:text-cream disabled:opacity-40">
        {busy ? "…" : "enregistrer comme pack"}
      </button>
      <a href="/editor" className="ml-auto min-h-[36px] underline hover:text-cream">
        éditeur ↗
      </a>
    </div>
  );
}
