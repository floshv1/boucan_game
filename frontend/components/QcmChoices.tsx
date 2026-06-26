"use client";

import { memo } from "react";

// One stable colour + shape per answer slot. Exported so the TV renders the same
// answer with the same colour/icon — a player sees their tile match the big screen.
// ANSWER_BG is the bare background (e.g. for chart bars); ANSWER_TILE adds the
// readable text colour for filled tiles.
export const ANSWER_BG = ["bg-quiz-a", "bg-quiz-b", "bg-quiz-c", "bg-quiz-d"];
export const ANSWER_TILE = ["bg-quiz-a", "bg-quiz-b text-ink", "bg-quiz-c text-ink", "bg-quiz-d text-ink"];
export const ANSWER_SHAPE = ["▲", "◆", "●", "■"];
const COLORS = ANSWER_TILE;
const SHAPES = ANSWER_SHAPE;

interface Props {
  choices: string[];
  disabled: boolean;
  myChoice: number | null;
  correct: number | null; // set at reveal
  onPick: (i: number) => void;
}

function QcmChoices({ choices, disabled, myChoice, correct, onPick }: Props) {
  return (
    <div className="grid w-full max-w-md grid-cols-1 gap-3 sm:grid-cols-2">
      {choices.map((c, i) => {
        const picked = myChoice === i;
        const revealed = correct !== null;
        let state = "";
        if (revealed) state = i === correct ? "ring-4 ring-volt" : picked ? "opacity-40 ring-4 ring-buzzdeep" : "opacity-40";
        else if (picked) state = "ring-4 ring-cream";
        else if (disabled) state = "opacity-60";
        return (
          <button
            key={i}
            disabled={disabled}
            onClick={() => onPick(i)}
            className={`flex items-center gap-3 rounded-2xl px-5 py-6 text-left font-display text-2xl text-white shadow-lg transition active:scale-95 ${COLORS[i]} ${state}`}
          >
            <span className="text-3xl">{SHAPES[i]}</span>
            <span className="flex-1">{c}</span>
          </button>
        );
      })}
    </div>
  );
}

export default memo(QcmChoices);
