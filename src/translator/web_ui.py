from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from translator.claude_client import ClaudeTranslator
from translator.processing import PDF_SUFFIX, build_report_payload, translate_file
from translator.settings import get_settings
from translator.terminology import Glossary, TranslationMemory

# Configure logging to capture in Streamlit with detailed format
import sys
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),  # Always log to stderr for /tmp/streamlit.log
        logging.StreamHandler(),  # Also log to stdout
    ],
    force=True,  # Override any existing configuration
)

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Legal Translator",
    page_icon="📄",
    layout="wide",
)

# Initialize session state
if "translation_result" not in st.session_state:
    st.session_state.translation_result = None
if "translation_report" not in st.session_state:
    st.session_state.translation_report = None
if "translation_in_progress" not in st.session_state:
    st.session_state.translation_in_progress = False
if "translation_completed" not in st.session_state:
    st.session_state.translation_completed = False
if "translation_started" not in st.session_state:
    st.session_state.translation_started = False
if "translated_file_hash" not in st.session_state:
    st.session_state.translated_file_hash = None
if "current_file_hash_in_progress" not in st.session_state:
    st.session_state.current_file_hash_in_progress = None
if "progress_info" not in st.session_state:
    st.session_state.progress_info = None
if "current_chunk" not in st.session_state:
    st.session_state.current_chunk = None
if "current_status" not in st.session_state:
    st.session_state.current_status = None
if "live_translations" not in st.session_state:
    st.session_state.live_translations = []
if "preview_content" not in st.session_state:
    st.session_state.preview_content = None


def _load_glossary(glossary_path: Path | None, source_lang: str, target_lang: str) -> Glossary | None:
    if glossary_path is None:
        return None
    return Glossary.from_csv(glossary_path, source_lang=source_lang, target_lang=target_lang, name=glossary_path.stem)


# Progress callback is now defined inline in the translation section


def find_glossary_files() -> list[Path]:
    """Find all CSV glossary files in common locations."""
    glossaries = []
    # Check glossary folder
    glossary_dir = Path("glossary")
    if glossary_dir.exists():
        glossaries.extend(glossary_dir.glob("*.csv"))
    # Check tests/docs
    test_dir = Path("tests/docs")
    if test_dir.exists():
        glossaries.extend(test_dir.glob("*.csv"))
    return sorted(set(glossaries))


# Main UI
st.title("📄 Legal Document Translator")
st.markdown("Translate legal documents (DOCX/PDF/TXT) using Claude AI with glossary and translation memory support.")

# Prompt editor - moved to main area
st.divider()
st.header("✏️ Translation Prompt")

# Load default prompt from prompt.md
PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompt.md"
default_prompt = ""
if PROMPT_FILE.exists():
    default_prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()
else:
    default_prompt = (
        "You are a professional translator. Translate the provided text accurately, "
        "regardless of its context or document type. For legal, insurance, or administrative documents, "
        "use formal professional tone. For other document types, adapt the style appropriately. "
        "Always preserve numbering, respect capitalization, and never add commentary. "
        "Never refuse to translate - always provide a translation."
    )

# Initialize prompt in session state if not exists
if "custom_prompt" not in st.session_state:
    st.session_state.custom_prompt = default_prompt

# Prompt editor with reset button
col_reset, col_info = st.columns([1, 3])
with col_reset:
    if st.button("🔄 Reset to Default", use_container_width=True, key="reset_prompt_btn"):
        st.session_state.custom_prompt = default_prompt
        st.session_state.prompt_editor = default_prompt
with col_info:
    st.caption(f"📄 Loaded from: {PROMPT_FILE if PROMPT_FILE.exists() else 'default'}")

# Editable prompt text area - bound to session state
edited_prompt = st.text_area(
    "Edit Translation Prompt",
    value=st.session_state.custom_prompt,
    height=300,
    help="Customize the prompt sent to Claude for translation. This will be used for all translation requests.",
    key="prompt_editor",
)

# Sync prompt_editor with custom_prompt
if "prompt_editor" in st.session_state:
    st.session_state.custom_prompt = st.session_state.prompt_editor

