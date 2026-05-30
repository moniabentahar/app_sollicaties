"""Rich CLI table and CSV export for scored job listings."""

import csv
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from src.models import ScoredListing

# Reconfigure stdout to use UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
console = Console()

_TIER_COLOR = {"strong": "green", "consider": "yellow", "low": "dim white"}
_TIER_LABEL = {
    "strong": "Strong Match  (score ≥ 7)",
    "consider": "Consider      (score 4–6)",
    "low": "Low           (score ≤ 3)",
}


def print_summary(scored: list[ScoredListing], total_scraped: int) -> None:
    console.rule("[bold cyan]Sollicitaties2026 — Scan Results[/bold cyan]")
    console.print(
        f"Scraped: [cyan]{total_scraped}[/cyan]  |  "
        f"After dedup + scoring: [cyan]{len(scored)}[/cyan]\n"
    )

    for tier_key in ("strong", "consider", "low"):
        tier_items = [s for s in scored if s.tier == tier_key]
        if not tier_items:
            continue

        color = _TIER_COLOR[tier_key]
        label = _TIER_LABEL[tier_key]

        table = Table(
            title=f"[{color}]{label}[/{color}]",
            box=box.SIMPLE_HEAVY,
            show_lines=False,
            expand=True,
            title_justify="left",
        )
        table.add_column("Score", style=color, width=6, justify="right")
        table.add_column("Title", style="bold white", min_width=28)
        table.add_column("Company", min_width=20)
        table.add_column("Location", min_width=18)
        table.add_column("Remote", width=9)
        table.add_column("Site", width=10)
        table.add_column("Flags")

        for s in tier_items:
            table.add_row(
                str(s.score),
                s.listing.title,
                s.listing.company,
                s.listing.location,
                s.listing.remote,
                s.listing.source_site,
                "  ".join(s.flags),
            )

        console.print(table)
        console.print()


def write_csv(scored: list[ScoredListing], path: Path) -> None:
    if not scored:
        console.print("[yellow]No results — CSV not written.[/yellow]")
        return

    fieldnames = list(scored[0].as_dict().keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for s in scored:
            writer.writerow(s.as_dict())

    console.print(f"[green]CSV saved →[/green] {path}  ({len(scored)} rows)")
