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
        logger.info(f"[DEBUG] TranslationMemory.__init__() - path={self.path}, absolute={self.path.resolve()}")
        self._load()

    def _load(self) -> None:
        glossary_memory = self.path.parent.parent / "glossary" / "memory.json"
        
        # Load glossary seed file for merging (if it exists)
        glossary_data = {}
        if glossary_memory.exists():
            try:
                glossary_raw = glossary_memory.read_text(encoding="utf-8")
                glossary_data = json.loads(glossary_raw or "{}")
                logger.info(f"[DEBUG] memory._load() - Found seed file {glossary_memory} with {len(glossary_data)} records")
            except Exception as e:
                logger.warning(f"[DEBUG] memory._load() - Failed to read glossary seed file: {e}")
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
                    logger.info(f"[DEBUG] memory._load() - Initialized memory file from {glossary_memory} to {self.path}")
                except Exception as e:
                    logger.warning(f"[DEBUG] memory._load() - Failed to copy from glossary: {e}, creating empty file")
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text("{}", encoding="utf-8")
                    logger.info(f"[DEBUG] memory._load() - Created empty memory file: {self.path}")
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text("{}", encoding="utf-8")
                logger.info(f"[DEBUG] memory._load() - Created empty memory file: {self.path}")
        else:
            # Runtime memory exists: will merge in any new records from glossary seed file below
            logger.info(f"[DEBUG] memory._load() - Runtime memory file exists, will merge with seed file if needed")
        
        # Load runtime memory file
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            logger.error(f"[DEBUG] memory._load() - JSON decode error: {exc}, path={self.path}, raw_preview={raw[:200]}")
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
            logger.info(f"[DEBUG] memory._load() - Merged {records_added_from_seed} new records from seed file, saving merged memory")
            self.save()
        
        logger.info(f"[DEBUG] memory._load() - Loaded {records_loaded} records from runtime file, added {records_added_from_seed} from seed, total={len(self._records)}, file_size={len(raw)} bytes")

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
        
        # Check file permissions before attempting to save
        file_exists = self.path.exists()
        parent_writable = os.access(self.path.parent, os.W_OK) if self.path.parent.exists() else False
        
        if file_exists:
            file_writable = os.access(self.path, os.W_OK)
            file_readable = os.access(self.path, os.R_OK)
            try:
                file_stat = self.path.stat()
                file_mode = stat.filemode(file_stat.st_mode)
            except Exception as e:
                file_stat = None
                file_mode = f"stat_error: {e}"
        else:
            file_writable = None
            file_readable = None
            file_stat = None
            file_mode = "file_not_exists"
        
        logger.info(f"[DEBUG] memory.save() - BEFORE SAVE: path={self.path}, exists={file_exists}, parent_writable={parent_writable}, file_writable={file_writable}, file_readable={file_readable}, file_mode={file_mode}, records={len(self._records)}")
        
        try:
            # Ensure parent directory exists and is writable
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not os.access(self.path.parent, os.W_OK):
                raise PermissionError(f"Parent directory is not writable: {self.path.parent}")
            
            # Ensure file is writable if it exists
            if self.path.exists():
                try:
                    os.chmod(self.path, 0o644)
                except Exception as e:
                    logger.warning(f"[DEBUG] memory.save() - Could not set file permissions: {e}")
            
            # Write the file
            json_content = json.dumps(serializable, ensure_ascii=False, indent=2)
            self.path.write_text(json_content, encoding="utf-8")
            
            # Ensure file is writable after write (in case it was created)
            try:
                os.chmod(self.path, 0o644)
            except Exception as e:
                logger.warning(f"[DEBUG] memory.save() - Could not set file permissions after write: {e}")
            
            # Verify write succeeded
            if not self.path.exists():
                raise IOError(f"File was not created after write: {self.path}")
            
            # Check file size
            file_size = self.path.stat().st_size
            logger.info(f"[DEBUG] memory.save() - SUCCESS: saved {len(self._records)} records to {self.path}, file_size={file_size} bytes, file_exists={self.path.exists()}")
        except PermissionError as e:
            logger.error(f"[DEBUG] memory.save() - PERMISSION ERROR: {e}, path={self.path}, parent_writable={parent_writable}, file_writable={file_writable}")
            raise
        except Exception as e:
            logger.error(f"[DEBUG] memory.save() - FAILED to save: {type(e).__name__}: {e}, path={self.path}, records={len(self._records)}")
            raise

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
        logger.info(f"[DEBUG] memory.record() - source_lang={source_lang}, target_lang={target_lang}, records_before={len(self._records)}, text_preview={source_text[:50]}...")
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
        logger.info(f"[DEBUG] memory.record() - saved: records_after={len(self._records)}, file_exists={self.path.exists()}")
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
        logger.info(f"[DEBUG] memory.get() - source_lang={source_lang}, target_lang={target_lang}, found={result is not None}, total_records={len(self._records)}, text_preview={source_text[:50]}...")
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