# Show prompt stats
prompt_length = len(edited_prompt)
estimated_tokens = prompt_length // 4
st.caption(f"📊 Prompt length: {prompt_length:,} characters (~{estimated_tokens:,} tokens)")

st.divider()

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    settings = get_settings()
    
    # Language selection
    col1, col2 = st.columns(2)
    with col1:
        source_lang = st.selectbox(
            "Source Language",
            options=["fr", "de", "it", "en"],
            index=0 if settings.default_source_lang == "fr" else 1,
        )
    with col2:
        # Default to "it" (Italian)
        target_lang_options = ["it", "en", "de", "fr"]
        default_target_index = 0  # "it" is first
        target_lang = st.selectbox(
            "Target Language",
            options=target_lang_options,
            index=default_target_index,
        )
    
    # Glossary selection
    glossary_files = find_glossary_files()
    glossary_options = ["None"] + [str(g) for g in glossary_files]
    selected_glossary = st.selectbox(
        "Glossary (CSV)",
        options=glossary_options,
        help="Select a glossary file for terminology consistency",
    )
    glossary_path = None if selected_glossary == "None" else Path(selected_glossary)
    
    # Advanced options
    with st.expander("Advanced Options"):
        use_fast_model = st.checkbox(
            "Use Fast Model (Claude Haiku)",
            value=False,
            help="Use Claude Haiku for faster, cheaper translations (slightly lower quality)",
        )
        skip_memory = st.checkbox(
            "Skip Translation Memory",
            value=True,  # Default to True (on)
            help="Force translation even if exact/similar text exists in memory",
        )
        dry_run = st.checkbox(
            "Dry Run (No API Calls)",
            value=False,
            help="Test without making Claude API calls",
        )
    
    st.divider()
    st.markdown("**Status:**")
    if settings.anthropic_api_key:
        st.success("✅ API Key configured")
    else:
        st.error("❌ API Key missing - set ANTHROPIC_API_KEY in .env")


# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose a DOCX, PDF, or TXT file",
        type=["docx", "pdf", "txt"],
        help="Upload a legal document to translate",
    )

with col2:
    st.header("📊 Translation Stats")
    if st.session_state.translation_result:
        report = st.session_state.translation_report
        if report:
            stats = report.get("stats", {})
            st.metric("Paragraphs", stats.get("paragraphs_total", 0))
            st.metric("Model Calls", stats.get("model_calls", 0))
            st.metric("Memory Hits", stats.get("reused_from_memory", 0))
            st.metric("Glossary Matches", stats.get("glossary_matches", 0))
            if "duration_seconds" in report:
                st.metric("Duration", f"{report['duration_seconds']:.1f}s")

