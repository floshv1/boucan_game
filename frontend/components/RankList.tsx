// Ordered standings list for the TV. Two looks: a chunky "podium" (end of game)
// and a tighter "scoreboard" with movement arrows. Replaces three near-identical
// <ol> blocks that were duplicated across the QCM / blindtest / buzzer branches.
export interface RankRow {
  id: string;
  rank: number;
  pseudo: string;
  score: number;
  delta?: number; // scoreboard only: change since last round
}

interface Props {
  rows: RankRow[];
  variant?: "podium" | "scoreboard";
  // Stagger each step rising into place (podium reveal). Honors reduced-motion.
  animate?: boolean;
  className?: string;
}

export default function RankList({ rows, variant = "podium", animate = false, className = "" }: Props) {
  const podium = variant === "podium";
  return (
    <ol className={`mx-auto flex max-w-xl flex-col ${podium ? "gap-3" : "gap-2"} ${className}`}>
      {rows.map((r, i) => (
        <li
          key={r.id}
          className={`flex items-center justify-between border border-panel2 bg-panel ${
            podium ? "rounded-2xl px-6 py-4" : "rounded-xl px-5 py-3"
          } ${animate ? "animate-podium-rise" : ""}`}
          // Rank 1 lands last for a build-up; later rows arrive sooner.
          style={animate ? { animationDelay: `${(rows.length - 1 - i) * 90}ms` } : undefined}
        >
          <span className={`font-display ${podium ? "text-3xl" : "text-2xl"}`}>
            {r.rank}. {r.pseudo}
            {!podium && r.delta !== undefined && (
              <span className={r.delta > 0 ? "text-volt" : r.delta < 0 ? "text-buzz" : "text-muted"}>
                {" "}
                {r.delta > 0 ? "▲" : r.delta < 0 ? "▼" : "·"}
              </span>
            )}
          </span>
          <span className={`font-display tabular-nums ${podium ? "text-3xl text-volt" : "text-2xl"}`}>
            {r.score}
          </span>
        </li>
      ))}
    </ol>
  );
}
