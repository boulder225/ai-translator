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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Legal Translator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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
    glossaries = []
    for dir_path in [Path("glossary"), Path("tests/docs")]:
        if dir_path.exists():
            glossaries.extend(dir_path.glob("*.csv"))
    return sorted(set(glossaries))


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
        skip_memory = job.get("skip_memory", True)
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
            memory = TranslationMemory(memory_file)
            logger.info(f"Job {job_id}: Using shared translation memory from {memory_file}")
            logger.info(f"Job {job_id}: Memory contains {len(memory)} existing records")
            
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
            
            # #region agent log
            pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:16]
            log_data = {
                "location": "api.py:256",
                "message": "Storing PDF bytes in job",
                "data": {
                    "job_id": job_id,
                    "pdf_size": len(pdf_bytes),
                    "pdf_hash": pdf_hash,
                    "file_hash": expected_hash,
                    "status_before": job.get("status"),
                    "has_existing_pdf": "pdf_bytes" in job
                },
                "timestamp": int(time.time() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C,D"
            }
            try:
                with open("/Users/enrico/workspace/translator/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except:
                pass
            # #endregion
            
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


@app.get("/api/prompt")
async def get_prompt():
    """Get the current translation prompt template."""
    from .claude_client import _load_prompt_template
    prompt = _load_prompt_template()
    return {"prompt": prompt}


@app.post("/api/translate", status_code=status.HTTP_202_ACCEPTED)
async def start_translation(
    file: UploadFile = File(...),
    source_lang: str = Form("fr"),
    target_lang: str = Form("it"),
    use_glossary: bool = Form(False),
    skip_memory: bool = Form(True),
    custom_prompt: Optional[str] = Form(None),
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
    
    # #region agent log
    log_data = {
        "location": "api.py:486",
        "message": "Download request received",
        "data": {
            "job_id": job_id,
            "available_jobs": list(translation_jobs.keys()),
            "total_jobs": len(translation_jobs)
        },
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "A,B"
    }
    try:
        with open("/Users/enrico/workspace/translator/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
    except:
        pass
    # #endregion
    
    if job_id not in translation_jobs:
        # #region agent log
        log_data = {
            "location": "api.py:495",
            "message": "Job not found",
            "data": {"job_id": job_id, "available_jobs": list(translation_jobs.keys())},
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open("/Users/enrico/workspace/translator/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except:
            pass
        # #endregion
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    
    job = translation_jobs[job_id]
    if job["status"] != "completed":
        # #region agent log
        log_data = {
            "location": "api.py:500",
            "message": "Job not completed",
            "data": {"job_id": job_id, "status": job.get("status")},
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "B"
        }
        try:
            with open("/Users/enrico/workspace/translator/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except:
            pass
        # #endregion
        raise HTTPException(status_code=400, detail="Translation not completed")
    
    # Get PDF bytes from memory
    pdf_bytes = job.get("pdf_bytes")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF not found in memory")
    
    # #region agent log
    pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:16]
    log_data = {
        "location": "api.py:515",
        "message": "PDF bytes retrieved",
        "data": {
            "job_id": job_id,
            "pdf_size": len(pdf_bytes),
            "pdf_hash": pdf_hash,
            "file_hash": job.get("file_hash"),
            "created_at": job.get("created_at"),
            "source_lang": job.get("source_lang"),
            "target_lang": job.get("target_lang")
        },
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "C,D"
    }
    try:
        with open("/Users/enrico/workspace/translator/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
    except:
        pass
    # #endregion
    
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
