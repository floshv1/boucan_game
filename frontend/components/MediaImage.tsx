"use client";

import Image from "next/image";

// Two thin wrappers over next/image so every cover/prompt image gets lazy-loading
// + sizing for free and the call sites stay terse.

// Square cover / thumbnail (Spotify art, uploaded preview) at a fixed pixel size.
// `size` should match the caller's h-*/w-* classes.
export function CoverImage({
  src,
  size,
  className = "",
}: {
  src: string;
  size: number;
  className?: string;
}) {
  return <Image src={src} alt="" width={size} height={size} className={`object-cover ${className}`} />;
}

// Responsive prompt/question image of unknown aspect ratio: renders at its natural
// size, capped by the caller's `max-h-*`, centred. The width/height are ratio
// placeholders; `style` auto/auto lets CSS drive the real dimensions (and silences
// next/image's aspect-ratio warning).
export function PromptImage({ src, className = "" }: { src: string; className?: string }) {
  return (
    <Image
      src={src}
      alt=""
      width={1200}
      height={800}
      sizes="(max-width: 768px) 90vw, 700px"
      className={`w-auto object-contain ${className}`}
      style={{ width: "auto", height: "auto" }}
    />
  );
}
