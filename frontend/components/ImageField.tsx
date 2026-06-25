"use client";

import { ChangeEvent, useState } from "react";

import { uploadImage } from "@/lib/packs";

// Compact image upload control for a question row. Uploads to /api/media and
// reports back the /media/<file> URL (or null when removed).
export default function ImageField({
  image,
  onChange,
}: {
  image?: string | null;
  onChange: (url: string | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    setErr(null);
    try {
      onChange(await uploadImage(f));
    } catch (x) {
      setErr(x instanceof Error ? x.message : "échec");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <span className="flex items-center gap-2 font-mono text-xs text-muted">
      {image ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt="" className="h-9 w-9 rounded object-cover" />
          <button type="button" onClick={() => onChange(null)} className="hover:text-buzz">
            retirer l&apos;image ✕
          </button>
        </>
      ) : (
        <label className="cursor-pointer hover:text-cream">
          {busy ? "…" : "+ image"}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={onFile}
            className="hidden"
          />
        </label>
      )}
      {err && <span className="text-buzz">{err}</span>}
    </span>
  );
}
