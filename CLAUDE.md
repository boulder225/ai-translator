# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Legal Document Translator - An MVP web application for batch translating legal documents (DOCX, PDF, TXT) using Claude AI with built-in terminology management and translation memory. The system maintains terminology consistency across translations through a cascading lookup system (translation memory → glossary → Claude translation).

**Tech Stack:**
- Backend: FastAPI (Python 3.11+), Anthropic Claude API, pdfplumber/python-docx/reportlab
- Frontend: React 18.3 + Vite
- Deployment: Docker with Nginx reverse proxy, ngrok for public access
- Testing: pytest with FastAPI TestClient

## Development Commands

### Initial Setup

Backend:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

Frontend:
```bash
cd frontend
npm install
```

Environment configuration (`.env` file required):
```
ANTHROPIC_API_KEY=your_api_key_here
DATA_ROOT=./data
DEFAULT_SOURCE_LANG=fr
DEFAULT_TARGET_LANG=it
```

### Running Services

**All services at once (recommended for development):**
```bash
./start_all_with_ngrok.sh  # Starts backend (8000), frontend (5173), and ngrok tunnel
```

**Individual services:**
```bash
./run_api.sh              # Backend on port 8000
./run_frontend.sh         # Frontend on port 5173 (cd frontend && npm run dev)
./run_ngrok_frontend.sh   # Public ngrok tunnel for frontend
```

Backend logs to `logs/backend.log`, frontend to `logs/frontend.log`.

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_terminology.py::test_glossary_exact_match
```

Test fixtures are in `/tests/fixtures/` (sample CSVs, documents).

### CLI Usage

```bash
# Single document translation
translate translate-doc input.pdf --target-lang it

# Batch processing
translate translate-batch ./documents --output-dir ./output

# Web UI (Streamlit alternative interface)
translate web
```

### Docker

```bash
# Build and test locally
./docker-build-local.sh  # Builds image
./docker-test.sh         # Runs container on port 8080

# Manual Docker commands
docker build -t legal-translator .
docker run -p 8080:80 -e ANTHROPIC_API_KEY=sk-... legal-translator
```

Docker uses multi-stage build (Node → Python+Nginx). Backend runs on port 8080 internally, Nginx proxies on port 80.

### Linting & Formatting

```bash
# Install dev dependencies first
pip install -e ".[dev]"

# Ruff (linter & formatter)
ruff check src tests          # Lint
ruff check --fix src tests    # Auto-fix
ruff format src tests         # Format code

# Type checking
mypy src
```

## Architecture

### Core Subsystems

**1. Translation Pipeline (`src/translator/processing.py`):**
- Entry point: `translate_file()` - orchestrates entire translation flow
- Document format handling: PDF (pdfplumber/PyPDF2), DOCX (python-docx), TXT
- Chunking strategy: 15,000 char max chunks with 100-char overlap to maintain context
- Paragraph-level processing with progress callbacks
- Alternative: `translate_file_to_memory()` - saves to memory without generating PDF

**2. Job Management System (`src/translator/api.py`):**
- In-memory job storage with threading (one thread per translation job)
- Job states: pending → in_progress → completed/cancelled
- Job isolation: unique temp directories per job, MD5 file verification
- Duplicate request detection via request hash tracking
- Status polling endpoint for real-time progress

**3. Terminology Cascade (`src/translator/terminology/`):**
- **Translation Memory** (`memory.py`): JSON-based, exact match lookups (fastest)
- **Glossary** (`glossary.py`): CSV-based, fuzzy matching with rapidfuzz (70%+ similarity default)
- **Term Hierarchy** (`term_hierarchy.py`): Consistent term substitution rules
- Lookup order: Memory → Glossary → Hierarchy → Claude translation

**4. Claude Integration (`src/translator/claude_client.py`):**
- Role-based prompt templates loaded from files (`prompt.md`, `prompt-translator.md`, `prompt-reviewer.md`)
- Dynamic glossary/memory injection into prompts
- Retry logic with tenacity for API resilience
- Dry-run mode for testing without API calls

**5. PDF Generation (`src/translator/pdf_writer.py`):**
- Memory-optimized: all PDFs generated in-memory via `write_pdf_to_bytes()`
- reportlab-based with headers, footers, page numbers
- Format preservation for legal documents

### Data Flow

```
User Upload
    ↓
[POST /api/translate] → Creates job, stores file in /tmp/{job_id}/
    ↓
[Background Thread]
    ├─ Extract paragraphs from document
    ├─ Chunk if >15K chars (with overlap)
    ├─ For each chunk:
    │   ├─ Check Translation Memory (exact match)
    │   ├─ If not found: Fuzzy match Glossary
    │   ├─ If not found: Call Claude API
    │   └─ Store result in Memory
    ├─ Generate PDF with reportlab
    └─ Update job status
    ↓
[Frontend polls GET /api/translate/{job_id}/status] → Real-time progress
    ↓
