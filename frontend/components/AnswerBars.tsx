"use client";

import { memo } from "react";

const COLORS = ["bg-buzz", "bg-blue-500", "bg-yellow-400", "bg-volt"];

interface Props {
  choices: string[];
  distribution: number[];
  correct: number;
}

function AnswerBars({ choices, distribution, correct }: Props) {
  const max = Math.max(1, ...distribution);
  return (
    <div className="grid w-full grid-cols-4 items-end gap-4">
      {choices.map((c, i) => (
        <div key={i} className="flex flex-col items-center gap-2">
          <span className="font-display text-2xl tabular-nums">{distribution[i]}</span>
          <div
            className={`w-full rounded-t-xl ${COLORS[i]} ${i === correct ? "" : "opacity-40"}`}
            style={{ height: `${20 + (distribution[i] / max) * 180}px` }}
          />
          <span className={`text-center font-display text-lg ${i === correct ? "text-volt" : "text-cream/70"}`}>
            {c} {i === correct && "✓"}
          </span>
        </div>
      ))}
    </div>
  );
}

export default memo(AnswerBars);
