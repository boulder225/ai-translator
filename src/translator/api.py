from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .claude_client import ClaudeTranslator
from .processing import PDF_SUFFIX, translate_file_to_memory
from .settings import get_settings
from .terminology import Glossary, TranslationMemory

# Configure logging with both console and file handlers
def setup_logging():
    """Configure logging to write to both console and file."""
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (append mode)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    return log_file

# Setup logging on module import
log_file_path = setup_logging()
logger = logging.getLogger(__name__)
logger.info(f"Logging initialized. Log file: {log_file_path}")

app = FastAPI(title="Legal Translator API", version="0.1.0")

# Add middleware to log all requests and catch exceptions
@app.middleware("http")
async def log_requests_and_errors(request, call_next):
    # #region agent log
    import json
    import os
    request_start_time = time.time()
    # Use environment variable for log directory, fallback to /tmp in production
    log_dir = Path(os.getenv("DEBUG_LOG_DIR", "/tmp"))
    if log_dir.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_data = {
                "location": "api.py:middleware",
                "message": "Request received",
                "data": {
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "client": str(request.client) if request.client else None,
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "A,B,C"
            }
            with open(log_dir / "debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write request log: {e}")
    # #endregion
    
    try:
        response = await call_next(request)
        # #region agent log
        if log_dir.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            try:
                duration = time.time() - request_start_time
                log_data = {
                    "location": "api.py:middleware",
                    "message": "Request completed",
                    "data": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_seconds": duration,
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A,B,C"
                }
                with open(log_dir / "debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write completion log: {e}")
        # #endregion
        return response
    except Exception as e:
        # #region agent log
        if log_dir.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            try:
                log_data = {
                    "location": "api.py:middleware",
                    "message": "Request exception",
                    "data": {
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None,
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "B,C"
                }
                with open(log_dir / "debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception as log_err:
                logger.error(f"Failed to write error log: {log_err}")
        # #endregion
        logger.error(f"Unhandled exception in request: {e}", exc_info=True)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"https://.*\.ngrok\.(io|app|free\.app)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage - each job is completely isolated
translation_jobs: dict[str, dict] = {}

# Request tracking to detect duplicates
request_log: list[dict] = []

JOB_NOT_FOUND = "Job not found"


class TranslationStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    current_paragraph: Optional[int] = None
    total_paragraphs: Optional[int] = None
    error: Optional[str] = None
    pdf_size: Optional[int] = None  # Size of PDF in bytes (in memory)
    original_text: Optional[list[str]] = None  # Original paragraphs
    translated_text: Optional[list[str]] = None  # Translated paragraphs
    report: Optional[dict] = None


def _load_glossary(glossary_path: Path | None, source_lang: str, target_lang: str) -> Glossary | None:
    if glossary_path and glossary_path.exists():
        return Glossary.from_csv(glossary_path, source_lang=source_lang, target_lang=target_lang, name=glossary_path.stem)
    return None


def find_glossary_files() -> list[Path]:
    # #region agent log
    import json
    import os
    log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
    try:
        if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "api.py:find_glossary_files",
                    "message": "Finding glossary files",
                    "data": {
                        "cwd": str(Path.cwd()),
                        "search_dirs": ["glossary", "tests/docs"]
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A,B,C"
                }) + "\n")
    except Exception as e:
        pass
    # #endregion
    glossaries = []
    for dir_path in [Path("glossary"), Path("tests/docs")]:
        # #region agent log
        try:
            if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "location": "api.py:find_glossary_files",
                        "message": "Checking directory",
                        "data": {
                            "dir_path": str(dir_path),
                            "exists": dir_path.exists(),
                            "absolute": str(dir_path.resolve())
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A,B,C"
                    }) + "\n")
            logger.info(f"[DEBUG] Checking dir_path={dir_path}, exists={dir_path.exists()}, absolute={dir_path.resolve()}")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to log directory check: {e}")
        # #endregion
        if dir_path.exists():
            found = list(dir_path.glob("*.csv"))
            # #region agent log
            try:
                if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
                    with open(log_path, "a") as f:
                        f.write(json.dumps({
                            "location": "api.py:find_glossary_files",
                            "message": "Found CSV files in directory",
                            "data": {
                                "dir_path": str(dir_path),
                                "found_files": [str(f) for f in found]
                            },
                            "timestamp": int(time.time() * 1000),
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A,B,C"
                        }) + "\n")
            except Exception:
                pass
            # #endregion
            glossaries.extend(found)
    result = sorted(set(glossaries))
    # #region agent log
    try:
        if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "api.py:find_glossary_files",
                    "message": "Returning glossary files",
                    "data": {
                        "total_found": len(result),
                        "files": [str(f) for f in result]
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A,B,C"
                }) + "\n")
            logger.info(f"[DEBUG] Returning {len(result)} glossary files: {[str(f) for f in result]}")
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to log return: {e}")
    # #endregion
    return result


