import Link from "next/link";

import { buttonClasses } from "@/components/buttonStyles";
import Equalizer from "@/components/Equalizer";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-14">
      <p className="font-mono text-xs uppercase tracking-[0.35em] text-muted">Quiz de soirée · à la maison</p>

      <h1 className="mt-4 flex items-end gap-3 font-display text-display-hero">
        BOUCA<span className="text-buzz">N</span>
        <Equalizer bars={4} className="mb-3 h-[16vw] sm:h-20" />
      </h1>

      <p className="mt-5 text-lg leading-snug text-cream/80">
        Le premier qui buzze a la main. L&apos;hôte mène la partie depuis la TV, vous répondez depuis votre téléphone.
      </p>

      <div className="mt-10 flex flex-col gap-4">
        <Link href="/host" className={buttonClasses("accent", "lg", "py-5 tracking-wide")}>
          Héberger une partie
        </Link>
        <Link href="/play" className={buttonClasses("ghost", "lg", "bg-panel py-5 tracking-wide")}>
          Rejoindre avec un code
        </Link>
      </div>
    </main>
  );
}
