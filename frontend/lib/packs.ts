// Pack library data helpers (Phase 4). All calls hit the backend via
// backendHttpUrl (the page is on :3200, the API on :8200). Pack files carry
// answers — they are host/editor-side only.

import { backendHttpUrl } from "./backend";
import { Pack, PackSummary } from "./types";

export async function listPacks(): Promise<PackSummary[]> {
  const res = await fetch(backendHttpUrl("/api/packs"));
  if (!res.ok) throw new Error(`listPacks ${res.status}`);
  return (await res.json()).packs as PackSummary[];
}

export async function getPack(id: string): Promise<Pack> {
  const res = await fetch(backendHttpUrl(`/api/packs/${id}`));
  if (!res.ok) throw new Error(`getPack ${res.status}`);
  return (await res.json()) as Pack;
}

export async function savePack(pack: Partial<Pack>): Promise<Pack> {
  const res = await fetch(backendHttpUrl("/api/packs"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pack),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? `savePack ${res.status}`);
  return (await res.json()) as Pack;
}

export async function updatePack(id: string, pack: Partial<Pack>): Promise<Pack> {
  const res = await fetch(backendHttpUrl(`/api/packs/${id}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pack),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? `updatePack ${res.status}`);
  return (await res.json()) as Pack;
}

export async function deletePack(id: string): Promise<void> {
  const res = await fetch(backendHttpUrl(`/api/packs/${id}`), { method: "DELETE" });
  if (!res.ok) throw new Error(`deletePack ${res.status}`);
}

export async function importPack(pack: unknown): Promise<Pack> {
  const res = await fetch(backendHttpUrl("/api/packs/import"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pack),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? `importPack ${res.status}`);
  return (await res.json()) as Pack;
}

// Upload a question image → returns the /media/<file> URL to store on a draft.
export async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(backendHttpUrl("/api/media"), { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? `uploadImage ${res.status}`);
  return (await res.json()).url as string;
}
