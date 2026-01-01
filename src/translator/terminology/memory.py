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
        self._allow_long_entries_flags: dict[str, bool] = {}  # Track which records allow long entries
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
            # But clean stale entries from seed file before copying
            if glossary_data:
                try:
                    import shutil
                    import os
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Clean stale entries from seed file data before copying
                    cleaned_seed_data = {}
                    for key, record_data in glossary_data.items():
                        if not isinstance(record_data, dict):
                            continue
                        source_text = record_data.get("source_text", "").strip()
                        translated_text = record_data.get("translated_text", "").strip()
                        
                        # Apply same filters as cleanup
                        if not source_text or not translated_text:
                            continue
                        MAX_MEMORY_ENTRY_LENGTH = 1000
                        if len(source_text) > MAX_MEMORY_ENTRY_LENGTH or len(translated_text) > MAX_MEMORY_ENTRY_LENGTH:
                            continue
                        placeholder_chars = source_text.count('_') + source_text.count('□') + source_text.count('☐') + source_text.count('☑')
                        placeholder_ratio = placeholder_chars / len(source_text) if source_text else 0
                        if placeholder_ratio > 0.1:
                            continue
                        non_whitespace_ratio = len(''.join(source_text.split())) / len(source_text) if source_text else 0
                        if non_whitespace_ratio < 0.3:
                            continue
                        # Entry passed filters, include it
                        cleaned_seed_data[key] = record_data
                    
                    # Write cleaned seed data to runtime file
                    self.path.write_text(
                        json.dumps(cleaned_seed_data, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    os.chmod(self.path, 0o644)
                    if len(cleaned_seed_data) < len(glossary_data):
                        logger.info(f"Cleaned {len(glossary_data) - len(cleaned_seed_data)} stale entries from seed file during initialization")
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
            raise ValueError(f"Invalid translation memory file: {self.path}")
        
        # Clean up stale entries (long entries with placeholders) from existing memory
        # #region agent log
        import json as json_module
        log_path = "/Users/enrico/workspace/translator/.cursor/debug.log"
        try:
            total_entries_before = len(data)
            with open(log_path, "a") as f:
                f.write(json_module.dumps({"sessionId": "debug-session", "runId": "cleanup-check", "hypothesisId": "A", "location": "memory.py:73", "message": "Starting cleanup of memory entries", "data": {"total_entries_before": total_entries_before, "memory_file": str(self.path)}, "timestamp": __import__("time").time() * 1000}) + "\n")
        except Exception:
            pass
        # #endregion
        cleaned_data = {}
        stale_count = 0
        for key, record_data in data.items():
            if not isinstance(record_data, dict):
                continue
            source_text = record_data.get("source_text", "").strip()
            translated_text = record_data.get("translated_text", "").strip()
            allow_long_entries = record_data.get("allow_long_entries", False)
            
            # Apply same filters as record() method
            # BUT: skip filters if allow_long_entries is True
            if not source_text or not translated_text:
                stale_count += 1
                continue
            
            MAX_MEMORY_ENTRY_LENGTH = 1000
            if not allow_long_entries and (len(source_text) > MAX_MEMORY_ENTRY_LENGTH or len(translated_text) > MAX_MEMORY_ENTRY_LENGTH):
                stale_count += 1
                continue
            
            placeholder_chars = source_text.count('_') + source_text.count('□') + source_text.count('☐') + source_text.count('☑')
            placeholder_ratio = placeholder_chars / len(source_text) if source_text else 0
            if not allow_long_entries and placeholder_ratio > 0.1:
                stale_count += 1
                continue
            
            non_whitespace_ratio = len(''.join(source_text.split())) / len(source_text) if source_text else 0
            if not allow_long_entries and non_whitespace_ratio < 0.3:
                stale_count += 1
                continue
            
            # Entry passed all filters, keep it
            cleaned_data[key] = record_data
        
        # Save cleaned data if stale entries were removed
        # #region agent log
        try:
            total_entries_after = len(cleaned_data)
            with open(log_path, "a") as f:
                f.write(json_module.dumps({"sessionId": "debug-session", "runId": "cleanup-check", "hypothesisId": "A", "location": "memory.py:106", "message": "Cleanup complete", "data": {"stale_count": stale_count, "total_entries_after": total_entries_after, "will_save": stale_count > 0}, "timestamp": __import__("time").time() * 1000}) + "\n")
        except Exception:
            pass
        # #endregion
        if stale_count > 0:
            logger.info(f"Cleaned {stale_count} stale entries from memory (long entries with placeholders)")
            data = cleaned_data
            # Write cleaned data back to file immediately
            try:
                cleaned_json = json.dumps(data, ensure_ascii=False, indent=2)
                self.path.write_text(cleaned_json, encoding="utf-8")
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json_module.dumps({"sessionId": "debug-session", "runId": "cleanup-check", "hypothesisId": "A", "location": "memory.py:118", "message": "Saved cleaned memory data", "data": {"entries_saved": len(data), "file_path": str(self.path)}, "timestamp": __import__("time").time() * 1000}) + "\n")
                except Exception:
                    pass
                # #endregion
            except Exception as e:
                logger.warning(f"Failed to save cleaned memory data: {e}")
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json_module.dumps({"sessionId": "debug-session", "runId": "cleanup-check", "hypothesisId": "A", "location": "memory.py:123", "message": "Failed to save cleaned memory", "data": {"error": str(e)}, "timestamp": __import__("time").time() * 1000}) + "\n")
                except Exception:
                    pass
                # #endregion
        
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
            # Restore the allow_long_entries flag if it exists
            self._allow_long_entries_flags[key] = payload.get("allow_long_entries", False)
            records_loaded += 1
        
        # Merge in new records from glossary seed file (only if they don't already exist)
        # This allows git updates to glossary/memory.json to add new records without overwriting runtime data
        # Apply same filters to seed file entries to prevent stale entries
        records_added_from_seed = 0
        if glossary_data:
            for key, payload in glossary_data.items():
                if key not in self._records:
                    source_text = payload.get("source_text", "").strip()
                    translated_text = payload.get("translated_text", "").strip()
                    
                    # Skip stale entries from seed file too
                    if not source_text or not translated_text:
                        continue
                    
                    MAX_MEMORY_ENTRY_LENGTH = 1000
                    if len(source_text) > MAX_MEMORY_ENTRY_LENGTH or len(translated_text) > MAX_MEMORY_ENTRY_LENGTH:
                        continue
                    
                    placeholder_chars = source_text.count('_') + source_text.count('□') + source_text.count('☐') + source_text.count('☑')
                    placeholder_ratio = placeholder_chars / len(source_text) if source_text else 0
                    if placeholder_ratio > 0.1:
                        continue
                    
                    non_whitespace_ratio = len(''.join(source_text.split())) / len(source_text) if source_text else 0
                    if non_whitespace_ratio < 0.3:
                        continue
                    
                    # Entry passed all filters, add it
                    record = TranslationRecord(
                        source_text=source_text,
                        translated_text=translated_text,
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
                "allow_long_entries": self._allow_long_entries_flags.get(key, False),
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

    def record(self, source_text: str, translated_text: str, source_lang: str, target_lang: str, allow_long_entries: bool = False) -> TranslationRecord | None:
        # Filter out entries that shouldn't be stored in memory:
        # 1. Very long entries (> 1000 chars) - likely entire document sections
        # 2. Entries with many placeholders/underscores - likely form fields
        # 3. Entries that are mostly placeholders or whitespace
        
        # #region agent log
        import json as json_module
        log_path = "/Users/enrico/workspace/translator/.cursor/debug.log"
        try:
            with open(log_path, "a") as f:
                f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:257", "message": "memory.record() called", "data": {"source_len": len(source_text), "translated_len": len(translated_text), "source_lang": source_lang, "target_lang": target_lang}, "timestamp": __import__("time").time() * 1000}) + "\n")
        except Exception:
            pass
        # #endregion
        
        source_stripped = source_text.strip()
        translated_stripped = translated_text.strip()
        
        # Skip empty entries
        if not source_stripped or not translated_stripped:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:272", "message": "Skipping empty entry", "data": {"source_empty": not source_stripped, "translated_empty": not translated_stripped}, "timestamp": __import__("time").time() * 1000}) + "\n")
            except Exception:
                pass
            # #endregion
            return None
        
        # Skip very long entries (likely document sections, not reusable phrases)
        # Exception: allow long entries when explicitly requested (e.g., entire document translations)
        MAX_MEMORY_ENTRY_LENGTH = 1000
        if not allow_long_entries and (len(source_stripped) > MAX_MEMORY_ENTRY_LENGTH or len(translated_stripped) > MAX_MEMORY_ENTRY_LENGTH):
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:278", "message": "Skipping entry: too long", "data": {"source_len": len(source_stripped), "translated_len": len(translated_stripped), "max_length": MAX_MEMORY_ENTRY_LENGTH}, "timestamp": __import__("time").time() * 1000}) + "\n")
            except Exception:
                pass
            # #endregion
            logger.debug(f"Skipping memory entry: too long ({len(source_stripped)}/{len(translated_stripped)} chars)")
            return None
        
        # Skip entries with too many placeholders/underscores (likely form fields)
        # Exception: allow placeholders when explicitly requested (e.g., entire document translations)
        placeholder_chars = source_stripped.count('_') + source_stripped.count('□') + source_stripped.count('☐') + source_stripped.count('☑')
        placeholder_ratio = placeholder_chars / len(source_stripped) if source_stripped else 0
        if not allow_long_entries and placeholder_ratio > 0.1:  # More than 10% placeholder characters
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:287", "message": "Skipping entry: too many placeholders", "data": {"placeholder_chars": placeholder_chars, "placeholder_ratio": placeholder_ratio, "threshold": 0.1}, "timestamp": __import__("time").time() * 1000}) + "\n")
            except Exception:
                pass
            # #endregion
            logger.debug(f"Skipping memory entry: too many placeholders (ratio: {placeholder_ratio:.2f})")
            return None
        
        # Skip entries that are mostly whitespace or separators
        # Exception: allow whitespace when explicitly requested (e.g., entire document translations)
        non_whitespace_ratio = len(''.join(source_stripped.split())) / len(source_stripped) if source_stripped else 0
        if not allow_long_entries and non_whitespace_ratio < 0.3:  # Less than 30% actual content
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:299", "message": "Skipping entry: too much whitespace", "data": {"non_whitespace_ratio": non_whitespace_ratio, "threshold": 0.3}, "timestamp": __import__("time").time() * 1000}) + "\n")
            except Exception:
                pass
            # #endregion
            logger.debug(f"Skipping memory entry: too much whitespace (non-whitespace ratio: {non_whitespace_ratio:.2f})")
            return None
        
        # Entry passed all filters, save it
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json_module.dumps({"sessionId": "debug-session", "runId": "memory-record", "hypothesisId": "C", "location": "memory.py:308", "message": "Saving memory entry (passed all filters)", "data": {"source_len": len(source_stripped), "translated_len": len(translated_stripped), "allow_long_entries": allow_long_entries}, "timestamp": __import__("time").time() * 1000}) + "\n")
        except Exception:
            pass
        # #endregion
        record = TranslationRecord(
            source_text=source_stripped,
            translated_text=translated_stripped,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        self._records[record.key] = record
        # Store the allow_long_entries flag separately (since TranslationRecord is frozen)
        self._allow_long_entries_flags[record.key] = allow_long_entries
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
