// Read-only "★ ×2" badge shown to everyone (host / TV / player) when the current
// question or song is a bonus, so players know it's worth double.
export default function BonusChip({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-volt/20 px-2.5 py-0.5 font-mono text-xs font-bold uppercase tracking-wide text-volt ${className}`}
    >
      ★ ×2
    </span>
  );
}
