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
        # #region agent log
        import json
        import os
        import time
        log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "memory.py:record",
                    "message": "Saving translation to memory",
                    "data": {
                        "source_text_preview": source_text[:100],
                        "translated_text_preview": translated_text[:100],
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "memory_file": str(self.path),
                        "records_before": len(self._records)
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "F"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        record = TranslationRecord(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        self._records[record.key] = record
        self.save()
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "memory.py:record",
                    "message": "Translation saved to memory",
                    "data": {
                        "key": record.key,
                        "records_after": len(self._records),
                        "memory_file": str(self.path),
                        "file_exists_after": self.path.exists()
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "F"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        return record

    def get(self, source_text: str, source_lang: str, target_lang: str) -> TranslationRecord | None:
        # #region agent log
        import json
        import os
        import time
        log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            key = TranslationRecord(
                source_text=source_text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
            ).key
            result = self._records.get(key)
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "memory.py:get",
                    "message": "Memory exact match lookup",
                    "data": {
                        "source_text_preview": source_text[:100],
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "key": key,
                        "found": result is not None,
                        "total_records": len(self._records)
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }) + "\n")
        except Exception:
            key = TranslationRecord(
                source_text=source_text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
            ).key
            result = self._records.get(key)
        # #endregion
        return result

    def similar(self, source_text: str, source_lang: str, target_lang: str, *, limit: int = 5, threshold: float = 80.0) -> list[TranslationRecord]:
        # #region agent log
        import json
        import os
        import time
        log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "memory.py:similar",
                    "message": "Memory similarity search started",
                    "data": {
                        "source_text_preview": source_text[:100],
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "threshold": threshold,
                        "limit": limit,
                        "total_records": len(self._records)
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        candidates: list[tuple[float, TranslationRecord]] = []
        checked_count = 0
        for record in self._records.values():
            if record.source_lang != source_lang or record.target_lang != target_lang:
                continue
            checked_count += 1
            score = fuzz.token_set_ratio(source_text, record.source_text)
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "location": "memory.py:similar",
                        "message": "Similarity score calculated",
                        "data": {
                            "source_text_preview": source_text[:100],
                            "record_source_preview": record.source_text[:100],
                            "score": score,
                            "threshold": threshold,
                            "above_threshold": score >= threshold,
                            "source_lang_match": record.source_lang == source_lang,
                            "target_lang_match": record.target_lang == target_lang
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "D"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            if score >= threshold:
                candidates.append((score, record))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        result = [record for _, record in candidates[:limit]]
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "memory.py:similar",
                    "message": "Memory similarity search completed",
                    "data": {
                        "source_text_preview": source_text[:100],
                        "checked_records": checked_count,
                        "candidates_found": len(candidates),
                        "results_returned": len(result),
                        "top_scores": [score for score, _ in candidates[:3]] if candidates else []
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        return result

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterable[TranslationRecord]:
        return iter(self._records.values())











