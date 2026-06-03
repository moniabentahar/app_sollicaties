import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search, ExternalLink, CheckCircle2, Loader2, Calendar, MapPin, Building2 } from "lucide-react";
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
  parseScanFileName,
  postedAgo,
  tierColor,
  tierLabel,
  type Application,
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
      { name: "description", content: "Job scan dashboard voor the candidate — België 2026." },
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

/** Add tier field to items that come from the static JSON (which lacks it). */
function withTier(items: Record<string, unknown>[]): Listing[] {
  return items.map((l) => ({
    ...l,
    tier: (l.tier as Tier | undefined) ??
      (Number(l.score) >= 7 ? "strong" : Number(l.score) >= 4 ? "consider" : "low"),
  })) as Listing[];
}

const DEMO_LISTINGS = withTier(demoData.listings as Record<string, unknown>[]);

function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [listings, setListings] = useState<Listing[]>(DEMO_LISTINGS);
  const [scans, setScans] = useState<Scan[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [selectedFile, setSelectedFile] = useState("");
  const [currentFile, setCurrentFile] = useState(demoData.file);
  const [scanning, setScanning] = useState(false);
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [isPreview, setIsPreview] = useState(true);

  const [query, setQuery] = useState("");
  const [filterTier, setFilterTier] = useState<Tier | "all">("all");
  const [filterSite, setFilterSite] = useState("all");
  const [tab, setTab] = useState<"listings" | "applied">("listings");

  const [detailJob, setDetailJob] = useState<Listing | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [letterJob, setLetterJob] = useState<Listing | null>(null);
  const [letterOpen, setLetterOpen] = useState(false);
  const [letterText, setLetterText] = useState("");
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
          setListings(withTier(latest.listings as Record<string, unknown>[]));
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
            setListings(withTier(latest.listings as Record<string, unknown>[]));
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

  async function handleRunScan() {
    if (scanning) return;
    if (isPreview) {
      toast.info("Scannen werkt alleen in de lokale app", {
        description:
          "Start de Python-backend (uvicorn) en open de app lokaal. In deze online preview zie je voorbeelddata.",
        duration: 7000,
      });
      return;
    }
    setScanning(true);
    try {
      const result = await api.runScan();
      if (result === "started") {
        toast.success("Scan gestart!", {
          description: "Een volledige scan duurt ±2-3 minuten. De pagina wordt automatisch bijgewerkt.",
          duration: 6000,
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
    () => new Set(applications.map((a) => listingKey(a))),
    [applications],
  );

  const isApplied = useCallback(
    (job: Listing) => appliedKeys.has(listingKey(job)),
    [appliedKeys],
  );

  async function handleToggleApplied(job: Listing) {
    try {
      if (isApplied(job)) {
        const match = applications.find((a) => listingKey(a) === listingKey(job));
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
    setLetterLoading(true);
    setLetterReadOnly(false);
    setLetterOpen(true);
    try {
      setLetterText(await api.generateLetter(job));
    } catch {
      setLetterText("Kon de brief niet genereren. Probeer het opnieuw.");
    }
    setLetterLoading(false);
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
    return listings.filter((l) => {
      if (filterTier !== "all" && l.tier !== filterTier) return false;
      if (filterSite !== "all" && l.source_site !== filterSite) return false;
      if (q) {
        const hay = `${l.title} ${l.company} ${l.location ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [listings, query, filterTier, filterSite]);

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
            <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
              v{APP_VERSION}
            </span>
            {profile?.name && (
              <span className="hidden text-xs text-muted-foreground sm:inline">
                voor {profile.name}
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
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-5 py-8">
        {/* Scan hero */}
        <ScanHero
          scanning={scanning}
          currentFile={currentFile}
          schedule={schedule}
          isPreview={isPreview}
          onScan={handleRunScan}
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
                <p className="mb-1 text-xs text-muted-foreground">
                  {filtered.length} van {listings.length} vacatures
                  {currentFile ? ` · ${currentFile}` : ""}
                </p>
                {filtered.map((job) => (
                  <JobCard
                    key={listingKey(job)}
                    job={job}
                    applied={isApplied(job)}
                    onOpen={() => openDetail(job)}
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
        loading={letterLoading}
        onLetterChange={setLetterText}
        onConfirm={letterReadOnly ? undefined : handleConfirmApply}
        readOnly={letterReadOnly}
      />
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

interface ScanHeroProps {
  scanning: boolean;
  currentFile: string;
  schedule: ScheduleInfo | null;
  isPreview: boolean;
  onScan: () => void;
}

function ScanHero({ scanning, currentFile, schedule, isPreview, onScan }: ScanHeroProps) {
  const nextLabel = schedule?.next_run ? formatNextScan(schedule.next_run) : null;

  return (
    <div className="mb-8 overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-6 p-6">
        <div className="space-y-1">
          <h2 className="font-display text-xl font-bold tracking-tight">Vacatures scannen</h2>
          <p className="text-sm text-muted-foreground">
            Doorzoekt alle Belgische jobsites en matcht vacatures op jouw profiel
          </p>
          {isPreview && (
            <p className="text-xs font-medium text-amber-600">
              Voorbeeldmodus — de scan draait alleen in de lokale app met de Python-backend.
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
              Automatisch elke dinsdag en vrijdag om 08:00
            </p>
          )}
        </div>

        <Button
          size="lg"
          onClick={onScan}
          disabled={scanning}
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
  onOpen: () => void;
}

function JobCard({ job, applied, onOpen }: JobCardProps) {
  const color = tierColor(job.tier);
  const posted = postedAgo(job.posted_date);
  const remoteLabel =
    job.remote && job.remote !== "unknown" ? REMOTE_LABEL[job.remote] ?? job.remote : null;
  return (
    <article
      onClick={onOpen}
      className="card-lift cursor-pointer rounded-2xl border border-border bg-card p-4 shadow-sm hover:shadow-md"
      style={{ borderLeft: `4px solid ${color}` }}
    >
      <div className="flex flex-wrap items-start gap-3">
        <div
          className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl text-white"
          style={{ background: color }}
        >
          <span className="font-display text-lg font-bold leading-none tabular-nums">{job.score}</span>
          <span className="text-[9px] uppercase tracking-wide opacity-80">score</span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-base font-bold leading-tight">{job.title}</h3>
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
              style={{ background: `color-mix(in oklab, ${color} 12%, transparent)`, color }}
            >
              {tierLabel(job.tier)}
            </span>
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
            <a
              href={job.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 rounded-lg border border-input px-3 py-1.5 text-xs font-semibold transition hover:bg-foreground hover:text-background"
            >
              Solliciteer <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
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
