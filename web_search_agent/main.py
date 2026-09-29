
"""
Web Search Research Agent CLI.
Run interactively:
    python main.py
Or with arguments:
    python main.py --query "Quantum Computing breakthroughs 2026" --output report.md
"""

import sys
import io
import os
import argparse
from typing import Optional

# Ensure UTF-8 output on Windows consoles to prevent charmap encoding errors
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
    console = Console(force_terminal=True, legacy_windows=False)
except ImportError:
    RICH_AVAILABLE = False
    console = None

from agent import ResearchAgent


def print_banner():
    title = "Web Search & Deep Research Agent"
    subtitle = "Autonomous Web Researcher • Extracts & Synthesizes Reports into Files"
    if RICH_AVAILABLE and console is not None:
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]\n[dim]{subtitle}[/dim]", border_style="blue"))
    else:
        print("=" * 60)
        print(f" {title} ")
        print(f" {subtitle} ")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Web Search & Research Agent that synthesizes findings into a file."
    )
    parser.add_argument(
        "-q", "--query", "--topic",
        dest="topic",
        type=str,
        help="The topic or question you want the agent to research."
    )
    parser.add_argument(
        "-o", "--output",
        dest="output_file",
        type=str,
        default=None,
        help="Optional custom output file path (e.g. my_research.md)."
    )
    parser.add_argument(
        "-n", "--max-sources",
        dest="max_sources",
        type=int,
        default=6,
        help="Maximum search results to collect (default: 6)."
    )
    parser.add_argument(
        "--scrape-top",
        dest="scrape_top",
        type=int,
        default=3,
        help="Number of top webpages to read deeply (default: 3)."
    )

    args = parser.parse_args()

    print_banner()

    topic = args.topic
    if not topic:
        prompt_text = "\n[?] Enter what you want to research: "
        if RICH_AVAILABLE and console is not None:
            topic = console.input(f"[bold yellow]{prompt_text}[/bold yellow]").strip()
        else:
            topic = input(prompt_text).strip()

    if not topic:
        print("[!] No research topic provided. Exiting.")
        sys.exit(0)

    agent = ResearchAgent(output_dir="reports")

    if RICH_AVAILABLE and console is not None:
        console.print(f"\n[bold green][*] Initiating deep research on:[/bold green] [italic]'{topic}'[/italic]\n")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Starting research pipeline...", total=None)

            def update_progress(step: int, msg: str):
                progress.update(task, description=f"[cyan][{step}/4][/cyan] [white]{msg}[/white]")

            result = agent.run(
                topic=topic,
                output_file=args.output_file,
                max_search_results=args.max_sources,
                scrape_top_n=args.scrape_top,
                callback=update_progress
            )
    else:
        print(f"\n[*] Initiating deep research on: '{topic}'\n")
        result = agent.run(
            topic=topic,
            output_file=args.output_file,
            max_search_results=args.max_sources,
            scrape_top_n=args.scrape_top
        )

    saved_path = result["file_path"]

    if RICH_AVAILABLE and console is not None:
        console.print(f"\n[bold green][+] Research Completed Successfully![/bold green]")
        console.print(f"[bold]Saved in file:[/bold] [underline cyan]{saved_path}[/underline cyan]")
        console.print(f"[dim]Sources analyzed: {result['sources_count']} | Deeply scraped: {result['scraped_count']}[/dim]\n")
        
        # Display preview panel
        preview_text = result["report"][:1400]
        if len(result["report"]) > 1400:
            preview_text += "\n\n*(Full report saved to file)*"

        console.print(Panel(
            Markdown(preview_text),
            title="Research Report Preview",
            border_style="green"
        ))
    else:
        print("\n" + "=" * 60)
        print("[+] Research Completed Successfully!")
        print(f"Saved in file: {saved_path}")
        print(f"Sources analyzed: {result['sources_count']} | Deeply scraped: {result['scraped_count']}")
        print("=" * 60)
        print("\n--- REPORT PREVIEW ---\n")
        print(result["report"][:800] + ("\n\n... (Full report saved to file)" if len(result["report"]) > 800 else ""))
        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
