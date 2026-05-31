// API types + fetch helpers for the Sollicitaties2026 dashboard.
// Mirrors the FastAPI contract in api.py.

export type Tier = "strong" | "consider" | "low"

export interface Profile {
  name: string
  location: string
  target_titles: string[]
  core_skills: string[]
  languages: string[]
}

export interface Listing {
  title: string
  company: string
  location?: string
  remote?: string
  source_site?: string
  apply_url?: string
  score: number
  tier: Tier
  flags?: string[]
  skills?: string[]
  languages?: string[]
  description_summary?: string
  posted_date?: string
  experience_level?: string
}

export interface Application extends Listing {
  job_id: string
  applied_date: string
  cover_letter?: string
}

export interface Scan {
  name: string
  stem: string
}

export interface ScanResult {
  file: string | null
  listings: Listing[]
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`)
  return res.json() as Promise<T>
}

export const api = {
  profile: () => getJson<Profile>("/api/profile"),
  scans: () => getJson<Scan[]>("/api/scans"),
  latest: () => getJson<ScanResult>("/api/scan/latest"),
  scan: (name: string) => getJson<ScanResult>(`/api/scan/${encodeURIComponent(name)}`),
  status: () => getJson<{ running: boolean }>("/api/scan/status"),

  async runScan(): Promise<"started" | "already-running"> {
    const res = await fetch("/api/scan/run", { method: "POST" })
    if (res.status === 409) return "already-running"
    if (!res.ok) throw new Error("scan failed to start")
    return "started"
  },

  applications: () => getJson<Application[]>("/api/applications"),

  async saveApplication(job: Listing, letter?: string): Promise<{ ok: boolean; job_id: string }> {
    const body = letter ? { ...job, cover_letter: letter } : job
    const res = await fetch("/api/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error("could not save application")
    return res.json()
  },

  async deleteApplication(jobId: string): Promise<void> {
    const res = await fetch(`/api/applications/${jobId}`, { method: "DELETE" })
    if (!res.ok) throw new Error("could not delete application")
  },

  async generateLetter(job: Listing): Promise<string> {
    const res = await fetch("/api/generate-letter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(job),
    })
    if (!res.ok) throw new Error("could not generate letter")
    const data = (await res.json()) as { letter: string }
    return data.letter
  },
}

// ── Presentation helpers ──────────────────────────────────────────────

export const TIER_META: Record<Tier, { label: string; color: string }> = {
  strong: { label: "Sterk", color: "var(--tier-strong)" },
  consider: { label: "Overweeg", color: "var(--tier-consider)" },
  low: { label: "Laag", color: "var(--tier-low)" },
}

export function tierColor(tier: string): string {
  return TIER_META[tier as Tier]?.color ?? "var(--tier-low)"
}

export function tierLabel(tier: string): string {
  return TIER_META[tier as Tier]?.label ?? tier
}

/** Stable identity for a listing without recomputing the server-side md5. */
export function listingKey(job: Listing): string {
  return `${job.title}|${job.company}|${job.apply_url ?? ""}`
}

export function postedAgo(dateStr?: string): string | null {
  if (!dateStr || dateStr === "unknown" || dateStr === "") return null
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000)
  if (days === 0) return "vandaag"
  if (days === 1) return "gisteren"
  if (days < 7) return `${days} dagen geleden`
  if (days < 14) return "vorige week"
  if (days < 30) return `${Math.floor(days / 7)} weken geleden`
  if (days < 60) return "vorige maand"
  return `${Math.floor(days / 30)} maanden geleden`
}

export function formatAppliedDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("nl-BE", { day: "numeric", month: "long", year: "numeric" })
}
