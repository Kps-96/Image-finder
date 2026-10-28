#!/bin/bash
# Start Drupal Media Visual Search Engine Web Application

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

PORT="${PORT:-5000}"
echo "=========================================================="
echo "Starting Visual Search Engine on http://localhost:$PORT"
echo "Indexed: 792 Drupal Media Images (Images + SVGs)"
echo "Threshold Default: 80%"
echo "=========================================================="

exec python3 app.py
