from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Sequence

from .claude_client import ClaudeTranslator
from .docx_io import read_paragraphs, write_new_document, write_paragraphs
from .pdf_io import read_paragraphs_from_pdf
from .terminology import Glossary, GlossaryMatch, TranslationMemory, TranslationRecord

DOCX_SUFFIX = ".docx"


ProgressCallback = Callable[[int, int, int], None]


@dataclass(slots=True)
class TranslationStats:
    paragraphs_total: int
    empty_paragraphs: int = 0
    reused_from_memory: int = 0
    model_calls: int = 0
    glossary_matches: int = 0
    paragraph_logs: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class TranslationOutcome:
    input_path: Path
    output_path: Path
    file_type: str
    translations: list[str]
    stats: TranslationStats
    duration_seconds: float


def _translate_paragraphs(
    paragraphs: Sequence[str],
    *,
    translator: ClaudeTranslator,
    glossary: Glossary | None,
    memory: TranslationMemory,
    source_lang: str,
    target_lang: str,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[str], TranslationStats]:
    stats = TranslationStats(paragraphs_total=len(paragraphs))
    translated: list[str] = []
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
            stats.empty_paragraphs += 1
            translated.append(paragraph)
            stats.paragraph_logs.append(paragraph_log)
            if progress_callback:
                progress_callback(idx, stats.paragraphs_total, len(text))
            continue

        glossary_matches: list[GlossaryMatch] = glossary.matches_in_text(text) if glossary else []
        stats.glossary_matches += len(glossary_matches)
        paragraph_log["glossary_terms"] = [match.entry.term for match in glossary_matches]

        memory_hit: TranslationRecord | None = memory.get(text, source_lang, target_lang)
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

        paragraph_log["output_preview"] = translated_text[:120]
        translated.append(translated_text)
        stats.paragraph_logs.append(paragraph_log)
        if progress_callback:
            progress_callback(idx, stats.paragraphs_total, len(text))
    return translated, stats


def _read_input_file(input_path: Path, output_path: Path) -> tuple[list[str], str, Path]:
    suffix = input_path.suffix.lower()
    if suffix == DOCX_SUFFIX:
        return read_paragraphs(input_path), "DOCX", output_path
    if suffix == ".pdf":
        paragraphs = read_paragraphs_from_pdf(input_path)
        return paragraphs, "PDF", output_path.with_suffix(DOCX_SUFFIX)
    raise ValueError("Unsupported file type. Use DOCX or PDF.")


def translate_file(
    input_path: Path,
    *,
    output_path: Path,
    glossary: Glossary | None,
    memory: TranslationMemory,
    translator: ClaudeTranslator,
    source_lang: str,
    target_lang: str,
    progress_callback: ProgressCallback | None = None,
) -> TranslationOutcome:
    paragraphs, file_type, normalized_output = _read_input_file(input_path, output_path)
    if not paragraphs:
        raise ValueError("No text found to translate.")

    start = perf_counter()
    translations, stats = _translate_paragraphs(
        paragraphs,
        translator=translator,
        glossary=glossary,
        memory=memory,
        source_lang=source_lang,
        target_lang=target_lang,
        progress_callback=progress_callback,
    )
    duration = perf_counter() - start

    if file_type == "DOCX":
        write_paragraphs(input_path, translations, normalized_output)
    else:
        write_new_document(translations, normalized_output)

    return TranslationOutcome(
        input_path=input_path,
        output_path=normalized_output,
        file_type=file_type,
        translations=translations,
        stats=stats,
        duration_seconds=duration,
    )


def build_report_payload(
    *,
    outcome: TranslationOutcome,
    source_lang: str,
    target_lang: str,
    generated_at: datetime | None = None,
) -> dict:
    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "input_file": str(outcome.input_path),
        "output_file": str(outcome.output_path),
        "file_type": outcome.file_type,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "duration_seconds": round(outcome.duration_seconds, 3),
        "stats": {
            "paragraphs_total": outcome.stats.paragraphs_total,
            "empty_paragraphs": outcome.stats.empty_paragraphs,
            "reused_from_memory": outcome.stats.reused_from_memory,
            "model_calls": outcome.stats.model_calls,
            "glossary_matches": outcome.stats.glossary_matches,
            "paragraphs": outcome.stats.paragraph_logs,
        },
        "generated_at": timestamp.isoformat(),
    }

