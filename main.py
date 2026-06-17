"""Sollicitaties2026 — CLI entry point."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from src.filters import filter_and_score
from src.output import print_summary, write_csv
from src.profile import (
    CANDIDATE_LOCATION,
    CANDIDATE_NAME,
    CORE_SKILLS,
    LANGUAGES,
    TARGET_TITLES,
)
from src.scraper import ALL_CATEGORIES, SITE_URLS, scrape_sites

app = typer.Typer(
    name="sollicitaties",
    help="Find jobs matching the uploaded CV's profile (Scrapling + Claude extraction).",
    no_args_is_help=True,
)
console = Console()

_ENV_CANDIDATES = [Path("config/.env"), Path(".env")]


def _load_api_key() -> str:
    for p in _ENV_CANDIDATES:
        if p.exists():
            load_dotenv(p)
            break
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        console.print(
            "[red]ANTHROPIC_API_KEY not found.[/red]\n"
            "Scrapling fetches the pages locally; Claude extracts the listings.\n"
            "Add your key to [bold]config/.env[/bold] as:\n"
            "  ANTHROPIC_API_KEY=sk-ant-..."
        )
        raise typer.Exit(1)
    return key


@app.command()
def run(
    site: Optional[str] = typer.Option(
        None, "--site", "-s",
        help=f"Scrape one site only. Choices: {', '.join(SITE_URLS)}",
    ),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help=f"Scrape a category of sites. Choices: {', '.join(ALL_CATEGORIES)}",
    ),
    output_dir: Path = typer.Option(
        Path("docs/vacatures"), "--output", "-o",
        help="Directory where the CSV is written.",
    ),
    min_score: int = typer.Option(
        1, "--min-score",
        help="Hide listings below this score in the CLI table (still in CSV).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Print each URL scraped."),
    csv_only: bool = typer.Option(False, "--csv-only", help="Skip CLI table; only write CSV."),
    browser: bool = typer.Option(
        False, "--browser",
        help="Use the Scrapling stealth browser (JS/anti-bot sites). Needs `scrapling install`.",
    ),
):
    """Scrape job sites and rank listings against the uploaded CV's profile."""
    api_key = _load_api_key()

    # Resolve which sites to scan: --site > --category > all
    if site:
        sites = [site]
    elif category:
        cat_sites = ALL_CATEGORIES.get(category)
        if not cat_sites:
            console.print(
                f"[red]Unknown category '{category}'.[/red]\n"
                f"Valid: {', '.join(ALL_CATEGORIES)}"
            )
            raise typer.Exit(1)
        sites = cat_sites
    else:
        sites = None

    console.print(f"\n[bold cyan]Sollicitaties2026[/bold cyan] — starting scan")
    if category:
        console.print(f"Category: [magenta]{category}[/magenta]")
    if sites:
        console.print(f"Sites  : [yellow]{', '.join(sites)}[/yellow]")
    else:
        console.print(f"Sites  : [yellow]{', '.join(SITE_URLS)}[/yellow]  (all)")

    listings = scrape_sites(api_key, sites=sites, verbose=verbose, use_browser=browser)
    console.print(f"\nUnique listings found: [cyan]{len(listings)}[/cyan]")

    scored = filter_and_score(listings)
    visible = [s for s in scored if s.score >= min_score]

    if not csv_only:
        print_summary(visible, total_scraped=len(listings))

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    site_tag = f"_{site}" if site else "_all"
    csv_path = output_dir / f"scan{site_tag}_{stamp}.csv"
    write_csv(scored, csv_path)   # always write full unfiltered set to CSV


@app.command()
def show_profile():
    """Display the candidate profile used for matching."""
    console.print(f"\n[bold cyan]Candidate:[/bold cyan] {CANDIDATE_NAME}")
    console.print(f"[bold]Location :[/bold] {CANDIDATE_LOCATION}")
    console.print(f"[bold]Languages:[/bold] {', '.join(sorted(LANGUAGES))}\n")

    console.print("[bold]Target titles:[/bold]")
    for t in sorted(TARGET_TITLES):
        console.print(f"  • {t}")

    console.print("\n[bold]Core skills:[/bold]")
    for s in sorted(CORE_SKILLS):
        console.print(f"  • {s}")


@app.command()
def list_sites():
    """List all supported job sites and how many search URLs each has."""
    console.print("\n[bold]Categories:[/bold]")
    for cat_name, cat_sites in ALL_CATEGORIES.items():
        console.print(f"  [magenta]{cat_name:<14}[/magenta] {', '.join(cat_sites)}")

    console.print("\n[bold]All sites:[/bold]")
    for name, urls in SITE_URLS.items():
        console.print(f"  [cyan]{name:<22}[/cyan] {len(urls)} search URL(s)")


if __name__ == "__main__":
    app()