# Translation section
if uploaded_file is not None:
    st.divider()
    
    # Calculate file hash FIRST to prevent retranslating the same file
    file_content = uploaded_file.getvalue()
    file_hash = hashlib.md5(file_content).hexdigest()
    uploaded_file.seek(0)  # Reset file pointer
    
    # CRITICAL: Check if translation is already in progress for THIS file
    # If so, show progress and STOP immediately to prevent reruns
    current_file_hash_in_progress = st.session_state.get("current_file_hash_in_progress")
    translation_in_progress = st.session_state.get("translation_in_progress", False)
    translation_completed = st.session_state.get("translation_completed", False)
    translated_file_hash = st.session_state.get("translated_file_hash")
    
    # If this exact file is already completed, show results and STOP
    if translation_completed and translated_file_hash == file_hash:
        st.success("✅ This file has already been translated. Results are shown below.")
        # Results section will display below - stop here to prevent any translation code
        st.stop()
    
    # If translation is in progress for THIS file, show progress and STOP
    if translation_in_progress and current_file_hash_in_progress == file_hash:
        # Translation is in progress for this file - show progress and STOP
        st.info("🔄 Translation in progress... Please wait.")
        # Display progress if available
        if "progress_info" in st.session_state and st.session_state.progress_info:
            prog_info = st.session_state.progress_info
            st.progress(prog_info["progress"], text=f"Paragraph {prog_info['idx']}/{prog_info['total']}")
        if "preview_content" in st.session_state and st.session_state.preview_content:
            st.markdown(st.session_state.preview_content)
        st.stop()  # CRITICAL: Stop execution to prevent reruns
    
    # Check if this file has already been translated
    already_translated = (
        st.session_state.get("translated_file_hash") == file_hash and
        st.session_state.get("translation_completed", False) and
        st.session_state.get("translation_result") is not None
    )
    
    # Display file info
    if uploaded_file.name.endswith(".pdf"):
        file_type = "PDF"
    elif uploaded_file.name.endswith(".txt"):
        file_type = "TXT"
    else:
        file_type = "DOCX"
    st.info(f"📄 **File:** {uploaded_file.name} ({file_type}, {uploaded_file.size:,} bytes)")
    
    # Translate button - disabled if in progress OR already completed for this file
    translate_button = st.button(
        "🚀 Translate Document", 
        type="primary", 
        use_container_width=True, 
        disabled=(translation_in_progress or already_translated),
        key=f"translate_btn_{file_hash[:8]}"  # Unique key per file
    )
    
    # Show message if file already translated
    if already_translated:
        st.success("✅ This file has already been translated. Results are shown below.")
        # Show existing results and STOP
        if st.session_state.get("translation_result"):
            st.stop()
    
    # ONLY execute translation if button was clicked AND file not already translated
    if not translate_button:
        # Button not clicked - show UI and stop
        if already_translated:
            st.stop()
        else:
            st.info("👆 Click the button above to start translation.")
            st.stop()
    
    # Button was clicked - proceed with translation
    # Double-check all conditions before starting
    if (st.session_state.get("translation_in_progress", False) or 
        st.session_state.get("translation_completed", False) or
        already_translated):
        st.warning("⚠️ Translation already in progress or completed. Please wait.")
        st.stop()
    
    # Set flags IMMEDIATELY to prevent reruns
    st.session_state.translation_in_progress = True
    st.session_state.translation_started = True
    st.session_state.current_file_hash_in_progress = file_hash
    st.session_state.translation_completed = False
    st.session_state.translated_file_hash = None
    
    logger.info(f"Starting translation for file: {uploaded_file.name} (hash: {file_hash[:8]}...)")
    
    # Clear previous progress tracking
    st.session_state.progress_info = None
    st.session_state.current_chunk = None
    st.session_state.current_status = None
    st.session_state.live_translations = []
    st.session_state.preview_content = None
    
    if not settings.anthropic_api_key and not dry_run:
        st.error("❌ API Key not configured. Please set ANTHROPIC_API_KEY in your .env file.")
        st.session_state.translation_in_progress = False
        st.stop()
    
    # Save uploaded file to temp location
    logger.info(f"Saving uploaded file to temporary location...")
    logger.debug(f"File size: {uploaded_file.size:,} bytes")
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_input_path = Path(tmp_file.name)
    logger.info(f"File saved to: {tmp_input_path}")
    
    try:
        # Prepare translation
        output_suffix = f".{target_lang}{PDF_SUFFIX}"
        output_name = Path(uploaded_file.name).stem + output_suffix
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=output_suffix) as tmp_output:
            tmp_output_path = Path(tmp_output.name)
        
        # Load glossary and memory
        glossary = _load_glossary(glossary_path, source_lang, target_lang) if glossary_path else None
        memory_path = settings.data_root / "memory.json"
        memory = TranslationMemory(memory_path)
        # Use fast model if requested
        translator_kwargs = {
            "api_key": settings.anthropic_api_key,
            "dry_run": dry_run,
            "custom_prompt_template": st.session_state.get("custom_prompt", None),
        }
        if use_fast_model:
            translator_kwargs["model"] = "claude-haiku-4-5-20251001"
        # If not using fast model, don't pass model parameter (uses default)
        translator = ClaudeTranslator(**translator_kwargs)
        
        # Initialize session state for live updates
        if "translated_paragraphs" not in st.session_state:
            st.session_state.translated_paragraphs = []
        if "current_status" not in st.session_state:
            st.session_state.current_status = ""
        
        # Create two-column layout for progress and preview
        col_progress, col_preview = st.columns([1, 1])
        
        with col_progress:
            st.subheader("📊 Translation Progress")
            progress_bar = st.progress(0, text="Starting translation...")
            status_display = st.empty()
            chunk_status = st.empty()
            
            # Display progress from session state if available
            if "progress_info" in st.session_state and st.session_state.progress_info:
                prog_info = st.session_state.progress_info
                progress_bar.progress(prog_info["progress"], text=f"Paragraph {prog_info['idx']}/{prog_info['total']}")
                status_display.info(f"✅ **Paragraph {prog_info['idx']}/{prog_info['total']}** completed ({prog_info['length']:,} chars)")
            
            # Display chunk status from session state if available
            if "current_chunk" in st.session_state and st.session_state.current_chunk:
                chunk_info = st.session_state.current_chunk
                chunk_status.info(f"🔄 **Translating chunk {chunk_info['chunk_idx']}/{chunk_info['total_chunks']}** ({chunk_info['chunk_length']:,} chars)\n\n*Paragraph {chunk_info['para_idx']}/{chunk_info['total_paragraphs']}*")
            elif "current_status" in st.session_state and st.session_state.current_status:
                chunk_status.info(f"🔄 {st.session_state.current_status}")
        
        with col_preview:
            st.subheader("📄 Translated Paragraphs")
            preview_container = st.container()
            preview_text = preview_container.empty()
            # Show preview from session state (updated by callback)
            if "preview_content" in st.session_state and st.session_state.preview_content:
                preview_text.markdown(st.session_state.preview_content)
            elif translation_in_progress:
                preview_text.info("🔄 Translation in progress...")
            else:
                preview_text.info("📝 Translated paragraphs will appear here as they are completed...")
        
        # Create progress callback for paragraphs
        # IMPORTANT: Only update session state here, NOT widgets, to prevent infinite loops
        def progress_callback(idx: int, total: int, length: int) -> None:
            try:
                logger.debug(f"Progress callback: paragraph {idx}/{total} ({length:,} chars)")
                # Store progress in session state ONLY - no widget updates here
                st.session_state.progress_info = {
                    "idx": idx,
                    "total": total,
                    "length": length,
                    "progress": idx / total if total > 0 else 0.0,
                }
                logger.debug(f"Progress stored in session state: {idx/total*100:.1f}%")
            except Exception as e:
                logger.error(f"Error in progress_callback: {e}", exc_info=True)
                import sys
                print(f"ERROR in progress_callback: {e}", file=sys.stderr, flush=True)
        
        # Create chunk progress callback for real-time updates
        # IMPORTANT: Only update session state here, NOT widgets, to prevent infinite loops
        def chunk_progress_callback(para_idx: int, chunk_idx: int, total_chunks: int, chunk_length: int, total_paragraphs: int) -> None:
            try:
                logger.info(f"Chunk progress: paragraph {para_idx}/{total_paragraphs}, chunk {chunk_idx}/{total_chunks} ({chunk_length:,} chars)")
                # Store status in session state ONLY - no widget updates here
                st.session_state.current_status = f"Translating chunk {chunk_idx}/{total_chunks} ({chunk_length:,} chars) - Paragraph {para_idx}/{total_paragraphs}"
                st.session_state.current_chunk = {
                    "para_idx": para_idx,
                    "chunk_idx": chunk_idx,
                    "total_chunks": total_chunks,
                    "chunk_length": chunk_length,
                    "total_paragraphs": total_paragraphs,
                }
                logger.debug(f"Chunk progress stored in session state")
            except Exception as e:
                logger.error(f"Error in chunk_progress_callback: {e}", exc_info=True)
                import sys
                print(f"ERROR in chunk_progress_callback: {e}", file=sys.stderr, flush=True)
        
        # Initialize session state for progress tracking
        if "progress_info" not in st.session_state:
            st.session_state.progress_info = None
        if "current_chunk" not in st.session_state:
            st.session_state.current_chunk = None
        
        # Translation execution
        import time
        start_time = time.time()
        # Custom translation wrapper to capture translated paragraphs live
        from translator.processing import _read_input_file, _translate_paragraphs, TranslationOutcome
        from translator.processing import write_pdf as write_pdf_func
        from time import perf_counter
        
        # Double-check: ensure we're not already in progress (defensive against Streamlit reruns)
        if st.session_state.get("translation_in_progress", False) and st.session_state.get("translation_started", False):
            logger.warning("Translation already started, skipping to prevent infinite loop")
            st.warning("⚠️ Translation is already running. Please wait for it to complete.")
            st.stop()
        
        # Additional check: if this file was already translated, don't translate again
        current_file_hash = hashlib.md5(file_content).hexdigest()
        if (st.session_state.get("translated_file_hash") == current_file_hash and 
            st.session_state.get("translation_completed", False)):
            logger.warning(f"File {uploaded_file.name} already translated (hash: {current_file_hash[:8]}...), skipping")
            st.info("✅ This file has already been translated. Showing results below.")
            st.stop()
        
        # Mark translation as started
        st.session_state.translation_started = True
        logger.info(f"Starting translation for file: {uploaded_file.name} (hash: {current_file_hash[:8]}...)")
        
        # Ensure we're reading from the INPUT file, not output
        logger.info(f"Reading input file from: {tmp_input_path}")
        logger.info(f"Output file will be: {tmp_output_path}")
        if not tmp_input_path.exists():
            raise FileNotFoundError(f"Input file not found: {tmp_input_path}")
        
        # Safety check: ensure input and output paths are different
        if tmp_input_path.resolve() == tmp_output_path.resolve():
            raise ValueError(f"Input and output paths are the same: {tmp_input_path}")
        
        paragraphs, file_type = _read_input_file(tmp_input_path)
        logger.info(f"Read {len(paragraphs)} paragraphs from input file (first 200 chars: {paragraphs[0][:200] if paragraphs else 'N/A'}...)")
        if not paragraphs:
            raise ValueError("No text found to translate.")
        
        # Initialize translations list in session state
        if "live_translations" not in st.session_state:
            st.session_state.live_translations = []
        st.session_state.live_translations.clear()  # Clear previous translations
        
        # Translation callback to capture each completed translation
        # IMPORTANT: Only update session state here, NOT widgets, to prevent infinite loops
        def translation_callback(idx: int, translated_text: str) -> None:
            try:
                logger.info(f"Translation callback: paragraph {idx} completed ({len(translated_text):,} chars)")
                logger.debug(f"Translation preview (first 200 chars): {translated_text[:200]}...")
                
                # Store in session state ONLY - no widget updates here
                if "live_translations" not in st.session_state:
                    st.session_state.live_translations = []
                # Ensure list is long enough
                while len(st.session_state.live_translations) < idx:
                    st.session_state.live_translations.append("")
                # Update or append the translation
                if idx <= len(st.session_state.live_translations):
                    st.session_state.live_translations[idx - 1] = translated_text
                else:
                    st.session_state.live_translations.append(translated_text)
                
                logger.debug(f"Stored translation in session state. Total translations: {len([t for t in st.session_state.live_translations if t])}")
                
                # Build preview content and store in session state (no widget updates)
                if st.session_state.live_translations:
                    preview_content = "### 📄 Translated Paragraphs\n\n"
                    preview_content += f"**Progress:** {len([t for t in st.session_state.live_translations if t])} paragraph(s) completed\n\n"
                    preview_content += "---\n\n"
                    for i, trans in enumerate(st.session_state.live_translations, 1):
                        if trans:  # Only show non-empty translations
                            preview_content += f"#### Paragraph {i}\n\n"
                            # Show more text for better preview
                            preview_text_display = trans[:1000] + "..." if len(trans) > 1000 else trans
                            preview_content += preview_text_display
                            preview_content += f"\n\n*Length: {len(trans):,} characters*\n\n"
                            preview_content += "---\n\n"
                    # Store in session state for persistence (no widget update here)
                    st.session_state.preview_content = preview_content
                    st.session_state.last_updated_paragraph = idx
                    logger.debug(f"Preview content updated for paragraph {idx}")
            except Exception as e:
                logger.error(f"Error in translation_callback: {e}", exc_info=True)
                import sys
                print(f"ERROR in translation_callback: {e}", file=sys.stderr, flush=True)
        
        # Enhanced progress callback - just use the progress_callback directly
        # (no need for wrapper since progress_callback only updates session state now)
        enhanced_progress_callback = progress_callback
        
        start = perf_counter()
        translations, stats = _translate_paragraphs(
            paragraphs,
            translator=translator,
            glossary=glossary,
            memory=memory,
            source_lang=source_lang,
            target_lang=target_lang,
            progress_callback=enhanced_progress_callback,
            chunk_progress_callback=chunk_progress_callback,
            translation_callback=translation_callback,
            skip_memory=skip_memory,
        )
        duration = perf_counter() - start
        
        # Store all translations (already stored via callback, but ensure it's complete)
        st.session_state.translated_paragraphs = translations
        # Ensure live_translations matches
        st.session_state.live_translations = translations
        
        # Write PDF
        normalized_output = tmp_output_path if tmp_output_path.suffix.lower() == PDF_SUFFIX else tmp_output_path.with_suffix(PDF_SUFFIX)
        write_pdf_func(translations, normalized_output)
        
        # Create outcome object
        outcome = TranslationOutcome(
            input_path=tmp_input_path,
            output_path=normalized_output,
            file_type=file_type,
            translations=translations,
            stats=stats,
            duration_seconds=duration,
        )
        progress_bar.progress(1.0, text="Translation complete!")
        status_display.success(f"✅ **Translation completed!** ({outcome.duration_seconds:.1f} seconds)")
        chunk_status.empty()
        # Show final preview with all translations - full text
        final_preview = "### ✅ Complete Translation\n\n"
        final_preview += f"**Total paragraphs:** {len(translations)}\n\n"
        final_preview += "---\n\n"
        for i, trans in enumerate(translations, 1):
            final_preview += f"#### Paragraph {i}\n\n"
            final_preview += trans  # Show full translation
            final_preview += f"\n\n*Length: {len(trans):,} characters*\n\n"
            final_preview += "---\n\n"
        preview_text.markdown(final_preview)
        # Store in session state
        st.session_state.preview_content = final_preview
        
        # Build report
        report_payload = build_report_payload(outcome=outcome, source_lang=source_lang, target_lang=target_lang)
        
        # Store results in session state
        st.session_state.translation_result = {
            "output_path": tmp_output_path,
            "output_name": output_name,
        }
        st.session_state.translation_report = report_payload
        
        # Clear translation flags and mark as completed
        st.session_state.translation_in_progress = False
        st.session_state.translation_started = False
        st.session_state.translation_completed = True
        st.session_state.translated_file_hash = file_hash  # Store file hash to prevent retranslation
        st.session_state.current_file_hash_in_progress = None  # Clear in-progress hash
        
        logger.info(f"Translation completed successfully, flags cleared. File hash: {file_hash[:8]}...")
        
        # Show completion message - results will be displayed below automatically
        st.success("✅ Translation completed! Results are shown below.")
        
        # DO NOT call st.rerun() - let Streamlit naturally rerun on next interaction
        # The guards above will prevent retranslation
        
    except Exception as e:
        import sys
        import traceback
        error_details = str(e)
        error_traceback = traceback.format_exc()
        
        # Log to both logger and stderr (will be captured in log file)
        logger.error(f"Translation error: {error_details}")
        logger.error(f"Traceback: {error_traceback}")
        print(f"TRANSLATION ERROR: {error_details}", file=sys.stderr, flush=True)
        print(f"TRACEBACK:\n{error_traceback}", file=sys.stderr, flush=True)
        
        try:
            status_display.error(f"❌ Translation failed: {error_details}")
            chunk_status.error(f"**Error:** {error_details}")
            preview_text.error(f"Translation failed. Check error details below.")
            # Show error in expander
            with st.expander("🔍 Error Details", expanded=True):
                st.exception(e)
        except Exception as ui_error:
            logger.error(f"Error displaying error message: {ui_error}")
            print(f"ERROR displaying error: {ui_error}", file=sys.stderr, flush=True)
        
        # Always clear flags on error
        st.session_state.translation_in_progress = False
        st.session_state.translation_started = False
        st.session_state.current_file_hash_in_progress = None  # Clear in-progress hash
        raise
    
    except Exception as e:
        import sys
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        # Log to both logger and stderr (will be captured in log file)
        logger.error(f"Translation error (outer catch): {error_msg}")
        logger.error(f"Traceback: {error_traceback}")
        print(f"TRANSLATION ERROR (outer): {error_msg}", file=sys.stderr, flush=True)
        print(f"TRACEBACK:\n{error_traceback}", file=sys.stderr, flush=True)
        
        try:
            st.error(f"❌ Translation failed: {error_msg}")
            st.exception(e)  # Show full traceback in UI
        except Exception as ui_error:
            logger.error(f"Error displaying error message: {ui_error}")
            print(f"ERROR displaying error: {ui_error}", file=sys.stderr, flush=True)
        
        # Always clear flags on error
        st.session_state.translation_in_progress = False
        st.session_state.translation_started = False
        st.session_state.translated_file_hash = None  # Clear hash on error so user can retry
        st.session_state.current_file_hash_in_progress = None  # Clear in-progress hash
        logger.exception("Translation error")
        # Clean up temp files
        try:
            if 'tmp_input_path' in locals() and tmp_input_path.exists():
                tmp_input_path.unlink()
        except Exception:
            pass
        try:
            if 'tmp_output_path' in locals() and tmp_output_path.exists():
                tmp_output_path.unlink()
        except Exception:
            pass
    finally:
        # Clean up input temp file
        if 'tmp_input_path' in locals() and tmp_input_path.exists():
            tmp_input_path.unlink()

