#!/bin/bash
set -e

DATA_DIR="${REPORT_BASE_DIR:-/app/data/reports}"

# First run: copy bundled reports to persistent disk if empty
if [ ! -d "$DATA_DIR/daily" ]; then
    echo "Initializing data directory..."
    mkdir -p "$DATA_DIR"
    cp -r /app/reports/* "$DATA_DIR/" 2>/dev/null || true
fi

exec uvicorn toslack.server:app --host 0.0.0.0 --port "${PORT:-8000}"
