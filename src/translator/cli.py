from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from .batch_runner import discover_documents, run_batch
from .claude_client import ClaudeTranslator
from .processing import PDF_SUFFIX, build_report_payload, translate_file
from .settings import get_settings
from .terminology import Glossary, TranslationMemory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)

app = typer.Typer(help="Legal translation CLI placeholder.")


def _load_glossary(glossary_path: Path | None, source_lang: str, target_lang: str) -> Glossary | None:
    if glossary_path is None:
        return None
    return Glossary.from_csv(glossary_path, source_lang=source_lang, target_lang=target_lang, name=glossary_path.stem)


def _progress_echo(idx: int, total: int, length: int) -> None:
    typer.echo(f"[{idx}/{total}] translated {length} chars")


@app.command()
def translate_doc(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input DOCX/PDF/TXT file."),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output PDF file (defaults to <name>.<lang>.pdf)"),
    glossary_path: Optional[Path] = typer.Option(None, "--glossary", "-g", help="Glossary CSV file."),
    memory_path: Optional[Path] = typer.Option(None, "--memory", help="Translation memory JSON (defaults to data/memory.json)"),
    source_lang: Optional[str] = typer.Option(None, "--source-lang", "-s", help="Source language code (default from settings)."),
    target_lang: Optional[str] = typer.Option(None, "--target-lang", "-t", help="Target language code (default from settings)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip Claude calls and echo text for testing."),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON file to store translation stats."),
    skip_memory: bool = typer.Option(False, "--skip-memory", help="Force skip translation memory, always apply term hierarchy and translate."),
) -> None:
    """Translate a DOCX, PDF, or TXT file with glossary + translation memory support."""
    settings = get_settings()
    src_lang = source_lang or settings.default_source_lang
    tgt_lang = target_lang or settings.default_target_lang
    default_output = input_path.with_name(f"{input_path.stem}.{tgt_lang}{PDF_SUFFIX}")
    output = output_path or default_output
    translation_memory_path = memory_path or settings.data_root / "memory.json"

    glossary = _load_glossary(glossary_path, src_lang, tgt_lang)
    memory = TranslationMemory(translation_memory_path)
    translator = ClaudeTranslator(api_key=settings.anthropic_api_key, dry_run=dry_run)

    typer.echo(f"Translating {input_path.name} -> {tgt_lang}")
    try:
        outcome = translate_file(
            input_path,
            output_path=output,
            glossary=glossary,
            memory=memory,
            translator=translator,
            source_lang=src_lang,
            target_lang=tgt_lang,
            progress_callback=_progress_echo,
            skip_memory=skip_memory,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Saved translated document to {outcome.output_path}")
    report_payload = build_report_payload(outcome=outcome, source_lang=src_lang, target_lang=tgt_lang)
    report_file = report_path or outcome.output_path.with_suffix(".report.json")
    report_file.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Wrote translation report to {report_file}")


@app.command("translate-batch")
def translate_batch(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, help="Directory containing DOCX/PDF/TXT files."),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Directory for translated files (defaults to data/exports/<timestamp>)."),
    glossary_path: Optional[Path] = typer.Option(None, "--glossary", "-g", help="Glossary CSV file."),
    memory_path: Optional[Path] = typer.Option(None, "--memory", help="Translation memory JSON (defaults to data/memory.json)"),
    source_lang: Optional[str] = typer.Option(None, "--source-lang", "-s", help="Source language code (default from settings)."),
    target_lang: Optional[str] = typer.Option(None, "--target-lang", "-t", help="Target language code (default from settings)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip Claude calls and echo text for testing."),
    skip_memory: bool = typer.Option(False, "--skip-memory", help="Force skip translation memory, always apply term hierarchy and translate."),
) -> None:
    """Translate every DOCX/PDF/TXT in a directory and emit a batch manifest."""
    settings = get_settings()
    src_lang = source_lang or settings.default_source_lang
    tgt_lang = target_lang or settings.default_target_lang
    translation_memory_path = memory_path or settings.data_root / "memory.json"
    default_output_dir = settings.data_root / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    batch_output_dir = output_dir or default_output_dir

    files = discover_documents(input_dir)
    if not files:
        typer.echo("No DOCX, PDF, or TXT files found in the input directory.")
        raise typer.Exit(code=1)

    glossary = _load_glossary(glossary_path, src_lang, tgt_lang)
    memory = TranslationMemory(translation_memory_path)
    translator = ClaudeTranslator(api_key=settings.anthropic_api_key, dry_run=dry_run)

    typer.echo(f"Processing {len(files)} files -> {batch_output_dir}")
    manifest_path, manifest = run_batch(
        files,
        output_dir=batch_output_dir,
        glossary=glossary,
        memory=memory,
        translator=translator,
        source_lang=src_lang,
        target_lang=tgt_lang,
        skip_memory=skip_memory,
    )
    summary = manifest["summary"]
    typer.echo(
        f"Batch complete: {summary['documents_success']} succeeded, {summary['documents_failed']} failed, "
        f"{summary['model_calls']} Claude calls."
    )
    typer.echo(f"Manifest saved to {manifest_path}")


@app.command()
def web() -> None:
    """Launch the web UI for document translation."""
    import subprocess
    import sys
    from pathlib import Path
    
    ui_file = Path(__file__).parent / "web_ui.py"
    typer.echo("Starting web UI at http://localhost:8501")
    typer.echo("Press Ctrl+C to stop the server.")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(ui_file),
        "--server.port", "8501"
    ])


@app.command()
def hello() -> None:
    """Placeholder command to verify wiring."""
    typer.echo("Translator CLI ready for implementation.")


if __name__ == "__main__":
    app()


