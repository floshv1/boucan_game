import { ElementType, HTMLAttributes } from "react";

// The standard surface shell: rounded panel with a hairline border over the
// translucent panel tint. Was copy-pasted ~6× across the TV screen.
interface Props extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
}

export default function Card({ as: Tag = "div", className = "", ...rest }: Props) {
  return <Tag className={`rounded-3xl border border-panel2 bg-panel/60 ${className}`} {...rest} />;
}
