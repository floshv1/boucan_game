"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

// One button system for the whole app: consistent look, tokenised arcade shadows,
// and ≥44px touch targets. Replaces the ad-hoc inline button classes that had
// drifted (e.g. mismatched shadow hexes after the rename).
type Variant = "primary" | "accent" | "danger" | "ghost";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl font-display transition " +
  "active:translate-y-0.5 disabled:opacity-30 disabled:shadow-none disabled:active:translate-y-0 " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cream";

// 3D arcade shadow per variant (tokenised so colours stay consistent everywhere).
const VARIANTS: Record<Variant, string> = {
  // "Go" / advance action.
  primary:
    "bg-volt text-ink shadow-[0_6px_0_0_#9bbf00] active:shadow-[0_2px_0_0_#9bbf00] hover:brightness-105",
  // Big call-to-action (Créer / Rejoindre / Démarrer).
  accent:
    "bg-buzz text-white shadow-[0_6px_0_0_#8e0c2c] active:shadow-[0_2px_0_0_#8e0c2c] hover:brightness-105",
  // Destructive / negative judgement.
  danger:
    "bg-buzzdeep text-white shadow-[0_6px_0_0_#5a0518] active:shadow-[0_2px_0_0_#5a0518] hover:brightness-105",
  // Quiet secondary.
  ghost: "border border-panel2 text-cream hover:border-muted",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-[40px] px-3 py-2 text-base",
  md: "min-h-[44px] px-4 py-2.5 text-lg",
  lg: "min-h-[52px] px-5 py-3.5 text-xl sm:text-2xl",
};

const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "ghost", size = "md", className = "", type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    />
  );
});

export default Button;
