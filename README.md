# Legal Translation MVP

Prototype that batches DOCX/PDF legal documents through Claude while keeping terminology consistent and returning formatted DOCX outputs.

## Getting Started

1. **Python**: use 3.11.
2. **Install**: `pip install -e .` or `uv pip install -e .`.
3. **Env vars**: copy `.env.example` to `.env` and fill the Anthropic key.
4. **Test run** (placeholder): `python -m translator.cli --help`.

## Project Layout

- `src/translator/`: application code (ingest, glossary, Claude client, CLI, UI).
- `data/`: runtime storage for uploads, exports, logs (not committed).

## Next Steps

- Implement glossary + translation memory helpers.
- Build single-document CLI that reads DOCX, calls Claude with translator prompt, and writes translated DOCX.


