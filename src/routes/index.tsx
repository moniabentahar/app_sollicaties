import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import listingsData from "@/data/listings.json";
import { profile } from "@/data/profile";

type Listing = (typeof listingsData)["listings"][number];

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sollicitaties2026 — Job Scan Dashboard" },
      { name: "description", content: "Ranked marketing job listings for the candidate — Belgium 2026." },
      { property: "og:title", content: "Sollicitaties2026 — Job Scan Dashboard" },
      { property: "og:description", content: "Ranked marketing job listings for the candidate — Belgium 2026." },
    ],
  }),
  component: Index,
});

const TIERS = ["strong", "consider", "low"] as const;
type Tier = (typeof TIERS)[number];

const TIER_META: Record<Tier, { label: string; dot: string; pill: string }> = {
  strong: {
    label: "Strong",
    dot: "bg-[var(--tier-strong)]",
    pill: "bg-[color-mix(in_oklab,var(--tier-strong)_14%,transparent)] text-[var(--tier-strong)] border-[color-mix(in_oklab,var(--tier-strong)_30%,transparent)]",
  },
  consider: {
    label: "Consider",
    dot: "bg-[var(--tier-consider)]",
    pill: "bg-[color-mix(in_oklab,var(--tier-consider)_14%,transparent)] text-[var(--tier-consider)] border-[color-mix(in_oklab,var(--tier-consider)_30%,transparent)]",
  },
  low: {
    label: "Low",
    dot: "bg-[var(--tier-low)]",
    pill: "bg-[color-mix(in_oklab,var(--tier-low)_14%,transparent)] text-[var(--tier-low)] border-[color-mix(in_oklab,var(--tier-low)_30%,transparent)]",
  },
};

