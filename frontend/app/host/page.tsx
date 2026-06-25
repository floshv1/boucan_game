"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/Button";
import { createSession } from "@/lib/api";

export default function HostCreate() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setLoading(true);
    setError(null);
    try {
      const { code, host_secret } = await createSession();
      // Only this device can act as host (cahier §16). Kept for host reconnection.
      localStorage.setItem(`quiz:host:${code}`, host_secret);
      router.push(`/host/${code}`);
    } catch {
      setError("Impossible de créer la partie. Le serveur répond-il ?");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-14">
      <p className="font-mono text-xs uppercase tracking-[0.35em] text-muted">Hôte · écran principal</p>
      <h1 className="mt-3 font-display text-6xl leading-none">Nouvelle partie</h1>
      <p className="mt-4 text-lg text-cream/80">
        Lance une session depuis l&apos;ordinateur ou la TV. Les joueurs rejoindront avec le code affiché.
      </p>

      <Button variant="accent" size="lg" onClick={create} disabled={loading} className="mt-10 w-full tracking-wide">
        {loading ? "Création…" : "Créer la partie"}
      </Button>

      {error && <p className="mt-5 rounded-xl border border-buzz/40 bg-buzz/10 px-4 py-3 text-buzz">{error}</p>}
    </main>
  );
}
