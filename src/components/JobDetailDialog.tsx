import { ExternalLink, FileText, Check, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { postedAgo, tierColor, tierLabel, type Listing } from "@/lib/api"

interface JobDetailDialogProps {
  job: Listing | null
  open: boolean
  onOpenChange: (open: boolean) => void
  applied: boolean
  onGenerateLetter: (job: Listing) => void
  onToggleApplied: (job: Listing) => void
}

function Chips({ items, className }: { items: string[]; className: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={className}>
          {item}
        </span>
      ))}
    </div>
  )
}

export function JobDetailDialog({
  job,
  open,
  onOpenChange,
  applied,
  onGenerateLetter,
  onToggleApplied,
}: JobDetailDialogProps) {
  if (!job) return null
  const color = tierColor(job.tier)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-start gap-3 pr-6">
            <div
              className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl text-white"
              style={{ background: color }}
            >
              <span className="font-display text-lg font-bold leading-none tabular-nums">
                {job.score}
              </span>
              <span className="text-[9px] uppercase tracking-wide opacity-80">score</span>
            </div>
            <div className="min-w-0">
              <DialogTitle className="font-display text-lg leading-tight">{job.title}</DialogTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{job.company}</span>
                {" · "}
                {job.location || "—"}
                {job.remote && job.remote !== "unknown" ? ` · ${job.remote}` : ""}
              </p>
              <span
                className="mt-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                style={{ background: `color-mix(in oklab, ${color} 12%, transparent)`, color }}
              >
                {tierLabel(job.tier)}
              </span>
            </div>
          </div>
        </DialogHeader>

        <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
          {/* Meta grid: source, posted date, experience level */}
          {(job.source_site || postedAgo(job.posted_date) || (job.experience_level && job.experience_level !== "unknown")) && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-muted/50 px-3 py-2.5 text-sm">
              {job.source_site && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Bron</p>
                  <p className="font-medium">{job.source_site}</p>
                </div>
              )}
              {postedAgo(job.posted_date) && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Online sinds</p>
                  <p className="font-medium">{postedAgo(job.posted_date)}</p>
                </div>
              )}
              {job.experience_level && job.experience_level !== "unknown" && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Niveau</p>
                  <p className="font-medium">{job.experience_level}</p>
                </div>
              )}
            </div>
          )}

          {job.description_summary && (
            <p className="text-sm leading-relaxed text-muted-foreground">{job.description_summary}</p>
          )}

          {job.flags && job.flags.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Aandachtspunten
              </p>
              <Chips
                items={job.flags}
                className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              />
            </div>
          )}

          {job.skills && job.skills.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Skills
              </p>
              <Chips
                items={job.skills}
                className="rounded-md border border-accent/25 bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent"
              />
            </div>
          )}

          {job.languages && job.languages.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Talen
              </p>
              <Chips
                items={job.languages}
                className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              />
            </div>
          )}
        </div>

        <Separator />

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => onGenerateLetter(job)}>
            <FileText className="h-4 w-4" /> Genereer sollicitatiebrief
          </Button>
          <Button
            variant={applied ? "destructive" : "outline"}
            onClick={() => onToggleApplied(job)}
          >
            {applied ? <Trash2 className="h-4 w-4" /> : <Check className="h-4 w-4" />}
            {applied ? "Uit gesolliciteerd halen" : "Markeer als gesolliciteerd"}
          </Button>
          {job.apply_url && (
            <Button variant="ghost" asChild className="ml-auto">
              <a href={job.apply_url} target="_blank" rel="noopener noreferrer">
                Solliciteer <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
