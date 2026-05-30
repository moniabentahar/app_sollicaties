import { useState } from "react"
import { Copy, Check, Loader2 } from "lucide-react"

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
  loading: boolean
  onLetterChange: (value: string) => void
}

export function CoverLetterDialog({
  open,
  onOpenChange,
  job,
  letter,
  loading,
  onLetterChange,
}: CoverLetterDialogProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(letter)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // Clipboard kan geweigerd worden; stil falen is hier acceptabel.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">Sollicitatiebrief</DialogTitle>
          <DialogDescription>
            {job ? (
              <>
                Voorgesteld voor <span className="font-semibold">{job.title}</span> bij{" "}
                <span className="font-semibold">{job.company}</span>. Pas de tekst gerust aan.
              </>
            ) : (
              "Genereer een brief vanuit een vacature."
            )}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex h-64 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Brief genereren…
          </div>
        ) : (
          <textarea
            value={letter}
            onChange={(e) => onLetterChange(e.target.value)}
            spellCheck={false}
            className="h-[55vh] w-full resize-none rounded-lg border border-input bg-card p-4 font-sans text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Sluiten
          </Button>
          <Button onClick={handleCopy} disabled={loading || !letter}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Gekopieerd" : "Kopiëren"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
