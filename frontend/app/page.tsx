import Link from "next/link";

import Equalizer from "@/components/Equalizer";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-14">
      <p className="font-mono text-xs uppercase tracking-[0.35em] text-muted">Quiz de soirée · à la maison</p>

      <h1 className="mt-4 flex items-end gap-3 font-display text-[22vw] leading-[0.8] sm:text-[128px]">
        BOUCA<span className="text-buzz">N</span>
        <Equalizer bars={4} className="mb-3 h-[16vw] sm:h-20" />
      </h1>

      <p className="mt-5 text-lg leading-snug text-cream/80">
        Le premier qui buzze a la main. L&apos;hôte mène la partie depuis la TV, vous répondez depuis votre téléphone.
      </p>

      <div className="mt-10 flex flex-col gap-4">
        <Link
          href="/host"
          className="rounded-2xl bg-buzz px-6 py-5 text-center font-display text-2xl tracking-wide text-white shadow-[0_10px_0_0_#8e0c2c] transition active:translate-y-1 active:shadow-[0_4px_0_0_#8e0c2c]"
        >
          Héberger une partie
        </Link>
        <Link
          href="/play"
          className="rounded-2xl border border-panel2 bg-panel px-6 py-5 text-center font-display text-2xl tracking-wide text-cream transition hover:border-muted"
        >
          Rejoindre avec un code
        </Link>
      </div>
    </main>
  );
}