def detect_language_from_file(file_path: Path) -> str:
    """Detect language from a document file."""
    try:
        from langdetect import detect_langs, LangDetectException
    except ImportError:
        logger.warning("langdetect not available, falling back to default language")
        return "fr"
    
    try:
        # Extract text from file
        text = ""
        if file_path.suffix.lower() == ".docx":
            from docx import Document
            doc = Document(file_path)
            text = "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
        elif file_path.suffix.lower() == ".pdf":
            import pdfplumber
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
            text = "\n\n".join(text_parts)
        elif file_path.suffix.lower() == ".txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        if not text or len(text.strip()) < 50:
            logger.warning(f"Not enough text to detect language (got {len(text.strip())} chars)")
            return "fr"
        
        # Use more text for better accuracy (langdetect works better with more text)
        # Use up to 5000 characters for better detection accuracy
        sample_text = text[:5000] if len(text) > 5000 else text
        
        # Get language probabilities
        languages = detect_langs(sample_text)
        
        # Map langdetect codes to our language codes
        lang_map = {
            "fr": "fr",  # French
            "de": "de",  # German
            "it": "it",  # Italian
            "en": "en",  # English
        }
        
        # Get the most probable language that we support
        for lang_obj in languages:
            detected_code = lang_obj.lang
            if detected_code in lang_map:
                detected = lang_map[detected_code]
                logger.info(f"Detected language: {detected_code} (prob: {lang_obj.prob:.2f}) -> {detected}")
                return detected
        
        # If none of the detected languages are in our map, use the most probable one
        # and log a warning
        if languages:
            best_match = languages[0].lang
            logger.warning(f"Detected language '{best_match}' not in supported languages, defaulting to 'fr'")
            logger.info(f"All detected languages: {[(l.lang, l.prob) for l in languages[:5]]}")
        
        return "fr"
        
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}, using default 'fr'")
        return "fr"
    except Exception as e:
        logger.error(f"Error detecting language: {e}", exc_info=True)
        return "fr"


