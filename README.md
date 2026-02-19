# ChatMerge

**The only AI chat interface that lets you merge conversations.**

People constantly have great conversations across different AI systems — deep explorations in Claude, structured reasoning in o4-mini, creative brainstorming in Gemini — but there's no way to combine them. ChatMerge solves this: chat with OpenAI, Anthropic, and Google Gemini in a single dark-themed interface, then merge any conversations into one unified thread where the model has the full context of everything you've discussed.

---

## Features

- **Multi-provider chat**: OpenAI (GPT-4o, o4-mini), Anthropic (Claude Sonnet/Opus/Haiku), Google Gemini — through one interface
- **Smart conversation merging**: Combine 2+ chats via vector-fusion — source namespaces are nearest-neighbor fused (not just concatenated), producing a compressed semantic representation of both conversations
- **RAG-powered merged chats**: Every query in a merged chat retrieves the most relevant context from the fused vector store via Pinecone — no context-window explosions, scales to conversations of any length
- **File & image uploads**: Drag-and-drop, paste, or pick files. Images sent natively to provider vision APIs
- **Streaming responses**: Real-time SSE streaming for all providers
- **Encrypted API keys**: Keys stored encrypted with Fernet, never logged

---

## Quickstart (Local)

```bash
# Clone the repo
git clone https://github.com/yourusername/chat-merge-app.git
cd chat-merge-app

# Start everything (installs deps, builds frontend, starts server)
./start.sh
```

