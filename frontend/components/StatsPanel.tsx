"use client";

import { GameStats } from "@/lib/types";

const MODE_LABEL: Record<string, string> = {
  buzzer: "Buzzer",
  qcm: "QCM",
  blindtest: "Blindtest",
};

// Per-game points breakdown for the current session (in-memory, resets on restart).
// A "game" = one pack played from start to the podium; points shown are what each
// player won *during that game* (scores are cumulative across games on the same code).
export default function StatsPanel({ stats, className = "" }: { stats: GameStats; className?: string }) {
  const history = stats?.history ?? [];
  if (history.length === 0) return null;

  // Aggregate total points won across all recorded games, per player.
  const totals = new Map<string, { pseudo: string; points: number }>();
  for (const g of history) {
    for (const r of g.results) {
      const cur = totals.get(r.id) ?? { pseudo: r.pseudo, points: 0 };
      cur.points += r.points;
      cur.pseudo = r.pseudo;
      totals.set(r.id, cur);
    }
  }
  const aggregate = [...totals.values()].sort((a, b) => b.points - a.points);

  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">
        Stats — points par partie ({history.length} partie{history.length > 1 ? "s" : ""})
      </p>

      {history
        .slice()
        .reverse()
        .map((g) => {
          const ranked = g.results.slice().sort((a, b) => b.points - a.points);
          return (
            <div key={g.game} className="rounded-xl border border-panel2 bg-ink/30 p-3">
              <p className="mb-2 font-mono text-xs text-muted">
                Partie {g.game} · {MODE_LABEL[g.mode] ?? g.mode}
              </p>
              <ul className="flex flex-col gap-1">
                {ranked.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate">{r.pseudo}</span>
                    <span className="font-display tabular-nums text-volt">+{r.points}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}

      {history.length > 1 && (
        <div className="rounded-xl border border-volt/30 bg-volt/5 p-3">
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-muted">Cumul sur la session</p>
          <ul className="flex flex-col gap-1">
            {aggregate.map((a, i) => (
              <li key={i} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate">{a.pseudo}</span>
                <span className="font-display tabular-nums text-volt">+{a.points}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
