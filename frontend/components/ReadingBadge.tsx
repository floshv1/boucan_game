"use client";

// Shown during the reading window before choices unlock / the buzzer opens, so
// players can read (or listen to) the question first.
export default function ReadingBadge({
  secondsLeft,
  label = "Lecture…",
  className = "",
}: {
  secondsLeft: number;
  label?: string;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center gap-1 ${className}`}>
      <span className="font-mono text-xs uppercase tracking-widest text-muted">{label}</span>
      <span className="font-display text-6xl tabular-nums text-volt">{Math.max(0, secondsLeft)}</span>
    </div>
  );
}
