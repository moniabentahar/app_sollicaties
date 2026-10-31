import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search, ExternalLink, CheckCircle2, Loader2, Calendar, MapPin, Building2, Upload, Sparkles } from "lucide-react";
import { toast } from "sonner";
import demoData from "@/data/listings.json";

import { APP_VERSION } from "@/version";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { JobDetailDialog } from "@/components/JobDetailDialog";
import { CoverLetterDialog } from "@/components/CoverLetterDialog";
import {
  api,
  formatAppliedDate,
  formatNextScan,
  listingKey,
  jobMatchKey,
  parseScanFileName,
  postedAgo,
  tierColor,
  tierLabel,
  type Application,
  type FitAdvice,
  type Listing,
  type Profile,
  type Scan,
  type ScheduleInfo,
  type Tier,
} from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sollicitaties2026 — Job Scan Dashboard" },
      { name: "description", content: "Job scan dashboard — België 2026." },
    ],
  }),
  component: App,
});

const TIER_FILTERS: Array<{ value: Tier | "all"; label: string }> = [
  { value: "all", label: "Alle" },
  { value: "strong", label: "Sterk" },
  { value: "consider", label: "Overweeg" },
  { value: "low", label: "Laag" },
];

const POLL_INTERVAL_MS = 2500;

/** Dutch labels for the work arrangement shown in the card footer. */
const REMOTE_LABEL: Record<string, string> = {
  onsite: "Op kantoor",
  hybrid: "Hybride",
  remote: "Thuiswerk",
};

/** Ensure every listing has a tier. The live backend already classifies each job
 * (only real marketing/sponsorship/partnership titles can be strong/consider —
 * a high score alone is not enough, so payroll/office roles stay low). We trust
 * that tier. The static demo JSON has no tier, so we derive one from its score. */
const STRONG_MIN = 5;
const CONSIDER_MIN = 4;
function withTier(items: Record<string, unknown>[]): Listing[] {
  return items.map((l) => ({
    ...l,
    tier:
      typeof l.tier === "string" && l.tier
        ? l.tier
        : Number(l.score) >= STRONG_MIN
          ? "strong"
          : Number(l.score) >= CONSIDER_MIN
            ? "consider"
            : "low",
  })) as Listing[];
}

const DEMO_LISTINGS = withTier(demoData.listings as Record<string, unknown>[]);

