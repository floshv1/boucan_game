// Compact ⭐ ×2 toggle reused across the buzzer / QCM / blindtest editors.
// One consistent control keeps the editors minimal and the bonus mechanic obvious.
export default function BonusToggle({
  on,
  onChange,
  className = "",
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      aria-pressed={on}
      title="Bonus : cette question rapporte le double de points"
      className={`flex shrink-0 items-center gap-1 rounded-lg border px-2.5 py-1.5 font-mono text-xs transition ${
        on
          ? "border-volt bg-volt/15 text-volt"
          : "border-panel2 text-muted hover:border-muted hover:text-cream"
      } ${className}`}
    >
      <span aria-hidden>★</span> ×2
    </button>
  );
}
