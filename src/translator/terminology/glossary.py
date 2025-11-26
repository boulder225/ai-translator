from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rapidfuzz import fuzz, process


@dataclass(slots=True, frozen=True)
class GlossaryEntry:
    term: str
    translation: str
    context: str | None = None

    @property
    def fingerprint(self) -> str:
        raw = f"{self.term.lower()}::{self.translation.lower()}::{self.context or ''}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True, frozen=True)
class GlossaryMatch:
    entry: GlossaryEntry
    score: float
    matched_term: str


class Glossary:
    def __init__(self, entries: Sequence[GlossaryEntry], source_lang: str, target_lang: str, *, name: str | None = None) -> None:
        self._entries = list(entries)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.name = name or "glossary"
        self._by_term = {}
        for entry in self._entries:
            key = entry.term.lower().strip()
            self._by_term.setdefault(key, []).append(entry)

    @classmethod
    def from_csv(cls, path: str | Path, source_lang: str, target_lang: str, *, name: str | None = None) -> "Glossary":
        entries: list[GlossaryEntry] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"term", "translation"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Glossary CSV must include headers {required}, got {reader.fieldnames}")
            for row in reader:
                term = (row.get("term") or "").strip()
                translation = (row.get("translation") or "").strip()
                if not term or not translation:
                    continue
                context = (row.get("context") or "").strip() or None
                entries.append(GlossaryEntry(term=term, translation=translation, context=context))
        return cls(entries, source_lang=source_lang, target_lang=target_lang, name=name or Path(path).stem)

    def __len__(self) -> int:
        return len(self._entries)

    def exact_matches(self, term: str) -> list[GlossaryEntry]:
        return list(self._by_term.get(term.lower().strip(), []))

    def fuzzy_matches(self, term: str, *, limit: int = 3, threshold: float = 75.0) -> list[GlossaryMatch]:
        if not self._entries:
            return []
        candidates = process.extract(term, [e.term for e in self._entries], scorer=fuzz.QRatio, limit=limit)
        matches: list[GlossaryMatch] = []
        for candidate_term, score, index in candidates:
            if score < threshold:
                continue
            entry = self._entries[index]
            matches.append(GlossaryMatch(entry=entry, score=score, matched_term=candidate_term))
        return matches

    def iter_entries(self) -> Iterable[GlossaryEntry]:
        return iter(self._entries)

    def matches_in_text(self, text: str) -> list[GlossaryMatch]:
        lowered = text.lower()
        matches: list[GlossaryMatch] = []
        for entry in self._entries:
            term_lower = entry.term.lower()
            if term_lower and term_lower in lowered:
                matches.append(GlossaryMatch(entry=entry, score=100.0, matched_term=entry.term))
        return matches

