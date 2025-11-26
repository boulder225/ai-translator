from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Iterable

from rapidfuzz import fuzz


@dataclass(slots=True, frozen=True)
class TranslationRecord:
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str

    @property
    def key(self) -> str:
        raw = f"{self.source_lang}:{self.target_lang}:{self.source_text.strip()}"
        return sha1(raw.encode("utf-8")).hexdigest()


class TranslationMemory:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: dict[str, TranslationRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("{}", encoding="utf-8")
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid translation memory file: {self.path}") from exc
        for key, payload in data.items():
            record = TranslationRecord(
                source_text=payload["source_text"],
                translated_text=payload["translated_text"],
                source_lang=payload["source_lang"],
                target_lang=payload["target_lang"],
            )
            self._records[key] = record

    def save(self) -> None:
        serializable = {
            key: {
                "source_text": record.source_text,
                "translated_text": record.translated_text,
                "source_lang": record.source_lang,
                "target_lang": record.target_lang,
            }
            for key, record in self._records.items()
        }
        self.path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, source_text: str, translated_text: str, source_lang: str, target_lang: str) -> TranslationRecord:
        record = TranslationRecord(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        self._records[record.key] = record
        self.save()
        return record

    def get(self, source_text: str, source_lang: str, target_lang: str) -> TranslationRecord | None:
        key = TranslationRecord(
            source_text=source_text,
            translated_text="",
            source_lang=source_lang,
            target_lang=target_lang,
        ).key
        return self._records.get(key)

    def similar(self, source_text: str, source_lang: str, target_lang: str, *, limit: int = 5, threshold: float = 80.0) -> list[TranslationRecord]:
        candidates: list[tuple[float, TranslationRecord]] = []
        for record in self._records.values():
            if record.source_lang != source_lang or record.target_lang != target_lang:
                continue
            score = fuzz.token_set_ratio(source_text, record.source_text)
            if score >= threshold:
                candidates.append((score, record))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in candidates[:limit]]

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterable[TranslationRecord]:
        return iter(self._records.values())