Open [http://localhost:8000](http://localhost:8000), click **Settings**, add your API key(s), and create your first chat.

**Manual setup:**
```bash
# Backend (uses uv for dependency management)
cd backend
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev  # Dev server on :5173, proxies API to :8000
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your keys:

```env
# Required: at least one AI provider key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional: enable RAG vector retrieval for merged chats
PINECONE_API_KEY=...

# Optional: cloud database (defaults to local SQLite)
DATABASE_URL=postgresql://user:pass@host/dbname

# Optional: cloud file storage (defaults to local uploads/)
BLOB_READ_WRITE_TOKEN=vercel_blob_...
```

Pinecone is required for merged-chat RAG (the core feature). Without it, merged chats fall back to simple vector union. The cloud DB and blob storage are optional (SQLite and local filesystem are the defaults).

---

## Architecture

```
chat-merge-app/
├── api/
│   └── index.py              # Vercel Python entry point
├── backend/
│   ├── main.py               # FastAPI app, CORS, static serving, startup
│   ├── requirements.txt
│   └── app/
│       ├── database.py       # SQLAlchemy async — SQLite or PostgreSQL
│       ├── models.py         # Chat, Message, Attachment, APIKey, MergeHistory
│       ├── schemas.py        # Pydantic request/response models
│       ├── providers/
│       │   ├── base.py       # Abstract BaseProvider + StreamChunk
│       │   ├── openai_provider.py    # OpenAI + o-series reasoning
│       │   ├── anthropic_provider.py # Claude + extended thinking
│       │   └── gemini_provider.py    # Gemini via google-genai SDK
│       ├── routes/
│       │   ├── chats.py      # CRUD: /api/chats
│       │   ├── messages.py   # Streaming: /api/chats/{id}/completions
│       │   ├── attachments.py # Files: /api/attachments
│       │   ├── api_keys.py   # Keys: /api/api-keys
│       │   └── merge.py      # Merge: /api/merge
│       └── services/
│           ├── chat_service.py       # CRUD operations
│           ├── completion_service.py # Streaming + RAG context building
│           ├── merge_service.py      # Full-context merge + vector merging
│           ├── vector_service.py     # Pinecone RAG (opt-in)
│           ├── storage_service.py    # Local or Vercel Blob storage
│           └── encryption_service.py # Fernet key encryption
├── frontend/
│   └── src/
│       ├── api.ts            # API client with SSE streaming
│       ├── store.ts          # Zustand global state
│       ├── types.ts          # TypeScript interfaces
│       └── components/
│           ├── App.tsx
│           ├── Sidebar.tsx   # Chat list + merge button
│           ├── ChatArea.tsx  # Messages + landing page
│           ├── InputArea.tsx # Text + file upload
│           ├── MessageBubble.tsx     # Message + attachment display
│           ├── MergeModal.tsx        # Merge UI with RAG status
│           └── SettingsModal.tsx     # API key management
├── vercel.json               # Vercel deployment config
└── requirements.txt          # Root-level Python deps for Vercel
```

### How Merging Works

1. User selects 2+ chats and a provider/model for the merge
2. **Vector fusion**: Source Pinecone namespaces are fused using nearest-neighbor averaging — semantically overlapping vectors from both chats are averaged into single embeddings; unique vectors are kept. Result size is between `max(|A|, |B|)` and `|A|+|B|`, not the full union
3. **Empty merged chat**: The new merged chat has zero copied messages — the fused vector namespace is its entire memory
4. **AI intro**: A brief assistant message is generated summarising the topics covered across the merged conversations
5. **Always-RAG completions**: Every user message in a merged chat embeds the query, retrieves top-K relevant chunks from the fused namespace, and injects them as context — no context window explosion regardless of source chat length

### Provider Details

| Provider | Streaming | Images | Notes |
|----------|-----------|--------|-------|
| OpenAI GPT-4o | ✅ | ✅ | Standard chat models |
| OpenAI o4-mini/o3 | ✅ | ❌ | No `temperature`, uses `developer` role |
| Anthropic Claude | ✅ | ✅ | Sonnet/Opus/Haiku via `claude-*-4-*` model IDs |
| Google Gemini | ✅ | ✅ | google-genai SDK (NOT google-generativeai) |

---

## Deployment (Vercel)

### Prerequisites
- Vercel account
- Neon or Vercel Postgres database (free tier works)
- Pinecone account for RAG (optional but recommended)
- Vercel Blob for file storage (optional)

### Steps

1. **Push to GitHub**
   ```bash
   gh repo create chatmerge --public
   git push -u origin main
   ```

2. **Import to Vercel**
   - Go to vercel.com → New Project → Import your repo

3. **Set environment variables** in Vercel dashboard:
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GOOGLE_API_KEY=...
   DATABASE_URL=postgresql://...   (from Neon/Vercel Postgres)
   PINECONE_API_KEY=...            (from pinecone.io)
   BLOB_READ_WRITE_TOKEN=...       (from Vercel Blob)
   ALLOWED_ORIGINS=https://your-app.vercel.app
   ```

4. **Deploy** — Vercel auto-detects FastAPI and the static frontend

### Database Setup (Neon)

1. Create a Neon project at neon.tech
2. Copy the connection string (PostgreSQL format)
3. Add as `DATABASE_URL` in Vercel — the app handles the rest (table creation on startup)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chats` | List all chats |
| POST | `/api/chats` | Create chat (`provider`, `model`, optional `title`, `system_prompt`) |
| GET | `/api/chats/{id}` | Get chat with messages |
| PATCH | `/api/chats/{id}` | Update chat title |
| DELETE | `/api/chats/{id}` | Delete chat |
| GET | `/api/chats/{id}/messages` | Get messages |
| POST | `/api/chats/{id}/completions` | Stream completion (SSE) |
| POST | `/api/attachments` | Upload files (multipart/form-data) |
| GET | `/api/attachments/{id}` | Download attachment |
| DELETE | `/api/attachments/{id}` | Delete attachment |
| GET | `/api/api-keys` | List configured providers |
| POST | `/api/api-keys` | Save API key |
| DELETE | `/api/api-keys/{id}` | Remove API key |
| POST | `/api/merge` | Merge chats (SSE streaming) |
| GET | `/health` | Health check with feature status |

---

## Troubleshooting

**"No API key configured for provider"**
→ Open Settings (gear icon), add your API key for the selected provider.

**Streaming stops / no response**
→ Check browser console. If you see CORS errors, verify `ALLOWED_ORIGINS` is set correctly. For local dev, leave it unset.

**Files not uploading**
→ Check file type (images, PDFs, text files supported). Max 10MB per file.

**RAG not working after merge**
→ Set `PINECONE_API_KEY`. Without it, merge falls back to simple vector union (no nearest-neighbor fusion). The merge modal shows a green "Smart fusion enabled" banner when Pinecone is configured.

**Merged chat not responding**
→ Ensure you chose a real LLM provider (OpenAI/Anthropic/Gemini) as the merge model — Pinecone (RAG) is not a chat provider.

**Database errors on first run**
→ Tables are created automatically on startup. If you see schema errors, delete `chat_app.db` (SQLite) or drop and recreate tables.

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 async, Fernet encryption
- **Database**: SQLite (local) / PostgreSQL via asyncpg (production)
- **Vector Store**: Pinecone serverless with OpenAI text-embedding-3-small
- **File Storage**: Local filesystem / Vercel Blob
- **Frontend**: React 18, TypeScript, Vite, Zustand, Lucide icons
- **Streaming**: Server-Sent Events (SSE) with manual formatting
- **Deployment**: Vercel (Python + static)
