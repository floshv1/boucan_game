"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import BlindtestEditor from "@/components/BlindtestEditor";
import BuzzerEditor, { EMPTY_BUZZER_ROW } from "@/components/BuzzerEditor";
import QcmEditor from "@/components/QcmEditor";
import { getPack, savePack, updatePack } from "@/lib/packs";
import { BlindtestTrackDraft, BuzzerRowDraft, PackMode, QcmRoundDraft } from "@/lib/types";

const EMPTY_QCM_ROW: QcmRoundDraft = {
  question: "",
  choices: ["", "", "", ""],
  correct: 0,
  time_limit: 20,
  points: 1000,
  image: null,
};

const MODE_LABEL: Record<PackMode, string> = { buzzer: "Buzzer", qcm: "QCM", blindtest: "Blindtest" };

function EditorInner() {
  const router = useRouter();
  const id = String(useParams().id ?? "");
  const isNew = id === "new";
  const sp = useSearchParams();

  const [mode, setMode] = useState<PackMode>(((sp.get("mode") as PackMode) || "qcm") as PackMode);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagsStr, setTagsStr] = useState("");
  const [buzzerRows, setBuzzerRows] = useState<BuzzerRowDraft[]>([{ ...EMPTY_BUZZER_ROW }]);
  const [qcmRows, setQcmRows] = useState<QcmRoundDraft[]>([{ ...EMPTY_QCM_ROW }]);
  const [btTracks, setBtTracks] = useState<BlindtestTrackDraft[]>([]);
  const [loaded, setLoaded] = useState(isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNew) return;
    getPack(id)
      .then((pack) => {
        setMode(pack.mode);
        setName(pack.name);
        setDescription(pack.description ?? "");
        setTagsStr((pack.tags ?? []).join(", "));
        if (pack.mode === "buzzer") {
          const items = pack.items as BuzzerRowDraft[];
          setBuzzerRows(items.length ? items : [{ ...EMPTY_BUZZER_ROW }]);
        } else if (pack.mode === "qcm") {
          const items = pack.items as QcmRoundDraft[];
          setQcmRows(items.length ? items : [{ ...EMPTY_QCM_ROW }]);
        } else {
          setBtTracks(pack.items as BlindtestTrackDraft[]);
        }
        setLoaded(true);
      })
      .catch(() => setError("Pack introuvable."));
  }, [id, isNew]);

  function currentItems(): unknown[] {
    if (mode === "buzzer") return buzzerRows;
    if (mode === "qcm") return qcmRows;
    return btTracks;
  }

  const itemCount = mode === "buzzer" ? buzzerRows.length : mode === "qcm" ? qcmRows.length : btTracks.length;

  function clearAll() {
    if (!confirm("Tout supprimer ? Cette action vide le pack (pense à enregistrer ensuite).")) return;
    if (mode === "buzzer") setBuzzerRows([]);
    else if (mode === "qcm") setQcmRows([]);
    else setBtTracks([]);
  }

  async function save() {
    if (!name.trim()) {
      setError("Donne un nom au pack.");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      name: name.trim(),
      description,
      tags: tagsStr
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      mode,
      items: currentItems(),
    };
    try {
      if (isNew) {
        const created = await savePack(payload);
        router.replace(`/editor/${created.id}`);
      } else {
        await updatePack(id, payload);
        setError(null);
      }
    } catch (x) {
      setError(x instanceof Error ? x.message : "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return <main className="p-10 font-mono text-muted">Chargement…</main>;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-5 px-6 py-10">
      <header className="flex items-center justify-between">
        <Link href="/editor" className="font-mono text-sm text-muted underline hover:text-cream">
          ← Bibliothèque
        </Link>
        <span className="rounded-full bg-panel2 px-3 py-1 font-mono text-xs text-muted">{MODE_LABEL[mode]}</span>
      </header>

      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nom du pack"
        className="w-full rounded-xl border border-panel2 bg-ink/60 px-4 py-3 font-display text-2xl outline-none placeholder:text-muted focus:border-muted"
      />
      <div className="flex flex-wrap gap-3">
        <input
          value={tagsStr}
          onChange={(e) => setTagsStr(e.target.value)}
          placeholder="tags, séparés, par, virgules"
          className="flex-1 rounded-lg border border-panel2 bg-ink/60 px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-muted"
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optionnelle)"
          className="flex-1 rounded-lg border border-panel2 bg-ink/60 px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-muted"
        />
      </div>

      {mode === "buzzer" && (
        <>
          <BuzzerEditor rows={buzzerRows} setRows={setBuzzerRows} />
          <button
            onClick={() => setBuzzerRows((rs) => [...rs, { ...EMPTY_BUZZER_ROW }])}
            className="rounded-xl border border-dashed border-panel2 px-4 py-3 font-mono text-sm text-muted hover:border-muted hover:text-cream"
          >
            + Ajouter une question
          </button>
        </>
      )}
      {mode === "qcm" && (
        <>
          <QcmEditor rows={qcmRows} setRows={setQcmRows} />
          <button
            onClick={() => setQcmRows((rs) => [...rs, { ...EMPTY_QCM_ROW }])}
            className="rounded-xl border border-dashed border-panel2 px-4 py-3 font-mono text-sm text-muted hover:border-muted hover:text-cream"
          >
            + Ajouter une question
          </button>
        </>
      )}
      {mode === "blindtest" && <BlindtestEditor tracks={btTracks} setTracks={setBtTracks} />}

      {itemCount > 0 && (
        <button
          onClick={clearAll}
          className="self-start font-mono text-sm text-muted underline hover:text-buzz"
        >
          Tout supprimer ({itemCount})
        </button>
      )}

      {error && <p className="rounded-xl border border-buzz/40 bg-buzz/10 px-4 py-3 text-buzz">{error}</p>}

      <button
        onClick={save}
        disabled={saving}
        className="rounded-2xl bg-volt px-6 py-4 font-display text-2xl text-ink shadow-[0_8px_0_0_#b5b200] transition active:translate-y-1 active:shadow-[0_3px_0_0_#b5b200] disabled:opacity-40"
      >
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
    </main>
  );
}

export default function EditorPage() {
  return (
    <Suspense fallback={<main className="p-10 font-mono text-muted">…</main>}>
      <EditorInner />
    </Suspense>
  );
}
