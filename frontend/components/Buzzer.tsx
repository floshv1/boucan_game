"use client";

interface Props {
  label: string;
  sublabel?: string;
  disabled?: boolean;
  locked?: boolean;
  onBuzz?: () => void;
}

export default function Buzzer({ label, sublabel, disabled, locked, onBuzz }: Props) {
  return (
    <div className="relative flex flex-col items-center">
      {locked && !disabled && (
        <span className="shockwave pointer-events-none absolute top-1/2 h-[340px] w-[340px] max-w-[76vw] -translate-y-1/2 rounded-full border-4 border-buzz/40" />
      )}
      <button
        type="button"
        className={`buzzer ${locked ? "buzzer--locked" : ""} flex items-center justify-center text-center`}
        disabled={disabled}
        onClick={onBuzz}
        aria-label={label}
      >
        <span className="text-5xl sm:text-6xl">{label}</span>
      </button>
      {sublabel && <p className="mt-10 text-center text-lg text-cream/80">{sublabel}</p>}
    </div>
  );
}
