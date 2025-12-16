#!/bin/bash
# Script to launch the FastAPI backend server

cd "$(dirname "$0")"
mkdir -p logs
source .venv/bin/activate
uvicorn src.translator.api:app --host 0.0.0.0 --port 8000 --reload 2>&1 | tee logs/backend.log

