from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import typer

from .claude_client import ClaudeTranslator
from .docx_io import read_paragraphs, write_new_document, write_paragraphs
from .pdf_io import read_paragraphs_from_pdf
from .settings import get_settings
from .terminology import Glossary, TranslationMemory

DOCX_SUFFIX = ".docx"
@dataclass
class TranslationStats:
    paragraphs_total: int
    empty_paragraphs: int = 0
    reused_from_memory: int = 0
    model_calls: int = 0
    glossary_matches: int = 0
    paragraph_logs: list[dict[str, object]] = field(default_factory=list)

app = typer.Typer(help="Legal translation CLI placeholder.")


def _load_glossary(glossary_path: Path | None, source_lang: str, target_lang: str) -> Glossary | None:
    if glossary_path is None:
        return None
    return Glossary.from_csv(glossary_path, source_lang=source_lang, target_lang=target_lang, name=glossary_path.stem)


def _translate_paragraphs(
    paragraphs: list[str],
    *,
    translator: ClaudeTranslator,
    glossary: Glossary | None,
    memory: TranslationMemory,
    source_lang: str,
    target_lang: str,
) -> Tuple[list[str], TranslationStats]:
    translated: list[str] = []
    total = len(paragraphs)
    stats = TranslationStats(paragraphs_total=total)
    for idx, paragraph in enumerate(paragraphs, start=1):
        text = paragraph.strip()
        paragraph_log: dict[str, object] = {
            "index": idx,
            "length": len(paragraph),
            "source_preview": text[:120],
            "used_memory": False,
            "model_called": False,
            "glossary_terms": [],
        }
        if not text:
            translated.append(paragraph)
            stats.empty_paragraphs += 1
            stats.paragraph_logs.append(paragraph_log)
            continue
        glossary_matches = glossary.matches_in_text(text) if glossary else []
        stats.glossary_matches += len(glossary_matches)
        paragraph_log["glossary_terms"] = [match.entry.term for match in glossary_matches]
        memory_hit = memory.get(text, source_lang, target_lang)
        if memory_hit:
            translated_text = memory_hit.translated_text
            stats.reused_from_memory += 1
            paragraph_log["used_memory"] = True
        else:
            memory_suggestions = memory.similar(text, source_lang, target_lang, limit=3, threshold=70.0)
            translated_text = translator.translate_paragraph(
                paragraph=text,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_matches=glossary_matches,
                memory_hits=memory_suggestions,
            )
            memory.record(text, translated_text, source_lang, target_lang)
            stats.model_calls += 1
            paragraph_log["model_called"] = True
            paragraph_log["memory_suggestions"] = [record.source_text[:80] for record in memory_suggestions]
        translated.append(translated_text)
        stats.paragraph_logs.append(paragraph_log)
        typer.echo(f"[{idx}/{total}] translated {len(text)} chars")
    return translated, stats


@app.command()
def translate_doc(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input DOCX file."),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output DOCX file (defaults to <name>.<lang>.docx)"),
    glossary_path: Optional[Path] = typer.Option(None, "--glossary", "-g", help="Glossary CSV file."),
    memory_path: Optional[Path] = typer.Option(None, "--memory", help="Translation memory JSON (defaults to data/memory.json)"),
    source_lang: Optional[str] = typer.Option(None, "--source-lang", "-s", help="Source language code (default from settings)."),
    target_lang: Optional[str] = typer.Option(None, "--target-lang", "-t", help="Target language code (default from settings)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip Claude calls and echo text for testing."),
    report_path: Optional[Path] = typer.Option(None, "--report", help="Optional JSON file to store translation stats."),
) -> None:
    """Translate a DOCX or PDF file paragraph by paragraph using Claude with glossary + translation memory context."""
    settings = get_settings()
    src_lang = source_lang or settings.default_source_lang
    tgt_lang = target_lang or settings.default_target_lang
    output = output_path or input_path.with_name(f"{input_path.stem}.{tgt_lang}{DOCX_SUFFIX}")
    translation_memory_path = memory_path or settings.data_root / "memory.json"

    glossary = _load_glossary(glossary_path, src_lang, tgt_lang)
    memory = TranslationMemory(translation_memory_path)

    translator = ClaudeTranslator(api_key=settings.anthropic_api_key, dry_run=dry_run)

    suffix = input_path.suffix.lower()
    if suffix == DOCX_SUFFIX:
        paragraphs = read_paragraphs(input_path)
        writer = "DOCX"
    elif suffix == ".pdf":
        paragraphs = read_paragraphs_from_pdf(input_path)
        writer = "PDF"
        if output.suffix.lower() != DOCX_SUFFIX:
            output = output.with_suffix(DOCX_SUFFIX)
    else:
        raise typer.BadParameter("Unsupported file type. Use DOCX or PDF.")

    if not paragraphs:
        typer.echo("No text found to translate.")
        raise typer.Exit(code=1)
    typer.echo(f"Translating {len(paragraphs)} paragraphs from {writer} -> DOCX")
    translated, stats = _translate_paragraphs(
        paragraphs,
        translator=translator,
        glossary=glossary,
        memory=memory,
        source_lang=src_lang,
        target_lang=tgt_lang,
    )

    if writer == "DOCX":
        write_paragraphs(input_path, translated, output)
    else:
        write_new_document(translated, output)
    typer.echo(f"Saved translated document to {output}")
    report_file = report_path or output.with_suffix(".report.json")
    report_payload = {
        "input_file": str(input_path),
        "output_file": str(output),
        "file_type": writer,
        "source_lang": src_lang,
        "target_lang": tgt_lang,
        "stats": {
            "paragraphs_total": stats.paragraphs_total,
            "empty_paragraphs": stats.empty_paragraphs,
            "reused_from_memory": stats.reused_from_memory,
            "model_calls": stats.model_calls,
            "glossary_matches": stats.glossary_matches,
            "paragraphs": stats.paragraph_logs,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    report_file.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Wrote translation report to {report_file}")


@app.command()
def hello() -> None:
    """Placeholder command to verify wiring."""
    typer.echo("Translator CLI ready for implementation.")


if __name__ == "__main__":
    app()


