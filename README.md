# ChatMerge

A multi-provider AI chat application with intelligent conversation merging. Chat with OpenAI, Anthropic, and Google Gemini models through a single interface, then use AI to intelligently merge conversations together.

## Quick Start

```bash
# 1. Install backend dependencies
cd backend
pip install -r requirements.txt

# 2. Install frontend dependencies
cd ../frontend
npm install

# 3. Build frontend
npm run build

# 4. Run the server
cd ../backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000 in your browser.

**Or use the start script:**
```bash
chmod +x start.sh
./start.sh
```

## Setup

1. Open the app and click the **Settings** gear icon
2. Add your API keys for the providers you want to use:
   - OpenAI: Get key from https://platform.openai.com/api-keys
   - Anthropic: Get key from https://console.anthropic.com/
   - Google Gemini: Get key from https://aistudio.google.com/apikey
3. Create a new chat, pick a provider and model, and start chatting!

## Merging Conversations

The signature feature. After you have 2 or more chats:

1. Click **Merge Chats** in the sidebar
2. Select which chats to merge
3. Pick a model to perform the synthesis
4. Click **Merge** — the AI reads both full conversations and produces a single coherent merged thread

The merge isn't simple concatenation. The AI synthesizes both conversations: preserving all insights, eliminating redundancy, surfacing contradictions, and creating natural conversational flow.

## Development

For development with hot reload:

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend (proxies API calls to backend)
cd frontend
npm run dev
```

## Tech Stack

- **Backend**: Python FastAPI, SQLAlchemy, SQLite, SSE streaming
- **Frontend**: React, TypeScript, Vite, Zustand
- **Providers**: OpenAI, Anthropic, Google Gemini
