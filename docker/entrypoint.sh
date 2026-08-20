#!/bin/bash
set -e

DATA_DIR="${REPORT_BASE_DIR:-/app/data/reports}"
PAPERS_DIR="${PAPERS_BASE_DIR:-/app/data/papers}"
INDEX_DIR="${INDEX_BASE_DIR:-/app/data/index}"

# First run: copy bundled reports to persistent disk if empty
if [ ! -d "$DATA_DIR/daily" ]; then
    echo "Initializing data directory..."
    mkdir -p "$DATA_DIR"
    cp -r /app/reports/* "$DATA_DIR/" 2>/dev/null || true
fi

# First run: seed skim history so trend aggregation has past days available
if [ ! -d "$PAPERS_DIR" ] || [ -z "$(ls -A "$PAPERS_DIR" 2>/dev/null)" ]; then
    echo "Initializing papers directory..."
    mkdir -p "$PAPERS_DIR"
    cp -r /app/papers/* "$PAPERS_DIR/" 2>/dev/null || true
fi

# First run: seed the tag/date/score indexes
if [ ! -d "$INDEX_DIR" ] || [ -z "$(ls -A "$INDEX_DIR" 2>/dev/null)" ]; then
    echo "Initializing index directory..."
    mkdir -p "$INDEX_DIR"
    cp -r /app/index/* "$INDEX_DIR/" 2>/dev/null || true
fi

exec uvicorn toslack.server:app --host 0.0.0.0 --port "${PORT:-8000}"
