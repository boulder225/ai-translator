#!/bin/bash
# Script to launch the React frontend

SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR/frontend"
mkdir -p "$SCRIPT_DIR/logs"
npm run dev 2>&1 | tee "$SCRIPT_DIR/logs/frontend.log"