/** First letters of the first two words of a name, e.g. "Bruno Vercruysse" → "BV". */
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [listings, setListings] = useState<Listing[]>(DEMO_LISTINGS);
  const [scans, setScans] = useState<Scan[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [selectedFile, setSelectedFile] = useState("");
  const [currentFile, setCurrentFile] = useState(demoData.file);
  const [scanning, setScanning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [isPreview, setIsPreview] = useState(true);

  const [query, setQuery] = useState("");
  const [filterTier, setFilterTier] = useState<Tier | "all">("all");
  const [filterSite, setFilterSite] = useState("all");
  const [tab, setTab] = useState<"listings" | "applied">("listings");

  // Jobs the user marked "not interested" — kept in the browser (per device).
  // Loaded after mount to stay SSR-safe (no hydration mismatch).
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [showHidden, setShowHidden] = useState(false);
  const [showLowScore, setShowLowScore] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("hiddenJobs");
      if (raw) setHidden(new Set(JSON.parse(raw) as string[]));
    } catch {
      /* ignore corrupt storage */
    }
  }, []);

  function toggleHidden(job: Listing) {
    setHidden((prev) => {
      const key = jobMatchKey(job);
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      try {
        window.localStorage.setItem("hiddenJobs", JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const [detailJob, setDetailJob] = useState<Listing | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [letterJob, setLetterJob] = useState<Listing | null>(null);
  const [letterOpen, setLetterOpen] = useState(false);
  const [letterText, setLetterText] = useState("");
  const [cvText, setCvText] = useState("");
  const [letterLoading, setLetterLoading] = useState(false);
  const [letterReadOnly, setLetterReadOnly] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Silently try to upgrade from demo data to live data in the background.
    // The UI is already showing demo data from initial state — no loading spinner needed.
    async function tryLiveData() {
      try {
        const [latest, prof, apps, scansData, sched] = await Promise.all([
          api.latest().catch(() => null),
          api.profile().catch(() => null),
          api.applications().catch(() => null),
          api.scans().catch(() => null),
          api.schedule().catch(() => null),
        ]);
        if (cancelled) return;
        if (latest) {
          setListings(withTier(latest.listings as unknown as Record<string, unknown>[]));
          setCurrentFile(latest.file ?? "");
          setIsPreview(false);
        }
        if (prof) setProfile(prof);
        if (apps) setApplications(apps);
        if (scansData && scansData.length) {
          setScans(scansData);
          setSelectedFile(scansData[0].name);
        }
        if (sched) setSchedule(sched);
      } catch {
        // Backend not available — keep showing demo data, that's fine
      }
    }

    void tryLiveData();
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { running } = await api.status();
        if (!running) {
          if (pollRef.current) clearInterval(pollRef.current);
          setScanning(false);
          // Reload live data after scan completes
          const [latest, scansData] = await Promise.all([
            api.latest().catch(() => null),
            api.scans().catch(() => null),
          ]);
          if (latest) {
            setListings(withTier(latest.listings as unknown as Record<string, unknown>[]));
            setCurrentFile(latest.file ?? "");
            setIsPreview(false);
          }
          if (scansData && scansData.length) {
            setScans(scansData);
            setSelectedFile(scansData[0].name);
          }
          toast.success("Scan voltooid!", {
            description: "Het dashboard is bijgewerkt met de nieuwste resultaten.",
          });
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        setScanning(false);
      }
    }, POLL_INTERVAL_MS);
  }, []);

  async function handleUploadCv(file: File) {
    if (uploading || scanning) return;
    setUploading(true);
    try {
      const prof = await api.uploadCv(file);
      setProfile(prof);
      toast.success("CV verwerkt!", {
        description: `Profiel voor ${prof.name || "kandidaat"} aangemaakt. De scan start nu.`,
        duration: 6000,
      });
      setUploading(false);
      await handleRunScan();
    } catch (err) {
      setUploading(false);
      toast.error("CV kon niet verwerkt worden.", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }

  async function handleRunScan() {
    if (scanning) return;
    setScanning(true);
    try {
      const result = await api.runScan();
      if (result === "started") {
        toast.success("Scan gestart!", {
          description: "Een volledige scan duurt enkele minuten (±3-8). Laat de PC-vensters open; de pagina wordt automatisch bijgewerkt.",
          duration: 7000,
        });
        startPolling();
      } else {
        setScanning(false);
        toast.info("Er loopt al een scan.");
      }
    } catch {
      setScanning(false);
      toast.error("Scan kon niet starten.");
    }
  }

  async function handleLoadScan(name: string) {
    if (!name) return;
    setSelectedFile(name);
    try {
      const data = await api.scan(name);
      setListings(data.listings as Listing[]);
      setCurrentFile(data.file ?? name);
      setIsPreview(false);
    } catch {
      // silent
    }
  }

  const appliedKeys = useMemo(
    () => new Set(applications.map((a) => jobMatchKey(a))),
    [applications],
  );

  const isApplied = useCallback(
    (job: Listing) => appliedKeys.has(jobMatchKey(job)),
    [appliedKeys],
  );

  async function handleToggleApplied(job: Listing) {
    try {
      if (isApplied(job)) {
        const match = applications.find((a) => jobMatchKey(a) === jobMatchKey(job));
        if (match) await api.deleteApplication(match.job_id);
      } else {
        await api.saveApplication(job);
      }
      setApplications(await api.applications());
    } catch {
      toast.error("Kon de status niet bijwerken.");
    }
  }

  async function handleGenerateLetter(job: Listing) {
    setLetterJob(job);
    setLetterText("");
    setCvText("");
    setLetterLoading(true);
    setLetterReadOnly(false);
    setLetterOpen(true);
    try {
      const [letter, cv] = await Promise.all([
        api.generateLetter(job).catch(() => "Kon de brief niet genereren. Probeer opnieuw."),
        api.generateCv(job).catch(() => "Kon het CV niet genereren. Probeer opnieuw."),
      ]);
      setLetterText(letter);
      setCvText(cv);
    } finally {
      setLetterLoading(false);
    }
  }

  async function handleConfirmApply() {
    if (!letterJob) return;
    try {
      await api.saveApplication(letterJob, letterText);
      setApplications(await api.applications());
      if (letterJob.apply_url) {
        window.open(letterJob.apply_url, "_blank", "noopener,noreferrer");
      }
      setLetterOpen(false);
      setDetailOpen(false);
      toast.success("Gesolliciteerd!", { description: `${letterJob.title} bij ${letterJob.company}` });
    } catch {
      toast.error("Kon de sollicitatie niet opslaan.");
    }
  }

  function viewAppliedLetter(app: Application) {
    setLetterJob(app);
    setLetterText(app.cover_letter ?? "");
    setLetterLoading(false);
    setLetterReadOnly(true);
    setLetterOpen(true);
  }

  function openDetail(job: Listing) {
    setDetailJob(job);
    setDetailOpen(true);
  }

  const sites = useMemo(
    () =>
      [...new Set(listings.map((l) => l.source_site).filter(Boolean) as string[])].sort(),
    [listings],
  );

  const tierCount = useCallback(
    (t: Tier) => listings.filter((l) => l.tier === t).length,
    [listings],
  );

  const statCards = useMemo(
    () => [
      { tier: "all" as const, label: "Totaal", value: listings.length, color: "var(--foreground)" },
      { tier: "strong" as const, label: "Sterk", value: tierCount("strong"), color: tierColor("strong") },
      { tier: "consider" as const, label: "Overweeg", value: tierCount("consider"), color: tierColor("consider") },
      { tier: "low" as const, label: "Laag", value: tierCount("low"), color: tierColor("low") },
    ],
    [listings.length, tierCount],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return listings
      .filter((l) => {
        // Hide clear non-matches (score < 3) by default. Real marketing/comms roles
        // always score ≥3 via the title-match bonus, so the relevant ones stay.
        // Bypassable via showLowScore so a specific job is never unreachable.
        if (!showLowScore && (Number(l.score) || 0) < 3) return false;
        if (!showHidden && hidden.has(jobMatchKey(l))) return false;
        if (filterTier !== "all" && l.tier !== filterTier) return false;
        if (filterSite !== "all" && l.source_site !== filterSite) return false;
        if (q) {
          const hay = `${l.title} ${l.company} ${l.location ?? ""}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      })
      // New vacancies always on top; within each group the best matches first.
      .sort((a, b) => {
        const an = a.is_new ? 1 : 0;
        const bn = b.is_new ? 1 : 0;
        if (an !== bn) return bn - an;
        return (Number(b.score) || 0) - (Number(a.score) || 0);
      });
  }, [listings, query, filterTier, filterSite, hidden, showHidden, showLowScore]);

  const hiddenInView = useMemo(
    () => listings.filter((l) => hidden.has(jobMatchKey(l))).length,
    [listings, hidden],
  );

  const lowScoreInView = useMemo(
    () => listings.filter((l) => (Number(l.score) || 0) < 3).length,
    [listings],
  );

  return (
    <div className="grain relative min-h-screen">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-5 py-4">
          <div className="flex items-baseline gap-3">
            <h1 className="font-display text-xl font-bold tracking-tight">
              Sollicitaties<span className="text-accent">2026</span>
            </h1>
            {profile?.name ? (
              <span className="hidden items-center gap-2 sm:flex">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-[10px] font-bold text-background">
                  {initialsOf(profile.name)}
                </span>
                <span className="leading-tight">
                  <span className="block text-xs font-bold text-foreground">{profile.name}</span>
                  {profile.location && (
                    <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                      {profile.location}
                    </span>
                  )}
                  {profile.languages && profile.languages.length > 0 && (
                    <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                      {profile.languages.join(" · ")}
                    </span>
                  )}
                </span>
              </span>
            ) : (
              <span className="hidden text-xs text-muted-foreground sm:inline">
                Upload een CV om te starten
              </span>
            )}
          </div>

          <div className="ml-auto flex items-center gap-3">
            {scanning && (
              <span className="flex items-center gap-2 text-xs font-medium text-amber-600">
                <span className="live-dot h-2 w-2 rounded-full bg-amber-500" /> scannen…
              </span>
            )}
            {scans.length > 1 && (
              <select
                value={selectedFile}
                onChange={(e) => handleLoadScan(e.target.value)}
                className="rounded-lg border border-input bg-card px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                {scans.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.stem}
                  </option>
                ))}
              </select>
            )}
            <span className="rounded-md border border-border bg-muted px-2.5 py-1 text-[11px] font-bold tabular-nums text-foreground">
              Sollicitaties2026 V{APP_VERSION}
            </span>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-5 py-8">
        {/* Scan hero */}
        <ScanHero
          scanning={scanning}
          uploading={uploading}
          profileName={profile?.name ?? ""}
          currentFile={currentFile}
          schedule={schedule}
          isPreview={isPreview}
          onScan={handleRunScan}
          onUploadCv={handleUploadCv}
        />

        {/* Stat cards */}
        <section className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {statCards.map((stat) => {
            const active = filterTier === stat.tier;
            return (
              <button
                key={stat.tier}
                onClick={() =>
                  setFilterTier((prev) => (prev === stat.tier ? "all" : (stat.tier as Tier | "all")))
                }
                className={`card-lift rounded-2xl border bg-card p-4 text-left shadow-sm hover:shadow-md ${
                  active ? "border-foreground ring-2 ring-foreground/10" : "border-border"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className="font-display text-3xl font-bold tabular-nums"
                    style={{ color: stat.color }}
                  >
                    {stat.value}
                  </span>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: stat.color }} />
                </div>
                <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {stat.label}
                </p>
              </button>
            );
          })}
        </section>

        {/* Tabs */}
        <div className="mb-6 flex gap-1 rounded-lg border border-input bg-card p-1 sm:w-fit">
          <button
            onClick={() => setTab("listings")}
            className={`flex-1 rounded-md px-4 py-1.5 text-sm font-semibold transition sm:flex-none ${
              tab === "listings" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Vacatures
          </button>
          <button
            onClick={() => setTab("applied")}
            className={`flex-1 rounded-md px-4 py-1.5 text-sm font-semibold transition sm:flex-none ${
              tab === "applied" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Gesolliciteerd
            {applications.length > 0 && (
              <span className="ml-1.5 rounded-full bg-accent/15 px-1.5 py-0.5 text-[11px] text-accent">
                {applications.length}
              </span>
            )}
          </button>
        </div>

        {tab === "listings" ? (
          <>
            {/* Filters */}
            <section className="mb-6 flex flex-wrap items-center gap-2">
              <div className="relative min-w-[220px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Zoek op functie, bedrijf, locatie…"
                  className="w-full rounded-lg border border-input bg-card py-2 pl-9 pr-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
                />
              </div>

              <div className="flex gap-1 rounded-lg border border-input bg-card p-1">
                {TIER_FILTERS.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setFilterTier(t.value)}
                    className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                      filterTier === t.value
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <select
                value={filterSite}
                onChange={(e) => setFilterSite(e.target.value)}
                className="rounded-lg border border-input bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                <option value="all">Alle sites</option>
                {sites.map((site) => (
                  <option key={site} value={site}>
                    {site}
                  </option>
                ))}
              </select>
            </section>

            {/* Content */}
            {listings.length === 0 ? (
              <EmptyState
                title="Nog geen vacatures"
                body="Klik op Start scan om verse vacatures op te halen en te scoren."
              />
            ) : (
              <section className="space-y-3">
                <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {filtered.length} van {listings.length} vacatures
                    {currentFile ? ` · ${currentFile}` : ""}
                  </p>
                  {hiddenInView > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowHidden((v) => !v)}
                      className="text-xs font-medium text-muted-foreground underline-offset-2 hover:underline"
                    >
                      {showHidden
                        ? "Verberg niet-interessante"
                        : `Toon ${hiddenInView} niet-interessante`}
                    </button>
                  )}
                  {lowScoreInView > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowLowScore((v) => !v)}
                      className="text-xs font-medium text-muted-foreground underline-offset-2 hover:underline"
                    >
                      {showLowScore
                        ? "Verberg lage scores"
                        : `Toon ${lowScoreInView} lage scores`}
                    </button>
                  )}
                </div>
                {filtered.map((job) => (
                  <JobCard
                    key={listingKey(job)}
                    job={job}
                    applied={isApplied(job)}
                    hidden={hidden.has(jobMatchKey(job))}
                    onOpen={() => openDetail(job)}
                    onApply={() => handleGenerateLetter(job)}
                    onToggleApplied={() => handleToggleApplied(job)}
                    onHide={() => toggleHidden(job)}
                  />
                ))}
                {filtered.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                    Geen vacatures komen overeen met deze filters.
                  </div>
                )}
              </section>
            )}
          </>
        ) : (
          <AppliedList
            applications={applications}
            onOpen={openDetail}
            onRemove={(a) => handleToggleApplied(a)}
            onViewLetter={viewAppliedLetter}
          />
        )}
      </main>

      <footer className="relative z-10 mx-auto max-w-6xl px-5 py-8 text-center text-xs text-muted-foreground/70">
        Sollicitaties2026 · gescoord tegen {profile?.target_titles?.length ?? 0} doelfuncties ·{" "}
        {profile?.core_skills?.length ?? 0} kernvaardigheden
      </footer>

      <JobDetailDialog
        job={detailJob}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        applied={detailJob ? isApplied(detailJob) : false}
        onGenerateLetter={handleGenerateLetter}
        onToggleApplied={handleToggleApplied}
      />

      <CoverLetterDialog
        open={letterOpen}
        onOpenChange={setLetterOpen}
        job={letterJob}
        letter={letterText}
        cv={cvText}
        loading={letterLoading}
        onLetterChange={setLetterText}
        onCvChange={setCvText}
        onConfirm={letterReadOnly ? undefined : handleConfirmApply}
        readOnly={letterReadOnly}
      />
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

