# ChatMerge

**The only AI chat interface that lets you merge conversations.**

People constantly have great conversations across different AI systems — deep explorations in Claude, structured reasoning in o4-mini, creative brainstorming in Gemini — but there's no way to combine them. ChatMerge solves this: chat with OpenAI, Anthropic, and Google Gemini in a single dark-themed interface, then merge any conversations into one unified thread where the model has the full context of everything you've discussed.

---

## Features

- **Multi-provider chat**: OpenAI (GPT-4o, o4-mini, o3), Anthropic (Claude Sonnet/Opus/Haiku 4.5+), Google Gemini (2.5 Flash/Pro) — through one interface
- **Smart conversation merging**: Combine 2+ chats via vector-fusion — source namespaces are nearest-neighbor fused (not just concatenated), producing a compressed semantic representation of both conversations
- **RAG-powered merged chats**: Every query in a merged chat retrieves the most relevant context from the fused vector store via Pinecone — no context-window explosions, scales to conversations of any length
- **File & image uploads**: Drag-and-drop, paste, or pick files. Images sent natively to provider vision APIs
- **Streaming responses**: Real-time SSE streaming for all providers
- **Browser-side API keys**: Keys stored in `localStorage`, sent as request headers — never persisted server-side

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

**API keys are browser-side** — you enter them in the Settings modal (⚙ gear icon), not in `.env`. They are stored in `localStorage` and sent as request headers on each API call. The server never stores them.

The only server-side config is optional infrastructure:

```env
# Optional: PostgreSQL for production (Railway injects DATABASE_URL automatically)
# DATABASE_URL=postgresql://user:pass@host/dbname

# Optional: lock CORS to your domain in production
# ALLOWED_ORIGINS=https://your-app.up.railway.app
```

Copy `backend/.env.example` to `backend/.env` for local overrides. SQLite is the default database — no setup required for local dev.

---

## Architecture

### System Overview

```
+-----------------------------------------------------------------+
|                         Browser (React 18)                       |
|  Zustand store --- api.ts --- SSE streaming --- dark theme UI    |
+----------------------------+------------------------------------+
                             | HTTP / SSE
                             v
+-----------------------------------------------------------------+
|                     FastAPI (Python 3.11)                         |
|                                                                   |
|  Routes                    Services                               |
|  +-- /api/chats           +-- chat_service      (CRUD)           |
|  +-- /api/chats/{id}/     +-- completion_service (streaming +    |
|  |   completions          |                      merged-chat RAG)|
|  +-- /api/merge           +-- merge_service      (vector fusion) |
|  +-- /api/attachments     +-- vector_service     (Pinecone ops)  |
|  +-- /api/models          +-- storage_service    (local files)   |
|  +-- /health                                                      |
|                                                                   |
|  Providers                                                        |
|  +-- openai_provider.py    (GPT-4o, o-series)                    |
|  +-- anthropic_provider.py (Claude Sonnet/Opus/Haiku)            |
|  +-- gemini_provider.py    (google-genai SDK)                    |
+----------+---------------------------+---------------------------+
           |                           |
           v                           v
  +-----------------+       +-----------------------+
  |  SQLite / PG    |       |  Pinecone Serverless   |
  |  (SQLAlchemy    |       |  OpenAI or Gemini emb.  |
  |   async)        |       |  768-dim, 1 namespace   |
  |                 |       |  per chat               |
  |  Chat, Message, |       |  fuse_namespaces() for  |
  |  Attachment,    |       |  merged chats           |
  |  MergeHistory   |       |                         |
  +-----------------+       +-----------------------+
```

### Directory Structure

```
chat-merge-app/
├── backend/
│   ├── main.py               # FastAPI app, CORS, static serving, startup
│   └── app/
│       ├── database.py       # SQLAlchemy async — SQLite or PostgreSQL
│       ├── models.py         # Chat, Message, Attachment, MergeHistory
│       ├── schemas.py        # Pydantic request/response models
│       ├── providers/
│       │   ├── base.py       # Abstract BaseProvider + StreamChunk
│       │   ├── openai_provider.py    # OpenAI + o-series reasoning
│       │   ├── anthropic_provider.py # Claude 4.5/4.6
│       │   └── gemini_provider.py    # Gemini via google-genai SDK
│       ├── routes/
│       │   ├── chats.py      # CRUD: /api/chats
│       │   ├── messages.py   # Streaming: /api/chats/{id}/completions
│       │   ├── attachments.py # Files: /api/attachments
│       │   └── merge.py      # Merge: /api/merge + /api/models
│       └── services/
│           ├── chat_service.py       # CRUD operations
│           ├── completion_service.py # Streaming + RAG context building
│           ├── merge_service.py      # Full-context merge + vector merging
│           ├── vector_service.py     # Pinecone RAG; OpenAI/Gemini embeddings
│           └── storage_service.py    # Local file storage (Railway volume in prod)
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
└── railway.toml              # Railway deployment config
```

### How Merging Works