def _run_translation(job_id: str) -> None:
    """
    Run translation in a completely isolated context.
    All data comes from job storage, no closure variables.
    """
    try:
        # Get job data from storage
        job = translation_jobs.get(job_id)
        if not job:
            logger.error(f"[TRANSLATION {job_id}] Job not found in storage")
            return
        
        logger.info("=" * 80)
        logger.info(f"[TRANSLATION {job_id}] ===== STARTING TRANSLATION THREAD =====")
        logger.info(f"[TRANSLATION {job_id}] Job data from storage:")
        logger.info(f"[TRANSLATION {job_id}]   - File hash: {job.get('file_hash', 'MISSING')}")
        logger.info(f"[TRANSLATION {job_id}]   - Input path: {job.get('input_path', 'MISSING')}")
        logger.info(f"[TRANSLATION {job_id}]   - Source: {job.get('source_lang')} -> Target: {job.get('target_lang')}")
        
        job["status"] = "in_progress"
        
        # Extract all data from job storage
        input_file_path = Path(job["input_path"])
        expected_hash = job["file_hash"]
        source_lang = job["source_lang"]
        target_lang = job["target_lang"]
        glossary_path_str = job.get("glossary_path")
        skip_memory = job.get("skip_memory", False)  # Default to False: use memory by default
        custom_prompt = job.get("custom_prompt")
        
        # Verify input file exists and hash matches
        if not input_file_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
            # Read and verify file content
            logger.info(f"Job {job_id}: [FILE VERIFICATION] Opening file: {input_file_path}")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] File absolute path: {input_file_path.resolve()}")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] File exists: {input_file_path.exists()}")
            
            with open(input_file_path, 'rb') as f:
                file_content = f.read()
                actual_hash = hashlib.md5(file_content).hexdigest()
            
            logger.info(f"Job {job_id}: [FILE VERIFICATION] Read {len(file_content):,} bytes from file")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] Expected hash: {expected_hash}")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] Actual hash: {actual_hash}")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] First 100 bytes: {file_content[:100]}")
            
            if actual_hash != expected_hash:
                logger.error(f"Job {job_id}: [FILE VERIFICATION] HASH MISMATCH!")
                logger.error(f"Job {job_id}: [FILE VERIFICATION] Expected: {expected_hash[:16]}...")
                logger.error(f"Job {job_id}: [FILE VERIFICATION] Got: {actual_hash[:16]}...")
                raise ValueError(f"File hash mismatch! Expected {expected_hash[:16]}..., got {actual_hash[:16]}...")
            
            logger.info(f"Job {job_id}: [FILE VERIFICATION] Hash verified successfully")
            logger.info(f"Job {job_id}: [FILE VERIFICATION] File: {input_file_path.name}, Size: {len(file_content):,} bytes")
        
        # Create completely isolated temporary directory for this job
        job_temp_dir = tempfile.mkdtemp(prefix=f"translation_{job_id}_")
        job["temp_dir"] = job_temp_dir
        logger.info(f"Job {job_id}: Created isolated temp directory: {job_temp_dir}")
        
        try:
            # No output file needed - we'll store PDF in memory
            
            # Load glossary (loaded fresh from file for each translation - no restart needed!)
            glossary = None
            if glossary_path_str:
                glossary_path_obj = Path(glossary_path_str)
                logger.info(f"Job {job_id}: Loading glossary from {glossary_path_obj} (file will be read fresh)")
                glossary = _load_glossary(glossary_path_obj, source_lang, target_lang)
                if glossary:
                    logger.info(f"Job {job_id}: Loaded glossary '{glossary.name}' with {len(glossary)} entries")
                else:
                    logger.warning(f"Job {job_id}: Failed to load glossary from {glossary_path_obj}")
            
            # Use shared translation memory (persisted across jobs)
            settings = get_settings()
            memory_file = settings.data_root / "memory.json"
            import os
            logger.info(f"[DEBUG] Job {job_id}: Memory file path check - path={memory_file}, absolute={memory_file.resolve()}, data_root={settings.data_root}, data_root_exists={settings.data_root.exists()}, data_root_writable={os.access(settings.data_root, os.W_OK) if settings.data_root.exists() else False}")
            # #region agent log
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "location": "api.py:translate_job",
                        "message": "Loading translation memory",
                        "data": {
                            "memory_file": str(memory_file),
                            "memory_file_exists": memory_file.exists(),
                            "data_root": str(settings.data_root),
                            "skip_memory": skip_memory
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B"
                    }) + "\n")
            except Exception:
                pass
            logger.info(f"[DEBUG] Job {job_id}: Loading translation memory: file={memory_file}, exists={memory_file.exists()}, skip_memory={skip_memory}")
            # #endregion
            memory = TranslationMemory(memory_file)
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "location": "api.py:translate_job",
                        "message": "Translation memory loaded",
                        "data": {
                            "memory_file": str(memory_file),
                            "records_count": len(memory),
                            "skip_memory": skip_memory
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B"
                    }) + "\n")
            except Exception:
                pass
            logger.info(f"[DEBUG] Job {job_id}: Translation memory loaded: records={len(memory)}, skip_memory={skip_memory}")
            # #endregion
            logger.info(f"Job {job_id}: Using shared translation memory from {memory_file}")
            logger.info(f"Job {job_id}: Memory contains {len(memory)} existing records")
            logger.info(f"[DEBUG] Job {job_id}: skip_memory={skip_memory}, memory_records={len(memory)}")
            
            # Extract translation pairs from reference document if provided
            reference_doc_pairs = {}
            reference_doc_path_str = job.get("reference_doc_path")
            if reference_doc_path_str:
                reference_doc_path_obj = Path(reference_doc_path_str)
                if reference_doc_path_obj.exists():
                    logger.info(f"Job {job_id}: Extracting translation pairs from reference document...")
                    from .processing import extract_translation_pairs_from_reference_doc
                    # Create translator temporarily for extraction
                    temp_translator = ClaudeTranslator(
                        api_key=settings.anthropic_api_key,
                        dry_run=False,
                    )
                    reference_doc_pairs = extract_translation_pairs_from_reference_doc(
                        reference_doc_path=reference_doc_path_obj,
                        translator=temp_translator,
                        source_lang=source_lang,
                        target_lang=target_lang,
                    )
                    logger.info(f"Job {job_id}: Extracted {len(reference_doc_pairs)} translation pairs from reference doc")
                else:
                    logger.warning(f"Job {job_id}: Reference doc path provided but file not found: {reference_doc_path_obj}")
            
            # Create translator
            translator = ClaudeTranslator(
                api_key=settings.anthropic_api_key,
                dry_run=False,
                custom_prompt_template=custom_prompt,
            )
            
            # Progress callback
            def update_progress(idx: int, total: int, length: int):
                if job.get("cancelled", False):
                    logger.info(f"Job {job_id}: Cancellation detected")
                    raise KeyboardInterrupt("Translation cancelled")
                
                job["current_paragraph"] = idx
                job["total_paragraphs"] = total
                job["progress"] = idx / total if total > 0 else 0.0
            
            # Run translation - verify file again before calling translate_file_to_memory
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] About to call translate_file_to_memory")
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Input path: {input_file_path}")
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Input path absolute: {input_file_path.resolve()}")
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Input file exists: {input_file_path.exists()}")
            
            # Verify file one more time right before translation
            with open(input_file_path, 'rb') as verify_f:
                verify_content = verify_f.read()
                verify_hash = hashlib.md5(verify_content).hexdigest()
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Final verification - Hash: {verify_hash}")
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Expected hash: {expected_hash}")
            if verify_hash != expected_hash:
                logger.error(f"Job {job_id}: [PRE-TRANSLATE] FILE CHANGED BEFORE TRANSLATION!")
                raise ValueError(f"File changed! Expected {expected_hash[:16]}..., got {verify_hash[:16]}...")
            
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] File verified, calling translate_file_to_memory")
            logger.info(f"Job {job_id}: [PRE-TRANSLATE] Source lang: {source_lang}, Target lang: {target_lang}")
            
            # Read original text before translation (using the same function that translate_file_to_memory uses)
            # Import here to avoid circular imports
            import sys
            from pathlib import Path as PathLib
            if input_file_path.suffix.lower() == ".docx":
                from docx import Document
                doc = Document(input_file_path)
                original_text = "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
            elif input_file_path.suffix.lower() == ".pdf":
                import pdfplumber
                text_parts = []
                with pdfplumber.open(input_file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text)
                original_text = "\n\n".join(text_parts)
            elif input_file_path.suffix.lower() == ".txt":
                with open(input_file_path, 'r', encoding='utf-8') as f:
                    original_text = f.read()
            else:
                original_text = ""
            
            # Split original text into paragraphs for display
            original_paragraphs = [p.strip() for p in original_text.split("\n\n") if p.strip()]
            if not original_paragraphs:
                original_paragraphs = [p.strip() for p in original_text.split("\n") if p.strip()]
            if not original_paragraphs:
                original_paragraphs = [original_text] if original_text else []
            
            # Store original text in job for later use
            job["original_text"] = original_paragraphs
            logger.info(f"Job {job_id}: Stored {len(original_paragraphs)} original paragraphs")
            
            pdf_bytes, translated_paragraphs, report = translate_file_to_memory(
                input_path=input_file_path,
                glossary=glossary,
                memory=memory,
                translator=translator,
                source_lang=source_lang,
                target_lang=target_lang,
                progress_callback=update_progress,
                skip_memory=skip_memory,
                reference_doc_pairs=reference_doc_pairs if reference_doc_pairs else None,
            )
            
            logger.info(f"[TRANSLATION {job_id}] Translation complete")
            logger.info(f"[TRANSLATION {job_id}] PDF generated in memory: {len(pdf_bytes):,} bytes")
            logger.info(f"[TRANSLATION {job_id}] Original paragraphs: {len(original_paragraphs)}")
            logger.info(f"[TRANSLATION {job_id}] Translated paragraphs: {len(translated_paragraphs)}")
            
            # Update job status - CRITICAL: Check if job was overwritten
            current_job = translation_jobs.get(job_id)
            if current_job and current_job.get("file_hash") != expected_hash:
                logger.error(f"[TRANSLATION {job_id}] ⚠️  JOB WAS OVERWRITTEN!")
                logger.error(f"[TRANSLATION {job_id}] Expected hash: {expected_hash}")
                logger.error(f"[TRANSLATION {job_id}] Current hash: {current_job.get('file_hash')}")
                raise ValueError("Job was overwritten by another request during translation")
            
            # Store PDF bytes, original text, and translated text in memory (not on filesystem)
            # Original text was already stored in job above
            # Extract applied glossary and memory terms from report
            applied_glossary_terms = report.get("applied_glossary_terms", [])
            applied_memory_terms = report.get("applied_memory_terms", [])
            
            job.update({
                "status": "completed",
                "progress": 1.0,
                "pdf_bytes": pdf_bytes,  # Store PDF in memory
                "pdf_size": len(pdf_bytes),
                "translated_text": translated_paragraphs,  # Store translated paragraphs (with <glossary> and <memory> markers)
                "original_text": job.get("original_text"),  # Store original text for side-by-side comparison
                "applied_glossary_terms": applied_glossary_terms,  # Store glossary terms that were applied
                "applied_memory_terms": applied_memory_terms,  # Store memory terms that were applied
                "report": report,
                "completed_at": time.time(),  # Track when completed
            })
            
            logger.info(f"[TRANSLATION {job_id}] Status updated to completed")
            logger.info(f"[TRANSLATION {job_id}] Final job hash: {job.get('file_hash')}")
            logger.info(f"[TRANSLATION {job_id}] ===== TRANSLATION COMPLETE =====")
            logger.info("=" * 80)
            
        finally:
            # Cleanup: remove input file immediately after translation
            if input_file_path.exists():
                try:
                    input_file_path.unlink()
                    logger.info(f"Job {job_id}: Cleaned up input file")
                except Exception as e:
                    logger.warning(f"Job {job_id}: Failed to cleanup input file: {e}")
            
    except KeyboardInterrupt:
        logger.info(f"Job {job_id}: Translation cancelled")
        job = translation_jobs.get(job_id, {})
        job.update({
            "status": "cancelled",
            "error": "Translation cancelled by user",
        })
    except Exception as e:
        logger.error(f"Job {job_id}: Translation failed: {e}", exc_info=True)
        job = translation_jobs.get(job_id, {})
        job.update({
            "status": "failed",
            "error": str(e),
        })


