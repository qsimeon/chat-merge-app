#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "  ChatMerge - Multi-Provider AI Chat App"
echo "========================================="
echo ""

# Install backend dependencies
echo "[1/4] Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"
pip install -r requirements.txt -q 2>&1 | tail -1
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

python -m uvicorn main:app --host 0.0.0.0 --port 8000