interface ScanHeroProps {
  scanning: boolean;
  uploading: boolean;
  profileName: string;
  currentFile: string;
  schedule: ScheduleInfo | null;
  isPreview: boolean;
  onScan: () => void;
  onUploadCv: (file: File) => void;
}

/** Lets the user point the app at their own backend (e.g. a PC tunnel URL),
 *  saved in the browser so it works on Lovable without any rebuild. */
function ConnectBackend() {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("apiBaseUrl") ?? "" : "",
  );
  const current = typeof window !== "undefined" ? localStorage.getItem("apiBaseUrl") : "";

  function connect() {
    localStorage.setItem("apiBaseUrl", url.trim().replace(/\/+$/, ""));
    window.location.reload();
  }
  function reset() {
    localStorage.removeItem("apiBaseUrl");
    window.location.reload();
  }

  return (
    <div className="border-t border-border bg-muted/30 px-6 py-2.5 text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="font-medium text-muted-foreground hover:text-foreground"
      >
        ⚙ Backend instellen{current ? " — verbonden met je eigen backend ✓" : ""}
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://....loca.lt  (jouw tunnel-URL)"
            className="flex-1 rounded-md border border-input bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
          <Button size="sm" onClick={connect} disabled={!url.trim()}>
            Verbind
          </Button>
          {current && (
            <Button size="sm" variant="outline" onClick={reset}>
              Standaard
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function AboutMe() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .profile()
      .then((p) => setText(p.about ?? ""))
      .catch(() => undefined)
      .finally(() => setLoaded(true));
  }, []);

  async function save() {
    try {
      await api.saveAbout(text);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      toast.error("Kon 'Over mij' niet opslaan.");
    }
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try {
      let extracted: string;
      try {
        // Normal multipart upload (this works in Lovable).
        extracted = await api.uploadAbout(file);
      } catch {
        // Fallback: read in the browser + send base64 (for sandboxes that block multipart).
        if (/\.(txt|md)$/i.test(file.name)) {
          extracted = await file.text();
        } else {
          const dataUrl: string = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result));
            r.onerror = () => reject(new Error("kon het bestand niet lezen"));
            r.readAsDataURL(file);
          });
          extracted = await api.uploadAboutBase64(file.name, dataUrl);
        }
      }
      setText((prev) => (prev.trim() ? `${prev.trim()}\n\n${extracted}` : extracted));
      toast.success("Bestand toegevoegd — controleer de tekst en klik Opslaan.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Kon het bestand niet lezen.");
    }
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <div className="border-t border-border bg-muted/30 px-6 py-2.5 text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="font-medium text-muted-foreground hover:text-foreground"
      >
        🧬 Over mij — testprofiel & aanbevelingen{loaded && text ? " — ingevuld ✓" : ""}
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="text-[11px] text-muted-foreground">
            Plak hier je persoonlijkheidsprofiel (uit testen), je aanbevelingen en wat anderen over je
            zeggen. Het AI-advies per vacature houdt hier dan rekening mee — niet alleen je ervaring,
            maar ook wie je bent.
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            placeholder="Bv. resultaten van je testprofiel, LinkedIn-aanbevelingen, citaten van collega's of leidinggevenden…"
            className="w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={save} disabled={!loaded || busy}>
              Opslaan
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()} disabled={busy}>
              {busy ? "Inlezen…" : "📎 Bestand toevoegen (PDF)"}
            </Button>
            {saved && <span className="font-medium text-accent">Opgeslagen ✓</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function ScanHero({
  scanning,
  uploading,
  profileName,
  currentFile,
  schedule,
  isPreview,
  onScan,
  onUploadCv,
}: ScanHeroProps) {
  const nextLabel = schedule?.next_run ? formatNextScan(schedule.next_run) : null;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const busy = scanning || uploading;

  return (
    <div className="mb-8 overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-6 p-6">
        <div className="space-y-1">
          <h2 className="font-display text-xl font-bold tracking-tight">Vacatures scannen</h2>
          <p className="text-sm text-muted-foreground">
            Upload een CV en doorzoek alle Belgische jobsites op een match met dat profiel
          </p>
          {!isPreview && !profileName && (
            <p className="text-xs font-medium text-accent">
              Upload eerst een CV (PDF) om het kandidaatprofiel te bepalen.
            </p>
          )}
          {!isPreview && profileName && (
            <p className="text-xs text-muted-foreground">
              Profiel: <span className="font-medium text-foreground">{profileName}</span>
            </p>
          )}
          {currentFile && !isPreview && (
            <p className="text-xs text-muted-foreground">
              Laatste scan: {parseScanFileName(currentFile)}
            </p>
          )}
          {nextLabel && !isPreview && (
            <p className="text-xs font-medium text-accent">
              Volgende automatische scan: {nextLabel}
            </p>
          )}
          {!isPreview && !nextLabel && (
            <p className="text-xs text-muted-foreground">
              Automatisch elke donderdag om 08:00
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUploadCv(file);
              e.target.value = "";
            }}
          />
          <Button
            size="lg"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={busy}
            className="min-w-[160px] gap-2 text-base"
          >
            {uploading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                CV verwerken…
              </>
            ) : (
              <>
                <Upload className="h-5 w-5" />
                Upload CV
              </>
            )}
          </Button>

          <Button
            size="lg"
            onClick={onScan}
            disabled={busy}
            className="min-w-[160px] gap-2 text-base"
          >
            {scanning ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Bezig…
              </>
            ) : (
              <>
                <Search className="h-5 w-5" />
                Start scan
              </>
            )}
          </Button>
        </div>
      </div>

      <AboutMe />
      <ConnectBackend />

      {scanning && !isPreview && (
        <div className="border-t border-border bg-muted/40 px-6 py-3">
          <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
            <span>Vacaturesites worden gescand…</span>
            <span>± 2–3 minuten</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full animate-pulse rounded-full bg-accent" style={{ width: "70%" }} />
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card/50 p-12 text-center">
      <p className="font-display text-lg font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

interface JobCardProps {
  job: Listing;
  applied: boolean;
  hidden: boolean;
  onOpen: () => void;
  onApply: () => void;
  onToggleApplied: () => void;
  onHide: () => void;
}

const FIT_META: Record<string, { label: string; color: string }> = {
  sterk: { label: "Sterke match", color: "var(--tier-strong)" },
  overweeg: { label: "Overweeg", color: "var(--tier-consider)" },
  zwak: { label: "Zwakke match", color: "var(--tier-low)" },
};

function JobCard({ job, applied, hidden, onOpen, onApply, onToggleApplied, onHide }: JobCardProps) {
  const posted = postedAgo(job.posted_date);
  const remoteLabel =
    job.remote && job.remote !== "unknown" ? REMOTE_LABEL[job.remote] ?? job.remote : null;
  const [advice, setAdvice] = useState<FitAdvice | null>(null);
  const [loadingAdvice, setLoadingAdvice] = useState(false);

  async function getAdvice() {
    if (loadingAdvice || advice) return;
    setLoadingAdvice(true);
    try {
      setAdvice(await api.analyzeFit(job));
    } catch {
      setAdvice({ fit: "", analysis: "Advies kon niet worden gegenereerd. Probeer opnieuw.", recommendation: "" });
    }
    setLoadingAdvice(false);
  }

  // Once the AI advice is in, let the tier label follow it (the advice knows your
  // real fit; the score is only a keyword pre-filter) so they never contradict.
  const FIT_TO_TIER: Record<string, "strong" | "consider" | "low"> = {
    sterk: "strong",
    overweeg: "consider",
    zwak: "low",
  };
  const shownTier = advice?.fit && FIT_TO_TIER[advice.fit] ? FIT_TO_TIER[advice.fit] : job.tier;
  // Keep the score number in step with the (advice-aware) tier so a high keyword
  // score never sits next to a "weak" verdict: low → ≤3, consider → 4, strong → ≥5.
  const clampScoreToTier = (s: number, t: "strong" | "consider" | "low"): number =>
    t === "low" ? Math.min(s, 3) : t === "consider" ? 4 : Math.max(s, 5);
  const shownScore =
    advice?.fit && FIT_TO_TIER[advice.fit] ? clampScoreToTier(job.score, FIT_TO_TIER[advice.fit]) : job.score;
  const shownColor = tierColor(shownTier);

  return (
    <article
      onClick={onOpen}
      className="card-lift cursor-pointer rounded-2xl border border-border bg-card p-4 shadow-sm hover:shadow-md"
      style={{ borderLeft: `4px solid ${shownColor}` }}
    >
      <div className="flex flex-wrap items-start gap-3">
        <div
          className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl text-white"
          style={{ background: shownColor }}
        >
          <span className="font-display text-lg font-bold leading-none tabular-nums">{shownScore}</span>
          <span className="text-[9px] uppercase tracking-wide opacity-80">score</span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-base font-bold leading-tight">{job.title}</h3>
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
              style={{
                background: `color-mix(in oklab, ${tierColor(shownTier)} 12%, transparent)`,
                color: tierColor(shownTier),
              }}
            >
              {tierLabel(shownTier)}
            </span>
            {job.is_new && (
              <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                Nieuw
              </span>
            )}
            {applied && (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-accent">
                <CheckCircle2 className="h-3 w-3" /> Gesolliciteerd
              </span>
            )}
          </div>

          <p className="mt-0.5 text-sm font-semibold text-foreground">{job.company}</p>

          {job.flags && job.flags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {job.flags.map((flag) => (
                <span key={flag} className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {flag}
                </span>
              ))}
            </div>
          )}

          {job.skills && job.skills.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {job.skills.slice(0, 6).map((skill) => (
                <span
                  key={skill}
                  className="rounded-md border border-accent/25 bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {job.source_site && (
            <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              {job.source_site}
            </span>
          )}
          {job.apply_url && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onApply();
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-input px-3 py-1.5 text-xs font-semibold transition hover:bg-foreground hover:text-background"
            >
              Solliciteer <ExternalLink className="h-3.5 w-3.5" />
            </button>
          )}

          <div className="flex items-center gap-2 text-[11px]">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleApplied();
              }}
              className={`font-medium ${applied ? "text-accent" : "text-muted-foreground hover:text-foreground"}`}
            >
              {applied ? "✓ Gesolliciteerd" : "Al gesolliciteerd"}
            </button>
            <span className="text-border">·</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onHide();
              }}
              className="font-medium text-muted-foreground hover:text-foreground"
            >
              {hidden ? "Terugzetten" : "Niet interessant"}
            </button>
            <span className="text-border">·</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                getAdvice();
              }}
              className="inline-flex items-center gap-1 font-semibold text-accent hover:underline"
            >
              <Sparkles className="h-3 w-3" /> {loadingAdvice ? "Advies…" : "Advies"}
            </button>
          </div>
        </div>
      </div>

      {/* Footer: samenvatting + datum · locatie · werkvorm */}
      <div className="mt-3 border-t border-border/60 pt-2.5">
        {job.description_summary && (
          <p className="text-xs leading-relaxed text-muted-foreground">{job.description_summary}</p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-medium text-muted-foreground">
          {posted && (
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" /> {posted}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5" /> {job.location || "—"}
          </span>
          {remoteLabel && (
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" /> {remoteLabel}
            </span>
          )}
        </div>

        {(loadingAdvice || advice) && (
          <div className="mt-2.5 rounded-lg border border-border bg-muted/40 p-2.5 text-xs" onClick={(e) => e.stopPropagation()}>
            {loadingAdvice ? (
              <p className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Advies obv je CV & profiel genereren…
              </p>
            ) : (
              advice && (
                <>
                  {advice.fit && FIT_META[advice.fit] && (
                    <span
                      className="mb-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                      style={{
                        background: `color-mix(in oklab, ${FIT_META[advice.fit].color} 14%, transparent)`,
                        color: FIT_META[advice.fit].color,
                      }}
                    >
                      {FIT_META[advice.fit].label}
                    </span>
                  )}
                  <p className="leading-relaxed text-foreground">{advice.analysis}</p>
                  {advice.recommendation && (
                    <p className="mt-1 font-semibold text-foreground">→ {advice.recommendation}</p>
                  )}
                </>
              )
            )}
          </div>
        )}
      </div>
    </article>
  );
}

