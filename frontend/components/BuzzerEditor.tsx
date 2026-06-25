"use client";

import BonusToggle from "@/components/BonusToggle";
import ImageField from "@/components/ImageField";
import { BuzzerRowDraft } from "@/lib/types";

interface Props {
  rows: BuzzerRowDraft[];
  setRows: (rows: BuzzerRowDraft[]) => void;
}

export const EMPTY_BUZZER_ROW: BuzzerRowDraft = { question: "", answer: "", points: 1, image: null };

// Buzzer round list editor, shared by the host console and the pack editor.
export default function BuzzerEditor({ rows, setRows }: Props) {
  const patch = (i: number, p: Partial<BuzzerRowDraft>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const remove = (i: number) => setRows(rows.length > 1 ? rows.filter((_, j) => j !== i) : rows);

  return (
    <div className="flex flex-col gap-3">
      {rows.map((row, i) => (
        <div key={i} className="rounded-xl border border-panel2 bg-ink/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-xs uppercase tracking-widest text-muted">Question {i + 1}</span>
            <button onClick={() => remove(i)} className="font-mono text-xs text-muted hover:text-buzz">
              retirer ✕
            </button>
          </div>
          <input
            value={row.question}
            onChange={(e) => patch(i, { question: e.target.value })}
            placeholder="Énoncé (laisser vide pour un buzz pur)"
            className="mb-2 w-full rounded-lg border border-panel2 bg-ink/60 px-3 py-2 outline-none placeholder:text-muted focus:border-muted"
          />
          <div className="flex flex-wrap items-center gap-3">
            <input
              value={row.answer}
              onChange={(e) => patch(i, { answer: e.target.value })}
              placeholder="Réponse (vue de l'hôte seulement)"
              className="flex-1 rounded-lg border border-panel2 bg-ink/60 px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-muted"
            />
            <label className="flex items-center gap-2 font-mono text-xs text-muted">
              Points
              <input
                type="number"
                value={row.points}
                onChange={(e) => patch(i, { points: Number.parseInt(e.target.value, 10) || 1 })}
                className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
              />
            </label>
            <BonusToggle on={!!row.bonus} onChange={(v) => patch(i, { bonus: v })} />
            <ImageField image={row.image} onChange={(url) => patch(i, { image: url })} />
          </div>
        </div>
      ))}
    </div>
  );
}