@app.get("/")
async def root():
    return {"message": "Legal Translator API", "version": "0.1.0"}


@app.get("/api/glossaries")
async def list_glossaries():
    return {"glossaries": [str(g) for g in find_glossary_files()]}


@app.get("/api/glossary/{glossary_name}/content")
async def get_glossary_content(glossary_name: str):
    """Get the content of a glossary file."""
    import csv
    
    # #region agent log
    import json
    import os
    log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
    try:
        if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "api.py:get_glossary_content",
                    "message": "Request received",
                    "data": {
                        "glossary_name": glossary_name,
                        "cwd": str(Path.cwd())
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }) + "\n")
            logger.info(f"[DEBUG] get_glossary_content: glossary_name={glossary_name}, cwd={Path.cwd()}")
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to log request: {e}")
    # #endregion
    
    # Find the glossary file
    glossary_files = find_glossary_files()
    # #region agent log
    try:
        if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "api.py:get_glossary_content",
                    "message": "Found glossary files",
                    "data": {
                        "glossary_name": glossary_name,
                        "found_files": [str(g) for g in glossary_files],
                        "file_stems": [g.stem for g in glossary_files],
                        "file_names": [g.name for g in glossary_files]
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }) + "\n")
    except Exception:
        pass
    # #endregion
    glossary_path = None
    for g in glossary_files:
        # #region agent log
        try:
            if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
                with open(log_path, "a") as f:
                    f.write(json.dumps({
                        "location": "api.py:get_glossary_content",
                        "message": "Matching glossary file",
                        "data": {
                            "glossary_name": glossary_name,
                            "file_path": str(g),
                            "file_stem": g.stem,
                            "file_name": g.name,
                            "stem_match": g.stem == glossary_name,
                            "name_match": g.name == glossary_name
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "D"
                    }) + "\n")
                logger.info(f"[DEBUG] Matching: glossary_name={glossary_name}, file={g}, stem={g.stem}, name={g.name}, stem_match={g.stem == glossary_name}, name_match={g.name == glossary_name}")
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to log match: {e}")
        # #endregion
        if g.stem == glossary_name or g.name == glossary_name:
            glossary_path = g
            break
    
    # #region agent log
    try:
        if log_path.parent.exists() or os.getenv("DEBUG_ENABLED", "false").lower() == "true":
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "location": "api.py:get_glossary_content",
                    "message": "Glossary path resolution",
                    "data": {
                        "glossary_name": glossary_name,
                        "glossary_path": str(glossary_path) if glossary_path else None,
                        "path_exists": glossary_path.exists() if glossary_path else False,
                        "path_absolute": str(glossary_path.resolve()) if glossary_path else None
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                    }) + "\n")
            logger.info(f"[DEBUG] Glossary path resolution: glossary_name={glossary_name}, glossary_path={glossary_path}, exists={glossary_path.exists() if glossary_path else False}")
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to log path resolution: {e}")
    # #endregion
    
    if not glossary_path or not glossary_path.exists():
        logger.error(f"[DEBUG] Glossary '{glossary_name}' not found. Found files: {[str(g) for g in glossary_files]}")
        raise HTTPException(status_code=404, detail=f"Glossary '{glossary_name}' not found")
    
    # Read and return glossary content
    entries = []
    try:
        with glossary_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not {"term", "translation"}.issubset(reader.fieldnames or []):
                raise HTTPException(status_code=400, detail="Invalid glossary format")
            for row in reader:
                term = (row.get("term") or "").strip()
                translation = (row.get("translation") or "").strip()
                if term and translation:
                    entries.append({
                        "term": term,
                        "translation": translation,
                        "context": (row.get("context") or "").strip() or None
                    })
    except Exception as e:
        logger.error(f"Error reading glossary {glossary_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading glossary: {str(e)}")
    
    return {
        "name": glossary_path.stem,
        "path": str(glossary_path),
        "entries": entries,
        "total": len(entries)
    }


