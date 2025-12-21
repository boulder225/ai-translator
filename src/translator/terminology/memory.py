from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Iterable

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


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
        glossary_memory = self.path.parent.parent / "glossary" / "memory.json"
        
        # Load glossary seed file for merging (if it exists)
        glossary_data = {}
        if glossary_memory.exists():
            try:
                glossary_raw = glossary_memory.read_text(encoding="utf-8")
                glossary_data = json.loads(glossary_raw or "{}")
            except Exception as e:
                logger.warning(f"Failed to read glossary seed file: {e}")
                glossary_data = {}
        
        if not self.path.exists():
            # First time: initialize from glossary/memory.json if it exists
            if glossary_data:
                try:
                    import shutil
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(glossary_memory, self.path)
                    # Make sure file is writable
                    import os
                    os.chmod(self.path, 0o644)
                except Exception as e:
                    logger.warning(f"Failed to copy from glossary: {e}, creating empty file")
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text("{}", encoding="utf-8")
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text("{}", encoding="utf-8")
        
        # Load runtime memory file
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            logger.error(f"JSON decode error in memory file: {exc}, path={self.path}")
            raise ValueError(f"Invalid translation memory file: {self.path}") from exc
        
        # Load runtime records (these take precedence)
        records_loaded = 0
        for key, payload in data.items():
            record = TranslationRecord(
                source_text=payload["source_text"],
                translated_text=payload["translated_text"],
                source_lang=payload["source_lang"],
                target_lang=payload["target_lang"],
            )
            self._records[key] = record
            records_loaded += 1
        
        # Merge in new records from glossary seed file (only if they don't already exist)
        # This allows git updates to glossary/memory.json to add new records without overwriting runtime data
        records_added_from_seed = 0
        if glossary_data:
            for key, payload in glossary_data.items():
                if key not in self._records:
                    record = TranslationRecord(
                        source_text=payload["source_text"],
                        translated_text=payload["translated_text"],
                        source_lang=payload["source_lang"],
                        target_lang=payload["target_lang"],
                    )
                    self._records[key] = record
                    records_added_from_seed += 1
        
        # Save merged data if we added records from seed
        if records_added_from_seed > 0:
            logger.info(f"Merged {records_added_from_seed} new records from seed file into memory")
            self.save()

    def save(self) -> None:
        import os
        import stat
        
        serializable = {
            key: {
                "source_text": record.source_text,
                "translated_text": record.translated_text,
                "source_lang": record.source_lang,
                "target_lang": record.target_lang,
            }
            for key, record in self._records.items()
        }
        
        try:
            # Ensure parent directory exists and is writable
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not os.access(self.path.parent, os.W_OK):
                raise PermissionError(f"Parent directory is not writable: {self.path.parent}")
            
            # Ensure file is writable if it exists
            if self.path.exists():
                try:
                    os.chmod(self.path, 0o644)
                except Exception:
                    pass
            
            # Write the file
            json_content = json.dumps(serializable, ensure_ascii=False, indent=2)
            self.path.write_text(json_content, encoding="utf-8")
            
            # Ensure file is writable after write (in case it was created)
            try:
                os.chmod(self.path, 0o644)
            except Exception:
                pass
        except PermissionError as e:
            logger.error(f"Permission error saving memory: {e}, path={self.path}")
            raise
        except Exception as e:
            logger.error(f"Failed to save memory: {type(e).__name__}: {e}, path={self.path}")
            raise

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











