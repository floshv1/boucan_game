"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import Button from "@/components/Button";
import { sessionExists } from "@/lib/api";

export default function PlayJoin() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [pseudo, setPseudo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const c = new URL(window.location.href).searchParams.get("code");
    if (c) setCode(c.toUpperCase());
    const saved = localStorage.getItem("quiz:lastPseudo");
    if (saved) setPseudo(saved);
  }, []);

  async function join(e: FormEvent) {
    e.preventDefault();
    const c = code.trim().toUpperCase();
    const p = pseudo.trim();
    if (c.length < 6 || !p) {
      setError("Entre le code à 6 lettres et un pseudo.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await sessionExists(c);
      if (!res.exists) {
        setError("Aucune partie avec ce code.");
        setBusy(false);
        return;
      }
      localStorage.setItem(`quiz:pseudo:${c}`, p);
      localStorage.setItem("quiz:lastPseudo", p);
      router.push(`/play/${c}`);
    } catch {
      setError("Le serveur ne répond pas.");
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-14">
      <p className="font-mono text-xs uppercase tracking-[0.35em] text-muted">Joueur</p>
      <h1 className="mt-3 font-display text-6xl leading-none">Rejoindre</h1>

      <form onSubmit={join} className="mt-8 flex flex-col gap-4">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="CODE"
          maxLength={6}
          autoCapitalize="characters"
          autoComplete="off"
          autoFocus={!code}
          enterKeyHint="next"
          className="rounded-2xl border border-panel2 bg-panel px-5 py-5 text-center font-display text-5xl tracking-[0.3em] outline-none placeholder:text-muted/50 focus:border-muted"
        />
        <input
          value={pseudo}
          onChange={(e) => setPseudo(e.target.value)}
          placeholder="Ton pseudo"
          maxLength={24}
          enterKeyHint="go"
          className="rounded-2xl border border-panel2 bg-panel px-5 py-4 text-xl outline-none placeholder:text-muted focus:border-muted"
        />
        <Button type="submit" variant="accent" size="lg" disabled={busy} className="w-full tracking-wide">
          {busy ? "Connexion…" : "C'est parti"}
        </Button>
      </form>

      {error && <p className="mt-5 rounded-xl border border-buzz/40 bg-buzz/10 px-4 py-3 text-buzz">{error}</p>}
    </main>
  );
}
