from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .claude_client import ClaudeTranslator
from .docx_io import read_paragraphs, write_paragraphs
from .settings import get_settings
from .terminology import Glossary, TranslationMemory

app = typer.Typer(help="Legal translation CLI placeholder.")


def _load_glossary(glossary_path: Path | None, source_lang: str, target_lang: str) -> Glossary | None:
    if glossary_path is None:
        return None
    return Glossary.from_csv(glossary_path, source_lang=source_lang, target_lang=target_lang, name=glossary_path.stem)


@app.command()
def translate_doc(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input DOCX file."),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output DOCX file (defaults to <name>.<lang>.docx)"),
    glossary_path: Optional[Path] = typer.Option(None, "--glossary", "-g", help="Glossary CSV file."),
    memory_path: Optional[Path] = typer.Option(None, "--memory", help="Translation memory JSON (defaults to data/memory.json)"),
    source_lang: Optional[str] = typer.Option(None, "--source-lang", "-s", help="Source language code (default from settings)."),
    target_lang: Optional[str] = typer.Option(None, "--target-lang", "-t", help="Target language code (default from settings)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip Claude calls and echo text for testing."),
) -> None:
    """Translate a DOCX file paragraph by paragraph using Claude with glossary + translation memory context."""
    settings = get_settings()
    src_lang = source_lang or settings.default_source_lang
    tgt_lang = target_lang or settings.default_target_lang
    output = output_path or input_path.with_name(f"{input_path.stem}.{tgt_lang}.docx")
    translation_memory_path = memory_path or settings.data_root / "memory.json"

    glossary = _load_glossary(glossary_path, src_lang, tgt_lang)
    memory = TranslationMemory(translation_memory_path)

    translator = ClaudeTranslator(api_key=settings.anthropic_api_key, dry_run=dry_run)

    paragraphs = read_paragraphs(input_path)
    translated: list[str] = []
    for idx, paragraph in enumerate(paragraphs, start=1):
        text = paragraph.strip()
        if not text:
            translated.append(paragraph)
            continue
        glossary_matches = glossary.matches_in_text(text) if glossary else []
        memory_hit = memory.get(text, src_lang, tgt_lang)
        if memory_hit:
            translated_text = memory_hit.translated_text
        else:
            memory_suggestions = memory.similar(text, src_lang, tgt_lang, limit=3, threshold=70.0)
            translated_text = translator.translate_paragraph(
                paragraph=text,
                source_lang=src_lang,
                target_lang=tgt_lang,
                glossary_matches=glossary_matches,
                memory_hits=memory_suggestions,
            )
            memory.record(text, translated_text, src_lang, tgt_lang)
        translated.append(translated_text)
        typer.echo(f"[{idx}/{len(paragraphs)}] translated {len(text)} chars")

    write_paragraphs(input_path, translated, output)
    typer.echo(f"Saved translated document to {output}")


@app.command()
def hello() -> None:
    """Placeholder command to verify wiring."""
    typer.echo("Translator CLI ready for implementation.")


if __name__ == "__main__":
    app()