function Index() {
  const listings = listingsData.listings as Listing[];
  const [tierFilter, setTierFilter] = useState<Tier | "all">("all");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<string>("all");

  const sources = useMemo(
    () => Array.from(new Set(listings.map((l) => l.source_site))).sort(),
    [listings],
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: listings.length, strong: 0, consider: 0, low: 0 };
    for (const l of listings) c[l.tier] = (c[l.tier] ?? 0) + 1;
    return c;
  }, [listings]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return listings.filter((l) => {
      if (tierFilter !== "all" && l.tier !== tierFilter) return false;
      if (source !== "all" && l.source_site !== source) return false;
      if (!q) return true;
      return (
        l.title.toLowerCase().includes(q) ||
        l.company.toLowerCase().includes(q) ||
        l.location.toLowerCase().includes(q) ||
        l.description_summary.toLowerCase().includes(q)
      );
    });
  }, [listings, tierFilter, query, source]);

  return (
    <div className="grain relative min-h-screen">
      <div className="relative z-10">
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-5 py-4">
            <div className="flex items-baseline gap-3">
              <h1 className="font-display text-xl font-bold tracking-tight">
                Sollicitaties<span className="text-[var(--accent)]">2026</span>
              </h1>
              <span className="hidden text-xs text-muted-foreground sm:inline">
                for {profile.name}
              </span>
            </div>
            <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
              <span>
                Latest scan ·{" "}
                <span className="font-medium text-foreground">{listingsData.file}</span>
              </span>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-5 py-8">
          {/* Profile card */}
          <section className="mb-8 rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="grid gap-6 md:grid-cols-[1fr_2fr]">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  Candidate
                </p>
                <h2 className="font-display mt-1 text-2xl font-semibold">{profile.name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{profile.location}</p>
                <p className="mt-4 text-xs uppercase tracking-wider text-muted-foreground">
                  Languages
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {profile.languages.map((l) => (
                    <span
                      key={l}
                      className="rounded-md border border-border bg-secondary px-2 py-0.5 text-xs"
                    >
                      {l}
                    </span>
                  ))}
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">
                    Target titles
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {profile.targetTitles.map((t) => (
                      <span
                        key={t}
                        className="rounded-md border border-border bg-background px-2 py-0.5 text-xs"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">
                    Core skills
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {profile.coreSkills.map((s) => (
                      <span
                        key={s}
                        className="rounded-md border border-border bg-background px-2 py-0.5 text-xs"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Filters */}
          <section className="mb-6 flex flex-wrap items-center gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <TierChip
                active={tierFilter === "all"}
                onClick={() => setTierFilter("all")}
                label={`All · ${counts.all}`}
              />
              {TIERS.map((t) => (
                <TierChip
                  key={t}
                  active={tierFilter === t}
                  onClick={() => setTierFilter(t)}
                  label={`${TIER_META[t].label} · ${counts[t] ?? 0}`}
                  dotClass={TIER_META[t].dot}
                />
              ))}
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                <option value="all">All sources</option>
                {sources.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search title, company, location…"
                className="w-64 rounded-lg border border-border bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </section>

          {/* Listings */}
          <section className="space-y-3">
            {filtered.length === 0 && (
              <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
                No listings match your filters.
              </div>
            )}
            {filtered.map((l, i) => (
              <ListingCard key={`${l.apply_url}-${i}`} l={l} />
            ))}
          </section>

          <footer className="mt-12 border-t border-border pt-6 text-xs text-muted-foreground">
            Scoring engine: title match (+3), Belgium (+2), Dutch/French required (+2), each
            skill match (+1, max 4), remote/hybrid (+1), junior penalty (-3), outside Belgium
            & not remote (-2). Tiers: Strong ≥ 7, Consider ≥ 4.
          </footer>
        </main>
      </div>
    </div>
  );
}

function TierChip({
  active,
  onClick,
  label,
  dotClass,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  dotClass?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-card text-foreground hover:border-foreground/40"
      }`}
    >
      {dotClass && <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />}
      {label}
    </button>
  );
}

function ListingCard({ l }: { l: Listing }) {
  const tier = (TIERS.includes(l.tier as Tier) ? l.tier : "low") as Tier;
  const meta = TIER_META[tier];
  return (
    <article className="group rounded-xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider ${meta.pill}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
              {meta.label}
            </span>
            <span className="text-xs text-muted-foreground">
              score <span className="font-semibold text-foreground">{l.score}</span>
            </span>
            <span className="text-xs text-muted-foreground">· {l.source_site}</span>
            {l.experience_level && l.experience_level !== "unknown" && (
              <span className="text-xs text-muted-foreground">· {l.experience_level}</span>
            )}
            {l.remote && l.remote !== "unknown" && (
              <span className="text-xs text-muted-foreground">· {l.remote}</span>
            )}
          </div>
          <h3 className="font-display mt-2 text-lg font-semibold leading-snug">
            {l.title}
          </h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{l.company}</span>
            {l.location && <span> · {l.location}</span>}
          </p>
          {l.description_summary && (
            <p className="mt-3 line-clamp-3 text-sm text-foreground/80">
              {l.description_summary}
            </p>
          )}
          {(l.skills.length > 0 || l.languages.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {l.languages.map((lang) => (
                <span
                  key={`lang-${lang}`}
                  className="rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px]"
                >
                  {lang}
                </span>
              ))}
              {l.skills.slice(0, 6).map((s) => (
                <span
                  key={`skill-${s}`}
                  className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {s}
                </span>
              ))}
              {l.skills.length > 6 && (
                <span className="text-[11px] text-muted-foreground">
                  +{l.skills.length - 6} more
                </span>
              )}
            </div>
          )}
          {l.flags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
              {l.flags.map((f, i) => (
                <span key={i}>{f}</span>
              ))}
            </div>
          )}
        </div>
        <a
          href={l.apply_url}
          target="_blank"
          rel="noreferrer noopener"
          className="shrink-0 rounded-lg bg-foreground px-4 py-2 text-sm font-semibold text-background transition hover:bg-foreground/85"
        >
          Apply ↗
        </a>
      </div>
    </article>
  );
}