```
Chat A namespace (N vectors)      Chat B namespace (M vectors)
         |                                  |
         +------------------+---------------+
                            v
                   fuse_namespaces()
           +-------------------------------------+
           | For each vector in B:               |
           |   cosine_sim with nearest in A      |
           |   >= 0.82 -> average embeddings     |
           |   <  0.82 -> keep as unique         |
           +-------------------------------------+
                            |
                            v
         Merged namespace (between max(N,M) and N+M vectors)
                            |
                  +-------------------+
                  |  Every query in   |
                  |  merged chat does |
                  |  RAG against this |
                  |  fused namespace  |
                  +-------------------+
```

1. User selects 2+ chats and a provider/model for the merge
2. **Vector fusion**: Source Pinecone namespaces are fused using nearest-neighbor averaging — semantically overlapping vectors from both chats are averaged into single embeddings; unique vectors are kept. Result size is between `max(|A|, |B|)` and `|A|+|B|`, not the full union
3. **Empty merged chat**: The new merged chat has zero copied messages — the fused vector namespace is its entire memory
4. **AI intro**: A brief assistant message is generated summarising the topics covered across the merged conversations
5. **Always-RAG completions**: Every user message in a merged chat embeds the query, retrieves top-K relevant chunks from the fused namespace, and injects them as context — no context window explosion regardless of source chat length

### Provider Details

| Provider | Models | Streaming | Images | Notes |
|----------|--------|-----------|--------|-------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o4-mini, o3, o3-mini | ✅ | ✅ (GPT) | o-series: no `temperature`, uses `developer` role |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5-20251001 | ✅ | ✅ | Claude 4.5/4.6 family |
| Google Gemini | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash | ✅ | ✅ | google-genai SDK (NOT google-generativeai) |

---

## Deployment

### Recommended: Railway

Railway runs the app as a **persistent process** — ideal for FastAPI with SSE streaming. No timeout issues, no stateless cold-start problems.

#### Steps

1. **Push to GitHub** (already done if you cloned this repo)

2. **Create a Railway account** at [railway.app](https://railway.app) → New Project → Deploy from GitHub repo → select this repo. Railway reads `railway.toml` automatically.

3. **Add a PostgreSQL database**: In your Railway project → Add Service → Database → PostgreSQL. Railway injects `DATABASE_URL` into your app — it auto-switches from SQLite to PostgreSQL.

4. **Set environment variables** in Railway project → Variables:
   ```
   ALLOWED_ORIGINS=https://your-app.up.railway.app
   ```
   API keys (OpenAI, Anthropic, Gemini, Pinecone) are **not** server-side env vars — users enter them in the Settings UI and they stay in the browser. The server never stores them.

5. **Get your URL** — Railway assigns `https://your-app.up.railway.app`. Set that as `ALLOWED_ORIGINS` above.

6. **File uploads** — Railway provides persistent volumes. Enable one under your service → Settings → Volumes, mounted at `/app/backend/uploads`. Without it, uploads persist only until the next redeploy.

#### What the `railway.toml` does

```toml
[build]
buildCommand = "cd frontend && npm ci && npm run build && cd ../backend && uv sync"
# ↑ Builds React frontend → frontend/dist/  then installs Python deps

[deploy]
startCommand = "cd backend && uv run uvicorn main:app --host 0.0.0.0 --port $PORT"
# ↑ $PORT is injected by Railway; FastAPI serves both API and frontend dist
healthcheckPath = "/health"
# ↑ Railway pings this — if it stops returning 200, Railway restarts the service
```

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
| POST | `/api/merge` | Merge chats (SSE streaming); include API keys as `x-*-key` headers |
| GET | `/api/models` | Available models per provider |
| GET | `/health` | Liveness check |

---

## Troubleshooting

**"No API key configured for provider"**
→ Open Settings (gear icon), add your API key for the selected provider.

**Streaming stops / no response**
→ Check browser console. If you see CORS errors, verify `ALLOWED_ORIGINS` is set correctly. For local dev, leave it unset.

**Files not uploading**
→ Check file type (images, PDFs, text files supported). Max 10MB per file.

**RAG not working after merge**
→ Open Settings and add both a Pinecone key AND either an OpenAI or Gemini key. Both are required for embeddings. The merge modal shows a yellow warning when RAG isn't configured. Pinecone index dimension must be 768 — delete and recreate if you had a previous 1536-dim index.

**Merged chat not responding**
→ Ensure you chose a real LLM provider (OpenAI/Anthropic/Gemini) as the merge model — Pinecone (RAG) is not a chat provider.

**Database errors on first run**
→ Tables are created automatically on startup. If you see schema errors, delete `chat_app.db` (SQLite) or drop and recreate tables.

**Gemini 404 NOT_FOUND**
→ Google periodically sunsets older model IDs. Keep `backend/app/providers/gemini_provider.py` `AVAILABLE_MODELS` and `frontend/src/types.ts` `PROVIDER_MODELS.gemini` in sync with current model IDs from Google AI Studio.

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 async
- **Database**: SQLite (local) / PostgreSQL via asyncpg (production)
- **Vector Store**: Pinecone serverless, 768-dim (OpenAI `text-embedding-3-small` or Gemini `gemini-embedding-001`)
- **File Storage**: Local filesystem (Railway persistent volume in production)
- **Frontend**: React 18, TypeScript, Vite, Zustand, Lucide icons
- **Streaming**: Server-Sent Events (SSE) with manual formatting
- **Deployment**: Railway
