"""CLI interface using Typer."""

import json
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .config import settings
from .converter import parse_report, to_slack_payload, to_slack_payload_interactive
from .reader import get_latest_report_date, list_available_reports, read_daily_report
from .sender import SlackSendError, send_to_slack_sync
from .storage import vote_store

app = typer.Typer(
    name="toslack",
    help="Paper Digest Slack Notifier - Send daily paper reports to Slack",
    no_args_is_help=True,
)
console = Console()


@app.command()
def send(
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Report date (YYYY-MM-DD). Defaults to latest."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the Slack message without sending."
    ),
    webhook_url: Optional[str] = typer.Option(
        None, "--webhook-url", "-w", help="Override Slack webhook URL."
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Include voting buttons (requires server running)."
    ),
) -> None:
    """Send a daily paper report to Slack.

    If no date is specified, sends the most recent report.
    Use --interactive to include Keep/Drop voting buttons.
    """
    try:
        # Determine date
        if date is None:
            date = get_latest_report_date()
            rprint(f"[dim]Using latest report: {date}[/dim]")

        # Read and parse report
        rprint(f"[blue]Reading report for {date}...[/blue]")
        content = read_daily_report(date)
        papers, skim_papers = parse_report(content)

        if not papers:
            rprint("[yellow]No papers found in the report.[/yellow]")
            raise typer.Exit(1)

        rprint(f"[green]Found {len(papers)} paper(s)[/green]")
        if skim_papers:
            rprint(f"[green]+ {len(skim_papers)} skim-only paper(s)[/green]")

        # Create Slack payload
        if interactive:
            # Get existing vote counts if any
            vote_counts = {}
            for paper in papers:
                votes = vote_store.get_paper_votes(date, paper.arxiv_id)
                vote_counts[paper.arxiv_id] = {
                    "applicable_count": votes["applicable_count"],
                    "idea_count": votes["idea_count"],
                    "pass_count": votes["pass_count"],
                }
            payload = to_slack_payload_interactive(papers, date, vote_counts)
            rprint("[cyan]Interactive mode: voting buttons included[/cyan]")
        else:
            payload = to_slack_payload(papers, date, skim_papers)

        if dry_run:
            # Preview mode
            rprint("\n[bold cyan]Preview (Slack Block Kit JSON):[/bold cyan]")
            json_str = json.dumps(payload, ensure_ascii=False, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
            console.print(syntax)

            # Also show paper summaries
            rprint("\n[bold cyan]Paper Summaries:[/bold cyan]")
            for i, paper in enumerate(papers, 1):
                rprint(Panel(
                    f"[bold]{paper.title}[/bold]\n"
                    f"{paper.star_emoji} | 총점: {paper.score}/{paper.max_score}\n"
                    f"arXiv: {paper.arxiv_id}\n"
                    f"📝 {paper.summary}\n"
                    f"✅ {paper.when_to_use}\n"
                    f"❌ {paper.when_not_to_use}",
                    title=f"Paper {i}",
                    border_style="blue",
                ))
        else:
            # Send to Slack
            url = webhook_url or settings.slack_webhook_url
            if not url:
                rprint("[red]Error: SLACK_WEBHOOK_URL is not configured.[/red]")
                rprint("[dim]Set it via environment variable or --webhook-url option.[/dim]")
                raise typer.Exit(1)

            rprint("[blue]Sending to Slack...[/blue]")
            send_to_slack_sync(payload, webhook_url)
            rprint("[green]Successfully sent to Slack![/green]")

            if interactive:
                rprint("\n[yellow]Note: Make sure the vote server is running to handle button clicks.[/yellow]")
                rprint(f"[dim]Run: toslack server[/dim]")

    except FileNotFoundError as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except SlackSendError as e:
        rprint(f"[red]Slack error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def preview(
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Report date (YYYY-MM-DD). Defaults to latest."
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Preview with voting buttons."
    ),
) -> None:
    """Preview parsed papers without sending (alias for send --dry-run)."""
    send(date=date, dry_run=True, webhook_url=None, interactive=interactive)


@app.command(name="list")
def list_reports() -> None:
    """List all available report dates."""
    reports = list_available_reports()

    if not reports:
        rprint("[yellow]No reports found.[/yellow]")
        rprint(f"[dim]Reports directory: {settings.daily_reports_dir}[/dim]")
        raise typer.Exit(1)

    rprint(f"[bold]Available reports ({len(reports)}):[/bold]")
    for report_date in reports:
        rprint(f"  {report_date}")