[Download endpoints] → PDF, text, report, TMX/TBX exports
```

### Key API Endpoints

- `POST /api/translate` - Start translation (returns job_id)
- `GET /api/translate/{job_id}/status` - Poll status/progress
- `GET /api/translate/{job_id}/download` - Download PDF
- `GET /api/translate/{job_id}/download-text` - Download plain text
- `GET /api/translate/{job_id}/report` - Get translation report
- `POST /api/translate/{job_id}/cancel` - Cancel running job
- `POST /api/glossary/entries` - Add glossary entry
- `GET /api/glossary/entries` - Get all entries
- `POST /api/export-memory-tmx/{job_id}` - Export memory as TMX
- `POST /api/export-glossary-tbx` - Export glossary as TBX
- `POST /api/detect-language` - Auto-detect source language

### File Locations

| Path | Purpose |
|------|---------|
| `src/translator/api.py` | FastAPI application, job management (1,331 LOC) |
| `src/translator/processing.py` | Translation pipeline orchestration (978 LOC) |
| `src/translator/claude_client.py` | Claude API wrapper, prompt management (520 LOC) |
| `src/translator/pdf_writer.py` | PDF generation with reportlab (508 LOC) |
| `src/translator/terminology/glossary.py` | CSV glossary with fuzzy matching |
| `src/translator/terminology/memory.py` | JSON translation memory |
| `src/translator/cli.py` | Typer CLI interface (156 LOC) |
| `frontend/src/components/TranslationForm.jsx` | Main UI form (~50KB) |
| `frontend/src/components/TranslationStatus.jsx` | Progress tracking UI |
| `glossary/glossary.csv` | Main glossary file (60KB) |
| `glossary/memory.json` | Translation memory storage |

## Project Philosophy (from .cursorrules)

**Mission:** Build MVP to secure first paying customer within 3-4 weeks.

**Core Principles:**
1. Speed over perfection
2. Validation over architecture
3. Simplicity over elegance
4. Working over comprehensive

**Must Have:**
- Process 50+ documents in batch
- Terminology consistency across translations
- Preserve document formatting
- Claude API integration
- Support French/German ↔ English/German

**Must NOT Have (yet):**
- MCP server implementation
- Database backend (using file system)
- User authentication (basic role selection only)
- Multi-tenant support
- Enterprise architecture

## Important Implementation Details

### Terminology Management

The 3-tier cascade ensures consistency:
1. **Translation Memory** (fastest): Exact paragraph matches from previous translations
2. **Glossary**: Fuzzy term matching (configurable threshold, default 70%)
3. **Claude Translation**: Fresh translation with glossary context

Memory deduplication filters placeholder text to avoid polluting the memory with generic translations.

### Chunking Strategy

Documents >15,000 chars split into chunks with 100-char overlap to maintain context across chunk boundaries. This prevents context loss at chunk edges while keeping within Claude's context limits.

### Job Isolation

Each translation job gets:
- Unique job ID (UUID)
- Isolated temp directory (`/tmp/{job_id}/`)
- File hash verification (MD5) for integrity
- Independent thread for processing

### Docker Startup Quirks

The `docker-start.sh` script has aggressive Nginx default site removal logic. This is intentional - conflicts with Nginx default configurations were a recurring issue. The script:
1. Removes default site configurations from sites-enabled/sites-available
2. Verifies nginx.conf doesn't have default_server
3. Starts backend (uvicorn on 8080)
4. Starts Nginx (reverse proxy on 80)

### CORS Configuration

CORS is pre-configured to allow:
- `http://localhost:5173` (Vite dev server)
- `*.ngrok.io`, `*.ngrok-free.app` (ngrok tunnels)

If adding new domains, update `CORS_ORIGINS` in `src/translator/api.py:36`.

### Prompt Customization

Prompts are loaded from files at startup:
- `prompt.md` - Default prompt
- `prompt-translator.md` - Translator role
- `prompt-reviewer.md` - Reviewer role
- `prompt-admin.md` - Admin role

Edit these files to modify translation behavior. Users can also provide custom prompts via the UI.

### Known Limitations

- JSON-based memory (not scalable beyond ~100MB)
- Sequential processing (no parallelization)
- Basic PDF table handling (formatting may need manual cleanup)
- Single-user authentication model (username stored in localStorage)
- No persistent database (MVP intentionally uses file system)

## Common Workflows

### Adding a New Translation Feature

1. Backend: Update `src/translator/processing.py` for pipeline changes
2. API: Add endpoint in `src/translator/api.py` if needed
3. Frontend: Update `TranslationForm.jsx` for UI controls
4. Test: Add tests in `tests/test_*.py`

### Modifying Glossary Matching

Edit `src/translator/terminology/glossary.py`:
- `FUZZY_THRESHOLD` constant controls matching sensitivity (default 70)
- `match_terms()` handles fuzzy matching logic
- `get_fuzzy_matches()` uses rapidfuzz for similarity

### Debugging Translation Issues

1. Check `logs/backend.log` for API/processing errors
2. Review Claude API calls in debug mode (set DEBUG=True in settings)
3. Inspect translation memory at `glossary/memory.json`
4. Use dry-run mode in `claude_client.py` to test without API calls
5. Check `.cursor/debug.log` for introspection data

### Adding New Document Formats

1. Add parser in `src/translator/pdf_io.py` or `src/translator/docx_io.py`
2. Update `extract_paragraphs()` in `processing.py` to handle new format
3. Update `api.py` to accept new file extensions in upload endpoint
4. Add tests with sample documents in `/tests/fixtures/`

### Exporting Translation Data

The system supports industry-standard formats:
- **TMX** (Translation Memory eXchange): Use `/api/export-memory-tmx/{job_id}`
- **TBX** (TermBase eXchange): Use `/api/export-glossary-tbx`

Export logic in `src/translator/export.py`.
