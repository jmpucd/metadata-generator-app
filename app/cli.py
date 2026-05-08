"""
app/cli.py — Typer CLI for the photo metadata review app.

Usage examples:
    python -m app.cli ingest /path/to/images --collection "Farm Life 1940s"
    python -m app.cli generate --collection "Farm Life 1940s"
    python -m app.cli review
    python -m app.cli export --format json
    python -m app.cli export --format csv
    python -m app.cli export --format xmp
    python -m app.cli db-check
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

app = typer.Typer(
    name="photo-review",
    help="Local-first photo metadata review tool for library collections.",
    no_args_is_help=True,
)
console = Console()


# ── Lazy DB / model imports so CLI starts fast ───────────────────────────────

def _get_db():
    from app.db.schema import create_tables, get_session
    create_tables()
    return get_session()


# ── ingest ────────────────────────────────────────────────────────────────────

@app.command()
def ingest(
    folder: Path = typer.Argument(..., help="Path to the folder of images to ingest."),
    collection: str = typer.Option(..., "--collection", "-c", help="Collection name."),
    recursive: bool = typer.Option(True, help="Search sub-folders recursively."),
):
    """Ingest a folder of images into the database."""
    from app.db.crud import get_or_create_collection, ingest_image
    from app.utils.image_utils import find_images, sha256_file

    if not folder.exists():
        rprint(f"[red]Folder not found:[/red] {folder}")
        raise typer.Exit(1)

    db = _get_db()
    coll = get_or_create_collection(db, collection)
    rprint(f"[bold]Collection:[/bold] {coll.name} (id={coll.id})")

    images = find_images(folder) if recursive else [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp", ".webp"}
    ]

    if not images:
        rprint("[yellow]No supported image files found.[/yellow]")
        raise typer.Exit(0)

    new_count = 0
    skipped = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting…", total=len(images))
        for img_path in images:
            file_hash = sha256_file(img_path)
            img = ingest_image(db, str(img_path), coll.id, file_hash)
            if img.ingested_at:
                new_count += 1
            else:
                skipped += 1
            progress.advance(task)

    rprint(f"[green]✔ Done.[/green] {new_count} ingested, {skipped} already known.")


# ── generate ──────────────────────────────────────────────────────────────────

@app.command()
def generate(
    collection: str = typer.Option(..., "--collection", "-c", help="Collection name."),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Max images to process."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-generate even if draft exists."),
):
    """Generate draft metadata for images using the local VLM."""
    from app.db.crud import (
        get_collection_by_name, list_images, get_metadata,
        upsert_metadata, mark_draft_generated, snapshot_revision,
    )
    from app.models.local_vlm import generate_metadata

    db = _get_db()
    coll = get_collection_by_name(db, collection)
    if not coll:
        rprint(f"[red]Collection not found:[/red] {collection!r}")
        raise typer.Exit(1)

    images = list_images(db, collection_id=coll.id)
    if not overwrite:
        images = [img for img in images if not (get_metadata(db, img.id) and get_metadata(db, img.id).draft_generated)]

    if limit:
        images = images[:limit]

    if not images:
        rprint("[yellow]No images need draft generation.[/yellow]")
        raise typer.Exit(0)

    rprint(f"[bold]Generating metadata for {len(images)} images…[/bold]")
    session_ctx = coll.session_context()
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing…", total=len(images))
        for img in images:
            progress.update(task, description=img.filename)
            try:
                fields = generate_metadata(img.filepath, session_ctx)
                upsert_metadata(db, img.id, fields)
                mark_draft_generated(db, img.id)
                snapshot_revision(db, img.id, "draft")
            except Exception as e:
                rprint(f"[red]  ✗ {img.filename}: {e}[/red]")
                errors += 1
            progress.advance(task)

    rprint(f"[green]✔ Done.[/green] {len(images) - errors} succeeded, {errors} failed.")


# ── review ────────────────────────────────────────────────────────────────────

@app.command()
def review(
    port: int = typer.Option(8501, help="Streamlit port."),
    host: str = typer.Option("localhost", help="Streamlit host."),
):
    """Launch the Streamlit review UI."""
    import subprocess, os
    app_path = Path(__file__).resolve().parent.parent / "streamlit_app.py"
    rprint(f"[bold]Launching Streamlit at http://{host}:{port}[/bold]")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.address", host,
    ])


# ── export ────────────────────────────────────────────────────────────────────

@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json | csv | xmp"),
    collection: Optional[str] = typer.Option(None, "--collection", "-c"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path."),
):
    """Export approved metadata records."""
    from app.db.crud import get_approved_records, get_collection_by_name
    from app.export import export_json, export_csv, export_xmp

    db = _get_db()
    col_id = None
    if collection:
        coll = get_collection_by_name(db, collection)
        if not coll:
            rprint(f"[red]Collection not found:[/red] {collection!r}")
            raise typer.Exit(1)
        col_id = coll.id

    records = get_approved_records(db, collection_id=col_id)
    if not records:
        rprint("[yellow]No approved records to export.[/yellow]")
        raise typer.Exit(0)

    rprint(f"Exporting {len(records)} approved records as [bold]{format.upper()}[/bold]…")

    fmt = format.lower()
    try:
        if fmt == "json":
            result = export_json(records, output)
            rprint(f"[green]✔[/green] {result}")
        elif fmt == "csv":
            result = export_csv(records, output)
            rprint(f"[green]✔[/green] {result}")
        elif fmt == "xmp":
            written = export_xmp(records, output)
            rprint(f"[green]✔[/green] {len(written)} XMP sidecars written to {written[0].parent}")
        else:
            rprint(f"[red]Unknown format:[/red] {format!r}. Use json, csv, or xmp.")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Export error:[/red] {e}")
        raise typer.Exit(1)


# ── db-check ──────────────────────────────────────────────────────────────────

@app.command(name="db-check")
def db_check():
    """Inspect the database schema and apply any missing migrations."""
    from app.db.migrations import check_and_migrate
    rprint("[bold]Running schema check…[/bold]")
    actions = check_and_migrate(verbose=True)
    if not actions:
        rprint("[green]✔ Schema is up to date.[/green]")
    else:
        rprint(f"[green]✔ Applied {len(actions)} migration(s).[/green]")


# ── status ────────────────────────────────────────────────────────────────────

@app.command()
def status(
    collection: Optional[str] = typer.Option(None, "--collection", "-c"),
):
    """Show review status counts."""
    from app.db.crud import status_counts, list_collections, get_collection_by_name
    from app.config import REVIEW_STATUSES

    db = _get_db()
    col_id = None
    if collection:
        coll = get_collection_by_name(db, collection)
        if not coll:
            rprint(f"[red]Collection not found:[/red] {collection!r}")
            raise typer.Exit(1)
        col_id = coll.id

    table = Table(title="Review Status", show_lines=True)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")

    counts = status_counts(db, collection_id=col_id)
    total = 0
    for s in REVIEW_STATUSES:
        n = counts.get(s, 0)
        total += n
        table.add_row(s, str(n))
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]")

    console.print(table)


# ── dagster ───────────────────────────────────────────────────────────────────

@app.command()
def dagster_dev(
    host: str = typer.Option("localhost", help="Dagster UI host."),
    port: int = typer.Option(3000, help="Dagster UI port."),
):
    """Launch the Dagster dev UI (dagster dev)."""
    import subprocess
    rprint(f"[bold]Launching Dagster UI at http://{host}:{port}[/bold]")
    subprocess.run([
        sys.executable, "-m", "dagster", "dev",
        "-m", "app.dagster.definitions",
        "--host", host,
        "--port", str(port),
    ])


@app.command()
def dagster_run(
    job: str = typer.Option("ingest_and_generate", "--job", "-j",
                             help="Job name: ingest_and_generate | export_all | export_json"),
    image_folder: Optional[str] = typer.Option(None, help="Image folder (for ingest jobs)."),
    collection: Optional[str] = typer.Option(None, "--collection", "-c"),
):
    """Run a Dagster job directly from the CLI (no UI needed)."""
    import subprocess, json as _json

    run_config: dict = {}
    if image_folder or collection:
        run_config = {
            "ops": {
                "ingested_images": {
                    "config": {
                        "image_folder": image_folder or "",
                        "collection_name": collection or "default",
                    }
                }
            }
        }

    config_arg = []
    if run_config:
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        _json.dump(run_config, tmp)
        tmp.close()
        config_arg = ["--config", tmp.name]

    rprint(f"[bold]Running Dagster job:[/bold] {job}")
    result = subprocess.run([
        sys.executable, "-m", "dagster", "job", "execute",
        "-m", "app.dagster.definitions",
        "--job", job,
        *config_arg,
    ])
    raise typer.Exit(result.returncode)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