@app.command()
def config() -> None:
    """Show current configuration."""
    rprint("[bold]Current Configuration:[/bold]")
    rprint(f"  SLACK_WEBHOOK_URL: {'[green]configured[/green]' if settings.slack_webhook_url else '[red]not set[/red]'}")
    rprint(f"  SLACK_SIGNING_SECRET: {'[green]configured[/green]' if settings.slack_signing_secret else '[yellow]not set (dev mode)[/yellow]'}")
    rprint(f"  SLACK_BOT_TOKEN: {'[green]configured[/green]' if settings.slack_bot_token else '[yellow]not set[/yellow]'}")
    rprint(f"  REPORT_BASE_DIR: {settings.report_base_dir}")
    rprint(f"  Daily reports dir: {settings.daily_reports_dir}")
    rprint(f"  Directory exists: {'[green]yes[/green]' if settings.daily_reports_dir.exists() else '[red]no[/red]'}")
    rprint(f"  Server: {settings.server_host}:{settings.server_port}")


@app.command()
def server(
    host: Optional[str] = typer.Option(
        None, "--host", "-h", help="Server host (default: 0.0.0.0)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Server port (default: 8000)"
    ),
) -> None:
    """Start the vote callback server.

    This server handles Slack button clicks and updates vote counts.
    Use ngrok to expose it externally for Slack webhooks.
    """
    import uvicorn

    server_host = host or settings.server_host
    server_port = port or settings.server_port

    rprint(f"[bold green]Starting vote server on {server_host}:{server_port}[/bold green]")
    rprint("\n[yellow]Setup instructions:[/yellow]")
    rprint("1. Run ngrok: [cyan]ngrok http {port}[/cyan]".format(port=server_port))
    rprint("2. Copy the ngrok URL (e.g., https://xxxx.ngrok.io)")
    rprint("3. In Slack App settings, set Interactivity Request URL to:")
    rprint("   [cyan]https://xxxx.ngrok.io/slack/interactions[/cyan]")
    rprint("\n[dim]Endpoints:[/dim]")
    rprint(f"  POST /slack/interactions - Slack callback endpoint")
    rprint(f"  GET  /health - Health check")
    rprint(f"  GET  /votes/{{date}} - Get vote status for a date")
    rprint(f"  GET  /kept - Get all kept papers")
    rprint(f"  GET  /dropped - Get all dropped papers")
    rprint("")

    uvicorn.run(
        "toslack.server:app",
        host=server_host,
        port=server_port,
        reload=True,
    )


@app.command()
def votes(
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Report date (YYYY-MM-DD). Defaults to latest."
    ),
) -> None:
    """Show voting results for a report."""
    try:
        if date is None:
            date = get_latest_report_date()
            rprint(f"[dim]Using latest report: {date}[/dim]")

        content = read_daily_report(date)
        papers, _ = parse_report(content)

        table = Table(title=f"Vote Results - {date}")
        table.add_column("Paper", style="cyan", no_wrap=False)
        table.add_column("Keep", justify="center", style="green")
        table.add_column("Drop", justify="center", style="red")
        table.add_column("Status", justify="center")

        for paper in papers:
            votes = vote_store.get_paper_votes(date, paper.arxiv_id)
            keep = votes["keep_count"]
            drop = votes["drop_count"]

            if keep > drop:
                status = "[green]✅ KEEP[/green]"
            elif drop > keep:
                status = "[red]❌ DROP[/red]"
            else:
                status = "[yellow]⏳ PENDING[/yellow]"

            table.add_row(
                paper.title[:60] + "..." if len(paper.title) > 60 else paper.title,
                str(keep),
                str(drop),
                status,
            )

        console.print(table)

    except FileNotFoundError as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def kept() -> None:
    """Show all papers that have been voted to keep."""
    kept_papers = vote_store.get_kept_papers()

    if not kept_papers:
        rprint("[yellow]No papers have been marked as 'keep' yet.[/yellow]")
        return

    table = Table(title="Kept Papers")
    table.add_column("Date", style="dim")
    table.add_column("Paper", style="cyan")
    table.add_column("Votes", justify="center")

    for paper in kept_papers:
        table.add_row(
            paper["date"],
            paper["title"][:50] + "..." if len(paper["title"]) > 50 else paper["title"],
            f"[green]{paper['keep_count']}[/green]/[red]{paper['drop_count']}[/red]",
        )

    console.print(table)


@app.command()
def dropped() -> None:
    """Show all papers that have been voted to drop."""
    dropped_papers = vote_store.get_dropped_papers()

    if not dropped_papers:
        rprint("[yellow]No papers have been marked as 'drop' yet.[/yellow]")
        return

    table = Table(title="Dropped Papers")
    table.add_column("Date", style="dim")
    table.add_column("Paper", style="cyan")
    table.add_column("Votes", justify="center")

    for paper in dropped_papers:
        table.add_row(
            paper["date"],
            paper["title"][:50] + "..." if len(paper["title"]) > 50 else paper["title"],
            f"[green]{paper['keep_count']}[/green]/[red]{paper['drop_count']}[/red]",
        )

    console.print(table)


if __name__ == "__main__":
    app()
