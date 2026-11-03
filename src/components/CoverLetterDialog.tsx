import { useState } from "react"
import { Copy, Check, Loader2, ExternalLink, Link as LinkIcon, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { Listing } from "@/lib/api"

interface CoverLetterDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  job: Listing | null
  letter: string
  cv: string
  loading: boolean
  onLetterChange: (value: string) => void
  onCvChange: (value: string) => void
  /** Rewrites the CV from the user's remarks; resolves with the new CV text. */
  onReviseCv?: (remarks: string) => Promise<string>
  onConfirm?: () => Promise<void>
  readOnly?: boolean
}

type Tab = "letter" | "cv"

export function CoverLetterDialog({
  open,
  onOpenChange,
  job,
  letter,
  cv,
  loading,
  onLetterChange,
  onCvChange,
  onReviseCv,
  onConfirm,
  readOnly = false,
}: CoverLetterDialogProps) {
  const [tab, setTab] = useState<Tab>("letter")
  const [copied, setCopied] = useState<"" | "doc" | "url">("")
  const [remarks, setRemarks] = useState("")
  const [isRevising, setIsRevising] = useState(false)

  const text = tab === "letter" ? letter : cv
  const applyUrl = job?.apply_url ?? ""

  async function copy(value: string, what: "doc" | "url") {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(what)
      setTimeout(() => setCopied(""), 1800)
    } catch {
      /* clipboard kan geweigerd worden; stil falen is acceptabel */
    }
  }

  async function handleReviseCv() {
    if (!onReviseCv || !remarks.trim()) return
    setIsRevising(true)
    try {
      onCvChange(await onReviseCv(remarks.trim()))
      setRemarks("")
      toast.success("CV aangepast", { description: "Lees het na; je kan het nog altijd zelf bewerken." })
    } catch (err) {
      toast.error("Kon het CV niet aanpassen.", {
        description: err instanceof Error ? err.message : undefined,
      })
    } finally {
      setIsRevising(false)
    }
  }

  const showRemarks = tab === "cv" && !readOnly && !loading && Boolean(onReviseCv) && Boolean(cv)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">Solliciteren — brief & CV</DialogTitle>
          <DialogDescription>
            {job ? (
              <>
                Voor <span className="font-semibold">{job.title}</span> bij{" "}
                <span className="font-semibold">{job.company}</span>. Lees na, pas aan en kopieer.
              </>
            ) : (
              "Genereer een brief en CV vanuit een vacature."
            )}
          </DialogDescription>
        </DialogHeader>

        {/* Sollicitatielink — ook kopieerbaar, voor als de site geblokkeerd is */}
        {applyUrl && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/40 p-2">
            <a
              href={applyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background"
            >
              <ExternalLink className="h-3.5 w-3.5" /> Open vacature
            </a>
            <button
              type="button"
              onClick={() => copy(applyUrl, "url")}
              className="inline-flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 text-xs font-medium"
            >
              {copied === "url" ? <Check className="h-3.5 w-3.5" /> : <LinkIcon className="h-3.5 w-3.5" />}
              {copied === "url" ? "Link gekopieerd" : "Kopieer link"}
            </button>
            <span className="truncate text-[11px] text-muted-foreground">{applyUrl}</span>
          </div>
        )}

        {/* Tabs: brief / cv */}
        <div className="flex gap-1 rounded-lg bg-muted p-1">
          {(["letter", "cv"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-semibold transition ${
                tab === t ? "bg-card shadow-sm" : "text-muted-foreground"
              }`}
            >
              {t === "letter" ? "Motivatiebrief" : "CV"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Brief & CV genereren…
          </div>
        ) : readOnly ? (
          <pre className="h-[48vh] w-full overflow-auto whitespace-pre-wrap rounded-lg border border-input bg-muted/30 p-4 font-sans text-sm leading-relaxed">
            {text}
          </pre>
        ) : (
          <textarea
            value={text}
            onChange={(e) => (tab === "letter" ? onLetterChange(e.target.value) : onCvChange(e.target.value))}
            spellCheck={false}
            disabled={isRevising}
            className={`${showRemarks ? "h-[38vh]" : "h-[48vh]"} w-full resize-none rounded-lg border border-input bg-card p-4 font-sans text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring/40 disabled:opacity-60`}
          />
        )}

        {/* Opmerkingen: laat het CV herschrijven (blijft in het Engels) */}
        {showRemarks && (
          <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
            <label htmlFor="cv-remarks" className="text-xs font-semibold">
              Opmerkingen voor het CV
            </label>
            <textarea
              id="cv-remarks"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              maxLength={2000}
              rows={2}
              disabled={isRevising}
              placeholder="Bv. maak het profiel korter, zet sponsoring meer op de voorgrond, laat de oudste functies weg…"
              className="w-full resize-y rounded-md border border-input bg-card p-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[11px] text-muted-foreground">
                Het CV blijft volledig in het Engels. Je kan het daarna nog zelf bewerken.
              </span>
              <Button size="sm" onClick={handleReviseCv} disabled={isRevising || !remarks.trim()}>
                {isRevising ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {isRevising ? "CV aanpassen…" : "Pas CV aan"}
              </Button>
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Sluiten
          </Button>
          <Button onClick={() => copy(text, "doc")} disabled={loading || !text}>
            {copied === "doc" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied === "doc" ? "Gekopieerd" : `Kopieer ${tab === "letter" ? "brief" : "CV"}`}
          </Button>
          {onConfirm && !readOnly && (
            <Button onClick={onConfirm} disabled={loading}>
              <ExternalLink className="h-4 w-4" /> Bevestig & open vacature
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