@app.get("/api/prompt")
async def get_prompt():
    """Get the current translation prompt template."""
    try:
        from .claude_client import _load_prompt_template
        prompt = _load_prompt_template()
        return {"prompt": prompt}
    except Exception as e:
        logger.error(f"Error in get_prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load prompt: {str(e)}")


@app.post("/api/detect-language")
async def detect_language(file: UploadFile = File(...)):
    """Detect the language of an uploaded document."""
    import tempfile
    
    try:
        # Save uploaded file temporarily
        file_content = await file.read()
        file_suffix = Path(file.filename).suffix if file.filename else ".pdf"
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix)
        temp_file.write(file_content)
        temp_file.close()
        temp_path = Path(temp_file.name)
        
        try:
            detected_lang = detect_language_from_file(temp_path)
            return {"detected_language": detected_lang}
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
    except Exception as e:
        logger.error(f"Language detection failed: {e}", exc_info=True)
        # Return default language on error
        return {"detected_language": "fr"}


@app.post("/api/translate", status_code=status.HTTP_202_ACCEPTED)
async def start_translation(
    file: UploadFile = File(...),
    source_lang: str = Form("fr"),
    target_lang: str = Form("it"),
    use_glossary: bool = Form(False),
    skip_memory: bool = Form(False),  # Default to False: use memory by default
    custom_prompt: Optional[str] = Form(None),
    reference_doc: Optional[UploadFile] = File(None),
):
    """Start translation job. Each job is completely isolated."""
    import time
    
    # Track this request
    request_timestamp = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    logger.info("=" * 80)
    logger.info(f"[REQUEST {request_id}] ===== NEW TRANSLATION REQUEST =====")
    logger.info(f"[REQUEST {request_id}] Timestamp: {request_timestamp}")
    logger.info(f"[REQUEST {request_id}] File name: {file.filename}")
    logger.info(f"[REQUEST {request_id}] Source: {source_lang} -> Target: {target_lang}")
    
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    
    # Read uploaded file content
    file_content = await file.read()
    file_hash = hashlib.md5(file_content).hexdigest()
    file_suffix = Path(file.filename).suffix if file.filename else ".pdf"
    
    logger.info(f"[REQUEST {request_id}] File size: {len(file_content):,} bytes")
    logger.info(f"[REQUEST {request_id}] File hash: {file_hash}")
    logger.info(f"[REQUEST {request_id}] First 200 bytes: {file_content[:200]}")
    logger.info(f"[REQUEST {request_id}] Use glossary: {use_glossary}")
    # #region agent log
    import json
    import os
    log_path = Path("/Users/enrico/workspace/translator/.cursor/debug.log")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "location": "api.py:start_translation",
                "message": "skip_memory parameter received",
                "data": {
                    "skip_memory": skip_memory,
                    "skip_memory_type": type(skip_memory).__name__,
                    "source_lang": source_lang,
                    "target_lang": target_lang
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "A"
            }) + "\n")
        logger.info(f"[DEBUG] skip_memory={skip_memory} (type={type(skip_memory).__name__})")
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to log skip_memory: {e}")
    # #endregion
    logger.info(f"[REQUEST {request_id}] Skip memory: {skip_memory}")
    
    # Determine glossary path - use default if enabled
    glossary_path = None
    if use_glossary:
        # Use default glossary: glossary/glossary.csv
        default_glossary = Path("glossary") / "glossary.csv"
        if default_glossary.exists():
            glossary_path = str(default_glossary)
            logger.info(f"[REQUEST {request_id}] Using default glossary: {glossary_path}")
        else:
            logger.warning(f"[REQUEST {request_id}] Glossary enabled but default file not found: {default_glossary}")
    
    # Check for duplicate requests with same file hash - only reject if there's an ACTIVE job
    # Allow re-translation of completed jobs (they will use memory)
    recent_requests = [r for r in request_log if time.time() - r["timestamp"] < 60]  # Last 60 seconds
    duplicate_requests = [r for r in recent_requests if r["file_hash"] == file_hash]
    
    if duplicate_requests:
        # Check if any of the duplicate requests have active jobs
        active_duplicates = []
        for dup in duplicate_requests:
            dup_job_id = dup.get('job_id')
            if dup_job_id and dup_job_id in translation_jobs:
                job_status = translation_jobs[dup_job_id].get("status", "unknown")
                if job_status in ["pending", "in_progress"]:
                    active_duplicates.append((dup, job_status))
        
        if active_duplicates:
            logger.warning(f"[REQUEST {request_id}] ⚠️  DUPLICATE REQUEST DETECTED!")
            logger.warning(f"[REQUEST {request_id}] Found {len(active_duplicates)} active jobs with same file hash:")
            for dup, status in active_duplicates:
                logger.warning(f"[REQUEST {request_id}]   - Request {dup['request_id']} at {dup['timestamp']}, job_id: {dup.get('job_id')}, status: {status}")
            logger.warning(f"[REQUEST {request_id}] Active translation in progress - REJECTING duplicate")
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate request detected. A translation with this file is already in progress."
            )
        else:
            # All duplicate requests are completed/failed - allow re-translation (will use memory)
            logger.info(f"[REQUEST {request_id}] Found {len(duplicate_requests)} recent requests with same hash, but all are completed")
            logger.info(f"[REQUEST {request_id}] Allowing re-translation - will check memory first")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    logger.info(f"[REQUEST {request_id}] Generated job_id: {job_id}")
    
    # Log this request
    request_log.append({
        "request_id": request_id,
        "job_id": job_id,
        "timestamp": request_timestamp,
        "file_hash": file_hash,
        "file_name": file.filename,
        "file_size": len(file_content),
    })
    
    # Keep only last 100 requests
    if len(request_log) > 100:
        request_log.pop(0)
    
    # Create unique temporary file for this job only
    # Use job_id in filename to ensure uniqueness
    temp_input = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=file_suffix,
        prefix=f"input_{job_id}_"
    )
    temp_input.write(file_content)
    temp_input.close()
    input_path = Path(temp_input.name)
    
    logger.info(f"Job {job_id}: Created isolated input file: {input_path.name}")
    logger.info(f"Job {job_id}: File hash: {file_hash[:16]}...")
    
    # Handle reference document if provided
    reference_doc_path = None
    if reference_doc:
        ref_doc_content = await reference_doc.read()
        ref_doc_suffix = Path(reference_doc.filename).suffix if reference_doc.filename else ".pdf"
        temp_ref = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ref_doc_suffix,
            prefix=f"reference_{job_id}_"
        )
        temp_ref.write(ref_doc_content)
        temp_ref.close()
        reference_doc_path = Path(temp_ref.name)
        logger.info(f"Job {job_id}: Reference document uploaded: {reference_doc_path.name}")
        logger.info(f"Job {job_id}: Reference doc size: {len(ref_doc_content):,} bytes")
    
    # Store ALL job data in job storage - no closure variables
    # CRITICAL: Check if job_id already exists (should never happen, but protect against it)
    if job_id in translation_jobs:
        logger.error(f"[REQUEST {request_id}] ⚠️  JOB ID COLLISION! Job {job_id} already exists!")
        logger.error(f"[REQUEST {request_id}] Existing job hash: {translation_jobs[job_id].get('file_hash')}")
        logger.error(f"[REQUEST {request_id}] New request hash: {file_hash}")
        raise HTTPException(status_code=500, detail="Job ID collision - please try again")
    
    translation_jobs[job_id] = {
        "status": "pending",
        "file_hash": file_hash,
        "input_path": str(input_path),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "glossary_path": glossary_path,
        "use_glossary": use_glossary,
        "skip_memory": skip_memory,
        "custom_prompt": custom_prompt,
        "reference_doc_path": str(reference_doc_path) if reference_doc_path else None,
        "progress": 0.0,
        "current_paragraph": 0,
        "total_paragraphs": 0,
        "cancelled": False,
        "request_id": request_id,  # Track which request created this job
        "created_at": request_timestamp,
    }
    
    logger.info(f"[REQUEST {request_id}] Job {job_id} stored in translation_jobs")
    logger.info(f"[REQUEST {request_id}] Total active jobs: {len([j for j in translation_jobs.values() if j.get('status') in ['pending', 'in_progress']])}")
    
    # Start translation thread - passes only job_id, reads everything from storage
    thread = threading.Thread(target=_run_translation, args=(job_id,), daemon=True)
    thread.start()
    
    logger.info(f"[REQUEST {request_id}] Job {job_id}: Translation thread started")
    logger.info(f"[REQUEST {request_id}] ===== REQUEST PROCESSING COMPLETE =====")
    logger.info("=" * 80)
    
    return {"job_id": job_id, "status": "pending"}


