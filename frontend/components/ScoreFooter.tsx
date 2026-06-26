// Player-view sticky score bar (rank + points). Was repeated 4× in the player
// screen across game modes.
interface Props {
  rank: number | string;
  score: number;
}

export default function ScoreFooter({ rank, score }: Props) {
  return (
    <footer className="flex items-center justify-between rounded-2xl border border-panel2 bg-panel/60 px-5 py-4">
      <span className="font-mono text-xs uppercase tracking-widest text-muted">Ton score</span>
      <span className="flex items-baseline gap-3">
        <span className="font-mono text-sm text-muted">#{rank}</span>
        <span className="font-display text-4xl tabular-nums">{score}</span>
      </span>
    </footer>
  );
}
