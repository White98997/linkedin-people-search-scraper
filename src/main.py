from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterable, List, Optional

import requests
import typer
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table

from extractors.linkedin_parser import (
    LinkedInProfile,
    parse_people_from_html,
)
from extractors.pagination_handler import (
    ensure_page_param,
    next_page_url,
)
from utils.cookie_manager import (
    cookie_header_from_cookie_editor_json,
    cookie_jar_from_cookie_string,
)
from utils.delay_randomizer import random_delay_ms

app = typer.Typer(add_completion=False, help="LinkedIn People Search Scraper")
console = Console()

class Settings(BaseModel):
    search_url: Optional[str] = Field(
        default=None,
        description="Full LinkedIn people search URL copied from the browser.",
    )
    cookie_mode: str = Field(
        default="string",
        description="One of: 'json' (Cookie-Editor export JSON) or 'string' (raw Cookie header).",
    )
    cookies_json_path: Optional[str] = Field(
        default=None, description="Path to Cookie-Editor JSON export."
    )
    cookie_string: Optional[str] = Field(
        default=None, description="Raw Cookie header string: 'name=value; name2=value2'"
    )
    min_delay_ms: int = Field(default=800, ge=0)
    max_delay_ms: int = Field(default=1800, ge=0)
    max_pages: int = Field(default=3, ge=1)
    output_path: str = Field(default="data/sample_output.json")

def load_settings(config_path: Optional[Path]) -> Settings:
    """
    Loads settings from a JSON file if provided; otherwise returns defaults.
    """
    if config_path and config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            return Settings(**cfg)
        except (json.JSONDecodeError, ValidationError) as e:
            raise SystemExit(f"[config] Invalid settings file: {e}")
    # Fallback to defaults if no config path
    return Settings()

def resolve_search_url(
    cli_url: Optional[str], settings: Settings, inputs_file: Path
) -> str:
    if cli_url:
        return cli_url
    if settings.search_url:
        return settings.search_url
    if inputs_file.exists():
        first_line = inputs_file.read_text(encoding="utf-8").strip().splitlines()
        if first_line:
            return first_line[0].strip()
    raise SystemExit(
        "No search URL provided. Use --search-url or add one to data/inputs.sample.txt"
    )

def resolve_cookies(
    cookie_mode: Optional[str],
    json_path: Optional[str],
    cookie_string: Optional[str],
) -> requests.cookies.RequestsCookieJar | dict:
    mode = (cookie_mode or "string").lower()
    if mode not in {"json", "string"}:
        raise SystemExit("--cookie-mode must be 'json' or 'string'")

    if mode == "json":
        if not json_path:
            raise SystemExit(
                "Cookie mode 'json' selected but --cookies-file not provided."
            )
        p = Path(json_path)
        if not p.exists():
            raise SystemExit(f"Cookies file not found: {p}")
        try:
            cookies_json = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid Cookie-Editor JSON: {e}")
        # Return header string for requests (more reliable across domains)
        cookie_header = cookie_header_from_cookie_editor_json(cookies_json)
        return {"Cookie": cookie_header}
    else:
        # raw string mode
        if not cookie_string:
            raise SystemExit("Cookie mode 'string' selected but --cookie-string missing.")
        return cookie_jar_from_cookie_string(cookie_string)

def fetch_html(
    session: requests.Session,
    url: str,
    cookie_payload: requests.cookies.RequestsCookieJar | dict,
    timeout: int = 30,
) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if isinstance(cookie_payload, dict):
        headers.update(cookie_payload)
        resp = session.get(url, headers=headers, timeout=timeout)
    else:
        resp = session.get(url, headers=headers, cookies=cookie_payload, timeout=timeout)

    if resp.status_code == 429:
        raise SystemExit("Received HTTP 429 (Too Many Requests). Try increasing delays.")
    if resp.status_code in (401, 403):
        console.print(
            "[yellow]Auth blocked (401/403). Ensure your cookies are valid and the URL is accessible.[/yellow]"
        )
    resp.raise_for_status()
    return resp.text

