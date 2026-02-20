#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "  ChatMerge - Multi-Provider AI Chat App"
echo "========================================="
echo ""

# Resolve uv (preferred) or fall back to pip
if command -v uv &>/dev/null; then
  USE_UV=true
  echo "Using uv for Python dependency management."
elif command -v python3 &>/dev/null; then
  USE_UV=false
  echo "uv not found — falling back to pip."
else
  echo "Error: No Python found. Install uv (https://github.com/astral-sh/uv) or python3."
  exit 1
fi

echo ""

# Install backend dependencies
echo "[1/4] Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"
if [ "$USE_UV" = true ]; then
  uv sync -q
else
  pip3 install -r requirements.txt -q 2>&1 | tail -1
fi
echo "  Backend dependencies installed."

# Install frontend dependencies
echo "[2/4] Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
npm install --silent 2>&1 | tail -1
echo "  Frontend dependencies installed."

# Build frontend
echo "[3/4] Building frontend..."
npx vite build 2>&1 | tail -3
echo "  Frontend built."

# Start server
echo "[4/4] Starting server..."
cd "$SCRIPT_DIR/backend"

echo ""
echo "========================================="
echo "  App running at: http://localhost:8000"
echo "========================================="
echo ""
echo "  1. Open http://localhost:8000 in your browser"
echo "  2. Go to Settings (gear icon) and add your API keys"
echo "  3. Create a new chat and start messaging!"
echo "  4. Create multiple chats and use 'Merge Chats' to combine them"
echo ""

if [ "$USE_UV" = true ]; then
  uv run uvicorn main:app --host 0.0.0.0 --port 8000
else
  python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
fi
