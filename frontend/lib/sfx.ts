"use client";

// Tiny self-contained sound + haptics layer for the party feel — no audio assets,
// just WebAudio oscillator blips. All calls are no-ops when muted, on the server,
// or when the browser blocks audio (e.g. a TV with no user gesture).
//
// Mute state is shared across the app via localStorage + a subscriber list so the
// header toggle and the sound calls stay in sync.

const MUTE_KEY = "boucan:muted";

let ctx: AudioContext | null = null;
const listeners = new Set<(muted: boolean) => void>();

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function isMuted(): boolean {
  if (!isBrowser()) return false;
  return window.localStorage.getItem(MUTE_KEY) === "1";
}

export function setMuted(muted: boolean): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  listeners.forEach((fn) => fn(muted));
}

export function subscribeMuted(fn: (muted: boolean) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function audio(): AudioContext | null {
  if (!isBrowser()) return null;
  try {
    if (!ctx) {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return null;
      ctx = new Ctor();
    }
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

interface ToneOpts {
  freq: number;
  durMs: number;
  type?: OscillatorType;
  gain?: number;
  at?: number; // seconds offset from now
  slideTo?: number; // optional end frequency for a glide
}

function tone({ freq, durMs, type = "sine", gain = 0.18, at = 0, slideTo }: ToneOpts): void {
  const ac = audio();
  if (!ac) return;
  const t0 = ac.currentTime + at;
  const dur = durMs / 1000;
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur);
  // Soft attack + decay so blips don't click.
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g).connect(ac.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

export function vibrate(pattern: number | number[]): void {
  if (!isBrowser() || isMuted()) return;
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* unsupported — ignore */
  }
}

// --- Named cues -----------------------------------------------------------

/** A player slaps the buzzer: punchy blip + a short haptic kick. */
export function buzz(): void {
  vibrate(35);
  if (isMuted()) return;
  tone({ freq: 320, slideTo: 660, durMs: 140, type: "square", gain: 0.2 });
}

/** Correct answer / points won. */
export function correct(): void {
  if (isMuted()) return;
  tone({ freq: 660, durMs: 110, type: "triangle" });
  tone({ freq: 990, durMs: 160, type: "triangle", at: 0.1 });
}

/** Wrong / missed. */
export function wrong(): void {
  vibrate([20, 40, 20]);
  if (isMuted()) return;
  tone({ freq: 200, slideTo: 120, durMs: 260, type: "sawtooth", gain: 0.16 });
}

/** One 3-2-1 countdown tick. */
export function tick(): void {
  if (isMuted()) return;
  tone({ freq: 520, durMs: 70, type: "square", gain: 0.12 });
}

/** The "go" at the end of a countdown / track start. */
export function go(): void {
  if (isMuted()) return;
  tone({ freq: 880, durMs: 220, type: "square", gain: 0.18 });
}