def write_output(records: Iterable[LinkedInProfile], output_path: Path) -> None:
    data = [r.model_dump() for r in records]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@app.command()
def run(
    search_url: Optional[str] = typer.Option(
        None,
        "--search-url",
        "-u",
        help="LinkedIn people search URL copied from the address bar.",
    ),
    cookies_file: Optional[Path] = typer.Option(
        None,
        "--cookies-file",
        "-c",
        help="Path to Cookie-Editor JSON export (use with --cookie-mode json).",
    ),
    cookie_string: Optional[str] = typer.Option(
        None,
        "--cookie-string",
        "-k",
        help="Raw Cookie header string (use with --cookie-mode string).",
    ),
    cookie_mode: str = typer.Option(
        "string",
        "--cookie-mode",
        "-m",
        help="Cookie mode: 'json' or 'string'.",
    ),
    max_pages: int = typer.Option(3, "--max-pages", "-p", min=1, help="Max pages to scrape."),
    min_delay_ms: int = typer.Option(800, "--min-delay-ms", min=0),
    max_delay_ms: int = typer.Option(1800, "--max-delay-ms", min=0),
    output: Path = typer.Option(Path("data/sample_output.json"), "--output", "-o"),
    config: Optional[Path] = typer.Option(
        None, "--config", "-f", help="Optional path to settings JSON."
    ),
):
    """
    Run the LinkedIn people search scraper using authenticated session cookies.
    """
    settings = load_settings(config)
    # Merge CLI over settings
    use_url = resolve_search_url(
        search_url or settings.search_url, settings, Path("data/inputs.sample.txt")
    )
    use_max_pages = max_pages or settings.max_pages
    use_min_delay = min_delay_ms if min_delay_ms is not None else settings.min_delay_ms
    use_max_delay = max_delay_ms if max_delay_ms is not None else settings.max_delay_ms

    # Resolve cookies
    cookie_payload = resolve_cookies(
        cookie_mode or settings.cookie_mode,  # type: ignore[arg-type]
        str(cookies_file) if cookies_file else settings.cookies_json_path,
        cookie_string or settings.cookie_string,
    )

    # Ensure URL has a page param
    url = ensure_page_param(use_url, page=1)

    session = requests.Session()
    all_profiles: List[LinkedInProfile] = []

    console.rule("[bold]LinkedIn People Search Scraper")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Page", style="dim", width=6)
    table.add_column("Found Profiles", width=16)
    table.add_column("URL", overflow="fold")

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Scraping pages…", total=use_max_pages)
        for page in range(1, use_max_pages + 1):
            progress.update(task, description=f"Fetching page {page}…")
            try:
                html = fetch_html(session, url, cookie_payload)
            except requests.HTTPError as e:
                console.print(f"[red]HTTP error on {url}[/red]: {e}")
                break
            except requests.RequestException as e:
                console.print(f"[red]Network error on {url}[/red]: {e}")
                break

            profiles = parse_people_from_html(html, base_url=url)
            all_profiles.extend(profiles)
            table.add_row(str(page), str(len(profiles)), url)

            # Compute next URL; stop if unchanged or None
            nxt = next_page_url(url, page + 1)
            if not nxt or nxt == url:
                break
            url = nxt

            # Delay between pages
            d_ms = random_delay_ms(use_min_delay, use_max_delay)
            progress.update(task, advance=1)
            time.sleep(d_ms / 1000.0)

        progress.update(task, completed=use_max_pages)

    console.print(table)
    write_output(all_profiles, output)
    console.print(
        f"[green]Done.[/green] Saved [bold]{len(all_profiles)}[/bold] profiles to [cyan]{output}[/cyan]"
    )

if __name__ == "__main__":
    # Allow `python src/main.py run ...`
    app()