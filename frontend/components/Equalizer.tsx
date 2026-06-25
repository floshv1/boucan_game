// Boucan signature motif: a row of animated bars evoking sound level meters
// ("boucan" = a joyful racket). Used in the wordmark, the blindtest countdown,
// the progress row and buzz feedback. Purely decorative → aria-hidden.
//
// When `animated` is false the bars sit still (e.g. paused playback), which also
// satisfies prefers-reduced-motion via the CSS in globals.css.
export default function Equalizer({
  bars = 5,
  className = "",
  animated = true,
}: {
  bars?: number;
  className?: string;
  animated?: boolean;
}) {
  return (
    <span
      aria-hidden
      className={`inline-flex items-end gap-[3px] ${className}`}
    >
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          className={`eq-bar${animated ? "" : " eq-bar--paused"}`}
          style={{ animationDelay: `${(i % bars) * 0.13}s` }}
        />
      ))}
    </span>
  );
}