@app.get("/api/translate/{job_id}/status")
async def get_translation_status(job_id: str):
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    return TranslationStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        current_paragraph=job.get("current_paragraph"),
        total_paragraphs=job.get("total_paragraphs"),
        error=job.get("error"),
        pdf_size=job.get("pdf_size"),
        original_text=job.get("original_text"),
        translated_text=job.get("translated_text"),
        report=job.get("report"),
    )


@app.get("/api/translate/{job_id}/download")
async def download_translation(job_id: str):
    from fastapi.responses import Response
    
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Translation not completed")
    
    # Get PDF bytes from memory
    pdf_bytes = job.get("pdf_bytes")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF not found in memory")
    
    logger.info(f"[DOWNLOAD {job_id}] Serving PDF from memory: {len(pdf_bytes):,} bytes")
    
    # Generate filename
    source_lang = job.get("source_lang", "unknown")
    target_lang = job.get("target_lang", "unknown")
    filename = f"translated_{source_lang}_{target_lang}_{job_id[:8]}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        }
    )


@app.post("/api/translate/{job_id}/cancel")
async def cancel_translation(job_id: str):
    """Cancel an ongoing translation job."""
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    if job["status"] not in ["pending", "in_progress"]:
        raise HTTPException(status_code=400, detail="Translation cannot be cancelled")
    
    logger.info(f"Job {job_id}: Cancellation requested")
    job["cancelled"] = True
    
    return {"message": "Cancellation requested", "job_id": job_id}


