# Legal Document Translator

Minimal viable prototype for batch legal document translation with Claude AI.

## Architecture

- **Backend**: FastAPI REST API (`src/translator/api.py`)
- **Frontend**: React application (`frontend/`)
- **CLI**: Command-line interface (`src/translator/cli.py`)

## Setup

### Backend

1. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -e .
```

3. Configure environment variables (create `.env` file):
```bash
ANTHROPIC_API_KEY=your_api_key_here
DATA_ROOT=./data
DEFAULT_SOURCE_LANG=fr
DEFAULT_TARGET_LANG=it
```

### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

## Running

### Backend API

```bash
./run_api.sh
# Or: uvicorn src.translator.api:app --host 0.0.0.0 --port 8000 --reload
```

API will be available at http://localhost:8000

### Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at http://localhost:5173

### Public Access (ngrok)

**Quick Start (All Services + ngrok):**

```bash
./start_all_with_ngrok.sh
```

This will start backend, frontend, and ngrok tunnel together. The public URL will be displayed.

**Individual ngrok tunnels:**

To expose the backend API publicly:

```bash
./run_ngrok.sh
```

To expose the frontend publicly:

```bash
./run_ngrok_frontend.sh
```

**Note:** 
- CORS is already configured to allow ngrok domains automatically
- The frontend proxy will continue to work through ngrok, forwarding `/api` requests to the backend
- Ngrok dashboard is available at http://localhost:4040

### CLI

```bash
translate translate-doc input.pdf --target-lang it
translate translate-batch ./documents --output-dir ./output
```

## API Endpoints

- `GET /` - API info
- `GET /api/glossaries` - List available glossaries
- `POST /api/translate` - Start translation job (returns job_id)
- `GET /api/translate/{job_id}/status` - Get translation status
- `GET /api/translate/{job_id}/download` - Download translated PDF
- `GET /api/translate/{job_id}/report` - Get translation report

## Features

- Translate DOCX, PDF, and TXT files
- Glossary support for terminology consistency
- Translation memory for reuse
- Progress tracking
- Batch processing via CLI
