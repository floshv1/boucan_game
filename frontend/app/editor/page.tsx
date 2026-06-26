"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useState } from "react";

import { backendHttpUrl } from "@/lib/backend";
import { deletePack, importPack, listPacks } from "@/lib/packs";
import { PackMode, PackSummary } from "@/lib/types";

const MODE_LABEL: Record<PackMode, string> = { buzzer: "Buzzer", qcm: "QCM", blindtest: "Blindtest" };
const MODE_BADGE: Record<PackMode, string> = {
  buzzer: "bg-buzz/20 text-buzz",
  qcm: "bg-quiz-b/20 text-quiz-b",
  blindtest: "bg-volt/20 text-volt",
};

export default function EditorLibrary() {
  const router = useRouter();
  const [packs, setPacks] = useState<PackSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    listPacks()
      .then(setPacks)
      .catch(() => setError("Impossible de charger les packs (serveur ?)."));
  }, []);

  useEffect(() => reload(), [reload]);

  async function onImport(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      const created = await importPack(data);
      router.push(`/editor/${created.id}`);
    } catch (x) {
      setError(x instanceof Error ? x.message : "Import invalide.");
    } finally {
      e.target.value = "";
    }
  }

  async function onDelete(id: string, name: string) {
    if (!confirm(`Supprimer le pack « ${name} » ?`)) return;
    await deletePack(id);
    reload();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-muted">Éditeur de packs</p>
          <h1 className="mt-2 font-display text-5xl">Bibliothèque</h1>
        </div>
        <Link href="/host" className="font-mono text-sm text-muted underline hover:text-cream">
          ← Console hôte
        </Link>
      </header>

      {/* Create + import */}
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <span className="font-mono text-xs uppercase tracking-widest text-muted">Nouveau pack :</span>
        {(["buzzer", "qcm", "blindtest"] as PackMode[]).map((m) => (
          <Link
            key={m}
            href={`/editor/new?mode=${m}`}
            className="rounded-xl border border-panel2 px-4 py-2 font-display text-lg hover:border-muted"
          >
            {MODE_LABEL[m]}
          </Link>
        ))}
        <label className="cursor-pointer rounded-xl border border-dashed border-panel2 px-4 py-2 font-mono text-sm text-muted hover:border-muted hover:text-cream">
          Importer JSON
          <input type="file" accept="application/json,.json" onChange={onImport} className="hidden" />
        </label>
      </div>

      {error && <p className="mt-4 rounded-xl border border-buzz/40 bg-buzz/10 px-4 py-3 text-buzz">{error}</p>}

      {/* List */}
      <div className="mt-8 flex flex-col gap-3">
        {packs === null ? (
          <p className="font-mono text-sm text-muted">Chargement…</p>
        ) : packs.length === 0 ? (
          <p className="font-mono text-sm text-muted">Aucun pack. Crée-en un ci-dessus.</p>
        ) : (
          packs.map((p) => (
            <div
              key={p.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-panel2 bg-panel/60 px-4 py-4 sm:px-5"
            >
              <span className={`rounded-full px-3 py-1 font-mono text-xs ${MODE_BADGE[p.mode]}`}>
                {MODE_LABEL[p.mode]}
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 truncate font-display text-xl">
                  {p.name}
                  {p.builtin && (
                    <span className="rounded-full bg-volt/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-volt">
                      intégré
                    </span>
                  )}
                </p>
                <p className="font-mono text-xs text-muted">
                  {p.count} élément{p.count > 1 ? "s" : ""}
                  {p.tags.length > 0 && <span> · {p.tags.join(", ")}</span>}
                </p>
              </div>
              {p.builtin ? (
                <span className="font-mono text-xs text-muted">prêt à jouer · depuis la console</span>
              ) : (
                <div className="flex items-center gap-4">
                  <Link href={`/editor/${p.id}`} className="font-mono text-sm text-cream underline hover:text-volt">
                    éditer
                  </Link>
                  <a
                    href={backendHttpUrl(`/api/packs/${p.id}/export`)}
                    className="font-mono text-sm text-muted underline hover:text-cream"
                  >
                    exporter
                  </a>
                  <button
                    onClick={() => onDelete(p.id, p.name)}
                    className="font-mono text-sm text-muted hover:text-buzz"
                  >
                    supprimer
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </main>
  );
}
