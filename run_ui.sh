#!/bin/bash
# Simple script to launch the Streamlit web UI on port 8501

cd "$(dirname "$0")"
source .venv/bin/activate
python -m streamlit run src/translator/web_ui.py --server.port 8501