# Results section
if st.session_state.translation_result:
    st.divider()
    st.header("📥 Download Results")
    
    result = st.session_state.translation_result
    report = st.session_state.translation_report
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Download translated PDF
        if result["output_path"].exists():
            with open(result["output_path"], "rb") as f:
                st.download_button(
                    label="📄 Download Translated PDF",
                    data=f.read(),
                    file_name=result["output_name"],
                    mime="application/pdf",
                    use_container_width=True,
                )
    
    with col2:
        # Download report JSON
        if report:
            report_json = json.dumps(report, ensure_ascii=False, indent=2)
            st.download_button(
                label="📊 Download Translation Report",
                data=report_json.encode("utf-8"),
                file_name=result["output_name"].replace(".pdf", ".report.json"),
                mime="application/json",
                use_container_width=True,
            )
    
    # Display report details
    if report:
        st.divider()
        st.header("📈 Translation Report")
        
        with st.expander("View Detailed Report", expanded=False):
            st.json(report)
        
        # Summary stats
        if "stats" in report:
            stats = report["stats"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Paragraphs", stats.get("paragraphs_total", 0))
            with col2:
                st.metric("Empty Paragraphs", stats.get("empty_paragraphs", 0))
            with col3:
                st.metric("Reused from Memory", stats.get("reused_from_memory", 0))
            with col4:
                st.metric("Claude API Calls", stats.get("model_calls", 0))
            
            # Term sources breakdown
            if "paragraph_logs" in stats and stats["paragraph_logs"]:
                st.subheader("Term Translation Sources")
                term_sources = {}
                for para_log in stats["paragraph_logs"]:
                    if "terms_found" in para_log:
                        for source, count in para_log["terms_found"].items():
                            term_sources[source] = term_sources.get(source, 0) + count
                
                if term_sources:
                    st.bar_chart(term_sources)

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'>Legal Translator MVP • Powered by Claude AI</div>",
    unsafe_allow_html=True,
)

