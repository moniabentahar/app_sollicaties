import { useState } from "react"
import { Copy, Check, Loader2, ExternalLink, Link as LinkIcon } from "lucide-react"

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
  onConfirm,
  readOnly = false,
}: CoverLetterDialogProps) {
  const [tab, setTab] = useState<Tab>("letter")
  const [copied, setCopied] = useState<"" | "doc" | "url">("")

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
            className="h-[48vh] w-full resize-none rounded-lg border border-input bg-card p-4 font-sans text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
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
