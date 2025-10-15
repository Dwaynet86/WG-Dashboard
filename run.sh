#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$DIR/venv/bin/activate" ]; then
  source "$DIR/venv/bin/activate"
else
  echo "❌ Virtual environment not found. Creating..."
  python3 -m venv "$DIR/venv"
  source "$DIR/venv/bin/activate"
  pip install -r "$DIR/requirements.txt"
fi

echo "✅ Starting WG Dashboard..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
