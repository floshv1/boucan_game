"use client";

import { useState } from "react";

import BonusToggle from "@/components/BonusToggle";
import Collapsible, { toggleInSet } from "@/components/Collapsible";
import ImageField from "@/components/ImageField";
import { ANSWER_BG } from "@/components/QcmChoices";
import { QcmRoundDraft } from "@/lib/types";

// Same per-slot colours as the live game (player + TV), so the editor preview
// matches what players will see.
const COLORS = ANSWER_BG;

interface Props {
  rows: QcmRoundDraft[];
  setRows: (rows: QcmRoundDraft[]) => void;
}

export default function QcmEditor({ rows, setRows }: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const patch = (i: number, p: Partial<QcmRoundDraft>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const patchChoice = (i: number, c: number, val: string) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, choices: r.choices.map((x, k) => (k === c ? val : x)) } : r)));
  const remove = (i: number) => setRows(rows.length > 1 ? rows.filter((_, j) => j !== i) : rows);

  return (
    <div className="flex flex-col gap-3">
      {rows.length > 1 && (
        <div className="flex justify-end gap-3 font-mono text-xs text-muted">
          <button onClick={() => setCollapsed(new Set(rows.map((_, i) => i)))} className="hover:text-cream">
            Tout replier
          </button>
          <button onClick={() => setCollapsed(new Set())} className="hover:text-cream">
            Tout déplier
          </button>
        </div>
      )}
      {rows.map((row, i) => (
        <Collapsible
          key={i}
          title={`Question ${i + 1}`}
          subtitle={row.question || "(sans énoncé)"}
          open={!collapsed.has(i)}
          onToggle={() => setCollapsed((s) => toggleInSet(s, i))}
          onRemove={() => remove(i)}
        >
          <input
            value={row.question}
            onChange={(e) => patch(i, { question: e.target.value })}
            placeholder="Énoncé de la question"
            className="mb-2 w-full rounded-lg border border-panel2 bg-ink/60 px-3 py-2 outline-none placeholder:text-muted focus:border-muted"
          />
          <div className="grid grid-cols-2 gap-2">
            {row.choices.map((choice, c) => (
              <label key={c} className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`correct-${i}`}
                  checked={row.correct === c}
                  onChange={() => patch(i, { correct: c })}
                  aria-label={`Bonne réponse : choix ${c + 1}`}
                />
                <span className={`h-3 w-3 shrink-0 rounded-full ${COLORS[c]}`} />
                <input
                  value={choice}
                  onChange={(e) => patchChoice(i, c, e.target.value)}
                  placeholder={`Choix ${c + 1}`}
                  className="w-full rounded-lg border border-panel2 bg-ink/60 px-2 py-1.5 text-sm outline-none placeholder:text-muted focus:border-muted"
                />
              </label>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-4 font-mono text-xs text-muted">
            <label className="flex items-center gap-2">
              Temps
              <input
                type="number"
                value={row.time_limit}
                onChange={(e) => patch(i, { time_limit: Number.parseInt(e.target.value, 10) || 20 })}
                className="w-16 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
              />
              s
            </label>
            <label className="flex items-center gap-2">
              Points
              <input
                type="number"
                value={row.points}
                onChange={(e) => patch(i, { points: Number.parseInt(e.target.value, 10) || 1000 })}
                className="w-20 rounded-lg border border-panel2 bg-ink/60 px-2 py-1 text-center text-cream outline-none"
              />
            </label>
            <BonusToggle on={!!row.bonus} onChange={(v) => patch(i, { bonus: v })} />
            <ImageField image={row.image} onChange={(url) => patch(i, { image: url })} />
          </div>
        </Collapsible>
      ))}
    </div>
  );
}
