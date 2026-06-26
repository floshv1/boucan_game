"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

import { buttonClasses, Size, Variant } from "@/components/buttonStyles";

// One button system for the whole app: consistent look, tokenised arcade shadows,
// and ≥44px touch targets. Replaces the ad-hoc inline button classes that had
// drifted (e.g. mismatched shadow hexes after the rename). Styling lives in
// buttonStyles.ts so server components can reuse it via buttonClasses().
export type { Size, Variant } from "@/components/buttonStyles";
export { buttonClasses } from "@/components/buttonStyles";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "ghost", size = "md", className = "", type = "button", ...rest },
  ref,
) {
  return (
    <button ref={ref} type={type} className={buttonClasses(variant, size, className)} {...rest} />
  );
});

export default Button;