@app.get("/api/translate/{job_id}/report")
async def get_translation_report(job_id: str):
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Translation not completed")
    
    return job.get("report", {})


@app.get("/api/translate/{job_id}/text")
async def get_translated_text(job_id: str):
    """Get translated text as plain text."""
    from fastapi.responses import Response
    
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Translation not completed")
    
    translated_paragraphs = job.get("translated_text")
    if not translated_paragraphs:
        raise HTTPException(status_code=404, detail="Translated text not found")
    
    # Join paragraphs with double newlines
    text_content = "\n\n".join(translated_paragraphs)
    
    return Response(
        content=text_content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="translated_{job_id[:8]}.txt"',
        }
    )


@app.get("/api/memory/export")
async def export_memory():
    """
    Export translation memory as JSON file.
    
    IMPORTANT: DigitalOcean App Platform uses ephemeral storage.
    Runtime memory is LOST on redeploy. Export this file before redeploying
    and merge it back into glossary/memory.json if you want to preserve it.
    """
    settings = get_settings()
    memory_file = settings.data_root / "memory.json"
    
    if not memory_file.exists():
        raise HTTPException(status_code=404, detail="Memory file not found")
    
    try:
        memory = TranslationMemory(memory_file)
        return FileResponse(
            path=str(memory_file),
            filename="memory.json",
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=memory.json",
                "X-Memory-Records": str(len(memory)),
            }
        )
    except Exception as e:
        logger.error(f"Error exporting memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export memory: {str(e)}")