interface AppliedListProps {
  applications: Application[];
  onOpen: (job: Listing) => void;
  onRemove: (job: Application) => void;
  onViewLetter: (app: Application) => void;
}

function AppliedList({ applications, onOpen, onRemove, onViewLetter }: AppliedListProps) {
  if (applications.length === 0) {
    return (
      <EmptyState
        title="Nog niets gesolliciteerd"
        body="Open een vacature en markeer ze als gesolliciteerd om ze hier bij te houden."
      />
    );
  }
  return (
    <section className="space-y-3">
      {applications.map((app) => {
        const color = tierColor(app.tier);
        return (
          <article
            key={app.job_id}
            className="card-lift rounded-2xl border border-border bg-card p-4 shadow-sm hover:shadow-md"
            style={{ borderLeft: `4px solid ${color}` }}
          >
            <div className="flex flex-wrap items-start gap-3">
              <div className="min-w-0 flex-1 cursor-pointer" onClick={() => onOpen(app)}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-display text-base font-bold leading-tight">{app.title}</h3>
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                    style={{ background: `color-mix(in oklab, ${color} 12%, transparent)`, color }}
                  >
                    {tierLabel(app.tier)}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  <span className="font-semibold text-foreground">{app.company}</span>
                  {" · "}
                  {app.location || "—"}
                </p>
                <p className="mt-1 text-xs text-accent">
                  Gesolliciteerd op {formatAppliedDate(app.applied_date)}
                </p>
              </div>

              <div className="flex shrink-0 flex-col items-end gap-2">
                {app.cover_letter && (
                  <Button variant="outline" size="sm" onClick={() => onViewLetter(app)}>
                    Bekijk brief
                  </Button>
                )}
                {app.apply_url && (
                  <a
                    href={app.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-lg border border-input px-3 py-1.5 text-xs font-semibold transition hover:bg-foreground hover:text-background"
                  >
                    Vacature <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
                <Button variant="ghost" size="sm" onClick={() => onRemove(app)}>
                  Verwijderen
                </Button>
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
