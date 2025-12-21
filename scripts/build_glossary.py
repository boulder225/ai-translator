from __future__ import annotations

import csv
import shlex
import subprocess
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_DIR = ROOT / "glossary"
OUTPUT_FILE = GLOSSARY_DIR / "glossary.csv"
LANGUAGE_MARKER = "ital"


def read_word_file(path: Path) -> List[str]:
    """Convert .doc/.docx to plain text using macOS textutil."""
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment specific
        raise RuntimeError("textutil is required on macOS to process Word files.") from exc
    return [line.strip() for line in result.stdout.splitlines()]


def parse_multicol_lines(lines: List[str]) -> List[tuple[str, str]]:
    """Parse multilingual glossary lines and return non-Italian -> Italian pairs."""
    # locate header block containing Italian column
    idx = 0
    columns: List[str] = []
    while idx < len(lines):
        if not lines[idx]:
            idx += 1
            continue
        block: List[str] = []
        j = idx
        while j < len(lines) and lines[j]:
            block.append(lines[j])
            j += 1
        if block and any(LANGUAGE_MARKER in entry.lower() for entry in block):
            columns = block
            idx = j
            break
        idx = j
    if not columns:
        return []

    try:
        italian_index = next(i for i, col in enumerate(columns) if LANGUAGE_MARKER in col.lower())
    except StopIteration:
        return []

    data_lines = lines[idx:]
    chunk_size = len(columns)
    rows: List[List[str]] = []
    chunk: List[str] = []
    for line in data_lines:
        chunk.append(line)
        if len(chunk) == chunk_size:
            rows.append(chunk)
            chunk = []

    pairs: List[tuple[str, str]] = []
    for row in rows:
        if len(row) < chunk_size:
            continue
        italian_value = row[italian_index].strip()
        if not italian_value:
            continue
        for idx, value in enumerate(row):
            if idx == italian_index:
                continue
            term = value.strip()
            if term:
                pairs.append((term, italian_value))
    return pairs


def parse_tab_file(path: Path) -> List[tuple[str, str]]:
    pairs: List[tuple[str, str]] = []
    with path.open("r", encoding="cp1252", errors="ignore") as handle:
        for line in handle:
            raw = line.strip()
            if not raw or raw.startswith("!"):
                continue
            parts = [segment.strip() for segment in raw.split("\t") if segment.strip()]
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
    return pairs


def collect_entries() -> OrderedDict[str, tuple[str, str]]:
    entries: OrderedDict[str, tuple[str, str]] = OrderedDict()
    sources: List[Path] = sorted(
        [path for path in GLOSSARY_DIR.iterdir() if path.suffix.lower() in {".doc", ".docx", ".txt"}]
    )
    for source in sources:
        if source.suffix.lower() == ".txt":
            pairs = parse_tab_file(source)
        else:
            lines = read_word_file(source)
            pairs = parse_multicol_lines(lines)
        for term, translation in pairs:
            key = term.lower()
            if key not in entries:
                entries[key] = (term, translation)
    return entries


def write_csv(rows: Iterable[tuple[str, str]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["term", "translation"])
        for term, translation in rows:
            writer.writerow([term, translation])


def main() -> None:
    entries = collect_entries()
    write_csv(entries.values())
    print(f"Written {len(entries)} entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()










