from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable, Sequence

from .claude_client import ClaudeTranslator
from .processing import DOCX_SUFFIX, build_report_payload, translate_file
from .terminology import Glossary, TranslationMemory

SUPPORTED_SUFFIXES = {DOCX_SUFFIX, ".pdf"}


def discover_documents(input_dir: Path) -> list[Path]:
    return sorted(
        [path for path in input_dir.iterdir() if path.suffix.lower() in SUPPORTED_SUFFIXES],
        key=lambda p: p.name,
    )


def run_batch(
    files: Sequence[Path],
    *,
    output_dir: Path,
    glossary: Glossary | None,
    memory: TranslationMemory,
    translator: ClaudeTranslator,
    source_lang: str,
    target_lang: str,
) -> tuple[Path, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "batch_id": batch_id,
        "output_dir": str(output_dir),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "files": [],
        "summary": {
            "documents_total": len(files),
            "documents_success": 0,
            "documents_failed": 0,
            "model_calls": 0,
            "glossary_matches": 0,
            "paragraphs_total": 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    for path in files:
        entry = {
            "input_file": str(path),
            "status": "pending",
        }
        manifest["files"].append(entry)

        try:
            default_output = output_dir / f"{path.stem}.{target_lang}{DOCX_SUFFIX}"
            start = perf_counter()
            outcome = translate_file(
                path,
                output_path=default_output,
                glossary=glossary,
                memory=memory,
                translator=translator,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            duration = perf_counter() - start
            report_payload = build_report_payload(outcome=outcome, source_lang=source_lang, target_lang=target_lang)
            report_file = outcome.output_path.with_suffix(".report.json")
            report_file.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            entry.update(
                {
                    "output_file": str(outcome.output_path),
                    "report_file": str(report_file),
                    "file_type": outcome.file_type,
                    "status": "success",
                    "duration_seconds": round(duration, 3),
                    "stats": report_payload["stats"],
                }
            )
            summary = manifest["summary"]
            summary["documents_success"] += 1
            summary["model_calls"] += outcome.stats.model_calls
            summary["glossary_matches"] += outcome.stats.glossary_matches
            summary["paragraphs_total"] += outcome.stats.paragraphs_total
        except Exception as exc:  # pragma: no cover - defensive logging
            entry.update({"status": "failed", "error": str(exc)})
            manifest["summary"]["documents_failed"] += 1
            continue

    manifest_path = output_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path, manifest

