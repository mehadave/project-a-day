#!/usr/bin/env bash
# Entry point for the Project-a-Day Agent.
# Usage:
#   bash run.sh              → interactive build (asks for idea + difficulty)
#   bash run.sh --queue      → save idea for tomorrow's scheduled build
#   bash run.sh --headless   → build from queued idea (or auto-generate one)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Error: venv/ not found. Run setup.sh first."
    exit 1
fi

source venv/bin/activate
python agent/main.py "$@"
