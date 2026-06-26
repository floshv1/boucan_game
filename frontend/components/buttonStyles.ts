// Pure styling for the button system — kept out of the "use client" Button so
// server components (e.g. the home page) can borrow the look for a <Link> CTA.
export type Variant = "primary" | "accent" | "danger" | "ghost";
export type Size = "sm" | "md" | "lg";

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl font-display transition " +
  "active:translate-y-0.5 disabled:opacity-30 disabled:shadow-none disabled:active:translate-y-0 " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cream";

// 3D arcade shadow per variant (tokenised so colours stay consistent everywhere).
const VARIANTS: Record<Variant, string> = {
  // "Go" / advance action.
  primary: "bg-volt text-ink shadow-arcade-volt active:shadow-arcade-volt-press hover:brightness-105",
  // Big call-to-action (Créer / Rejoindre / Démarrer).
  accent: "bg-buzz text-white shadow-arcade-buzz active:shadow-arcade-buzz-press hover:brightness-105",
  // Destructive / negative judgement.
  danger: "bg-buzzdeep text-white shadow-arcade-deep active:shadow-arcade-deep-press hover:brightness-105",
  // Quiet secondary.
  ghost: "border border-panel2 text-cream hover:border-muted",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-[40px] px-3 py-2 text-base",
  md: "min-h-[44px] px-4 py-2.5 text-lg",
  lg: "min-h-[52px] px-5 py-3.5 text-xl sm:text-2xl",
};

export function buttonClasses(variant: Variant = "ghost", size: Size = "md", className = "") {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`;
}
