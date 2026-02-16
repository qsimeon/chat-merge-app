# ChatMerge — Claude Code Session Initialization Prompt

Copy everything below this line and paste it as your first message when starting a new Claude Code session in the `~/chat-merge-app` directory.

---

## Context: What This Project Is

You are continuing development on **ChatMerge**, a multi-provider AI chat application with a unique "merge chats" feature. The app connects to OpenAI, Anthropic, and Google Gemini APIs through a single ChatGPT/Claude-like dark-themed interface. Its killer feature is the ability to merge separate conversations so that when you continue chatting in the merged conversation, the model has the full context (all messages, files, and reasoning traces) from all source chats.

**The motivation**: People constantly have great conversations across different AI chats but can't combine them. ChatMerge solves this by letting you merge any two (or more) conversations into one, preserving the complete context including internal reasoning traces.

The project was built from scratch over several sessions. It works — chats with all 3 providers stream correctly, merge works, reasoning traces are captured from Anthropic (extended thinking) and OpenAI (o-series reasoning summaries), and the dark-themed UI is functional. But there are three major feature additions / architectural changes to implement now.

## Current Architecture

### Tech Stack
- **Backend**: Python FastAPI (async), SQLAlchemy ORM, SQLite via aiosqlite, Fernet encryption for API keys
- **Frontend**: React 18 + TypeScript + Vite + Zustand (state management) + Lucide icons
- **Streaming**: Server-Sent Events (SSE) via `StreamingResponse` with manual `data: {json}\n\n` formatting
- **No auth** currently — single-user local app

### Directory Structure
```
chat-merge-app/
├── backend/
│   ├── main.py                          # FastAPI app, CORS, static file serving, startup
│   ├── requirements.txt                 # Python deps
│   ├── app/
│   │   ├── database.py                  # SQLAlchemy async engine, sqlite+aiosqlite
│   │   ├── models.py                    # ORM: Chat, Message, APIKey, MergeHistory
│   │   ├── schemas.py                   # Pydantic request/response models
│   │   ├── providers/
│   │   │   ├── base.py                  # Abstract BaseProvider + StreamChunk dataclass
│   │   │   ├── factory.py               # create_provider() factory
│   │   │   ├── openai_provider.py       # OpenAI + o-series reasoning capture
│   │   │   ├── anthropic_provider.py    # Anthropic + extended thinking enabled
│   │   │   └── gemini_provider.py       # google-genai SDK (not google-generativeai)
│   │   ├── routes/
│   │   │   ├── chats.py                 # CRUD: /api/chats
│   │   │   ├── messages.py              # Streaming: /api/chats/{id}/completions
│   │   │   ├── api_keys.py             # Key management: /api/api-keys
│   │   │   └── merge.py                # Merge streaming: /api/merge
│   │   └── services/
│   │       ├── chat_service.py          # Chat/message CRUD operations
│   │       ├── completion_service.py    # Streaming + reasoning trace context building
│   │       ├── merge_service.py         # Full-context merge (copies ALL messages)
│   │       └── encryption_service.py    # Fernet encrypt/decrypt for API keys
├── frontend/
│   ├── package.json                     # React 18, Zustand, Lucide, Vite
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── main.tsx                     # Entry point
│   │   ├── api.ts                       # API layer with SSE streaming
│   │   ├── store.ts                     # Zustand store (all state + actions)
│   │   ├── types.ts                     # TypeScript interfaces
│   │   ├── index.css                    # Full dark theme CSS (~1000 lines)
│   │   └── components/
│   │       ├── App.tsx                  # Main layout
│   │       ├── Sidebar.tsx              # Chat list + merge button
│   │       ├── ChatArea.tsx             # Message display + streaming
│   │       ├── InputArea.tsx            # Text input
│   │       ├── MessageBubble.tsx        # Message render + reasoning toggle
│   │       ├── MergeModal.tsx           # Merge UI with streaming progress
│   │       └── SettingsModal.tsx        # API key management per provider
│   └── dist/                            # Built frontend served by FastAPI
└── start.sh                             # Startup script
```

### Database Schema (SQLite)
- **Chat**: id (UUID), title, provider, model, system_prompt, created_at, updated_at, messages (relationship)
- **Message**: id (UUID), chat_id (FK), role (user/assistant/system), content, reasoning_trace (nullable), created_at
- **APIKey**: id (UUID), provider (unique), encrypted_key, is_active, created_at
- **MergeHistory**: id (UUID), source_chat_ids (JSON), merged_chat_id (FK), merge_model, created_at

### Key Implementation Details

**Provider abstraction**: `BaseProvider` abstract class with `stream_completion()` returning `AsyncGenerator[StreamChunk, None]`. `StreamChunk` is a dataclass with `type` (content/reasoning/error/done/merge_complete) and `data` (string).

**Streaming DB session fix**: Streaming endpoints create their OWN db sessions via `async with async_session() as db` inside the generator function. Using `Depends(get_db)` fails because FastAPI closes the dependency session before the async generator runs.

**Reasoning trace capture**:
- Anthropic: Extended thinking enabled for Sonnet 4 and Opus 4 via `thinking={"type": "enabled", "budget_tokens": 10000}` with `temperature=1` (required). Captures `thinking_delta` events.
- OpenAI: o-series models (o1, o3, o4-mini) use `reasoning={"effort": "high", "summary": "auto"}`, `developer` role instead of `system`, `max_completion_tokens` instead of `max_tokens`.
- Gemini: No reasoning trace support currently.

**Completion context building** (`_build_message_history` in completion_service.py): When building the message history to send to a provider, reasoning traces from prior assistant messages are embedded in the content as `<reasoning_trace>...</reasoning_trace>` blocks. System messages (merge context markers) are converted to user messages with `[System context: ...]` prefix since not all providers handle system messages in the history.

**Current merge algorithm**: Full-context merge — copies ALL messages from source chats chronologically, adds system-level context boundary markers ("--- Context from: {title} ---"), preserves reasoning traces on every copied message, generates a brief 2-4 sentence AI synthesis bridge at the end (NOT a summary/rewrite). Sets a system prompt on the merged chat explaining the merge.

**Google Gemini SDK**: Uses the NEW `google-genai` SDK (not the deprecated `google-generativeai`). Pattern: `client = genai.Client(api_key=...)`, `client.aio.models.generate_content_stream(model=..., contents=..., config=types.GenerateContentConfig(...))`.

## Three Major Changes To Implement

### 1. File/Image Upload Support

The app is currently text-only. Add support for:
- **File upload endpoint** on the backend to accept and store attachments (images, PDFs, text files, code files)
- **Database schema change**: New `Attachment` model linked to messages (file_name, file_type, file_size, storage_path or blob, created_at)
- **Provider-level support**: Send images/files to all three providers:
  - OpenAI: base64 image_url content blocks in messages
  - Anthropic: base64 image content blocks
  - Gemini: `types.Part.from_image()` or `types.Part.from_bytes()`
- **Frontend UI**: Drag-and-drop zone, paste handler (Ctrl+V images), file picker button next to the text input, thumbnail previews for images, file chips for documents
- **Merge must carry over attachments** when copying messages between chats

### 2. RAG Vector Store Architecture for Chat Merging

**Replace the current merge approach** with a RAG-based system. The new architecture:

- **Each chat gets its own vector store** that's updated incrementally with every new message, file/attachment, model response, and reasoning trace
- **Every piece of content gets embedded**: user messages, assistant responses, reasoning traces (when available), and file contents (extracted text from PDFs, images via OCR/description, etc.)
- **Merging chats = merging their vector stores** into a new combined vector store for the merged chat
- **When continuing a merged chat**, the system uses RAG retrieval from the merged vector store to pull the most relevant context from all source conversations, rather than stuffing the entire message history into the context window (which hits token limits for long conversations)

**Vector store technology choice**: Since we're deploying to Vercel (serverless, stateless), we CANNOT use embedded/local vector stores like FAISS or local ChromaDB. Options:
- **Pinecone** (serverless, managed, great Python SDK, free tier available)
- **Upstash Vector** (serverless, deeply integrated with Vercel ecosystem, REST API)
- **Chroma Cloud** (hosted ChromaDB service)
- Use **namespaces or metadata filtering** to scope vectors per-chat, and merge by creating a new namespace that unions both source namespaces

**Embedding model**: Use the provider's own embedding API (OpenAI `text-embedding-3-small` is a good default) or a self-hosted sentence-transformers model.

**FAISS `merge_from()`** is the simplest merge approach if we were local, but since we're going serverless, the merge operation becomes: create new collection/namespace, copy all vectors from source collections into it. With Pinecone this can be done by querying all vectors from source namespaces and upserting into the target.

The RAG retrieval flow for completions becomes:
1. User sends message
2. Embed the user message
3. Query the chat's vector store for top-K most relevant chunks
4. Include retrieved context in the system prompt or as context messages
5. Send to the LLM provider as before
6. Embed and store the assistant response + reasoning trace

### 3. Convert to Vercel-Deployable Web App

**Vercel deployment constraints**:
- Serverless functions are STATELESS — no persistent filesystem
- SQLite won't work — need a cloud database (Vercel Postgres, Supabase, PlanetScale, Neon)
- Python serverless functions supported via `@vercel/python` runtime
- Can do zero-config FastAPI deployment (Vercel auto-detects FastAPI)
- OR traditional `vercel.json` with `api/index.py` entry point
- Frontend can be built as static and served from CDN
- Environment variables set in Vercel dashboard (API keys, DB connection strings)
- Max bundle size 250MB for Python functions
- SSE streaming works on Vercel with `StreamingResponse`

**Required changes**:
- **Database migration**: SQLite → Vercel Postgres (or Supabase/Neon PostgreSQL). Update SQLAlchemy connection string, switch from `aiosqlite` to `asyncpg` driver
- **File storage**: Local filesystem → cloud storage (Vercel Blob, S3, Cloudflare R2) for uploaded files
- **Project restructure** for Vercel:
  ```
  chat-merge-app/
  ├── api/
  │   └── index.py          # FastAPI app entry point
  ├── app/                   # Backend application code
  ├── frontend/              # React frontend (or move to root)
  ├── vercel.json            # Deployment config
  ├── requirements.txt       # Python deps
  └── package.json           # Frontend build
  ```
- **Environment variables**: All API keys, DB URLs, vector store credentials via env vars (not .env files)
- **CORS**: Update from `*` to actual domain
- **Auth**: Add basic auth (at minimum API key-based, or NextAuth/Clerk for proper user auth) since it's now a public web app
- **Landing page**: Create a front page describing the motivation — how people want to merge contexts across their various AI chats but no current interface supports it

### 4. GitHub Repo + AGENTS.md

- Initialize as a git repo
- Create a proper README.md with project description, architecture, setup instructions, deployment guide
- Create an AGENTS.md file following Vercel's AGENTS.md conventions (fetch https://vercel.com/docs/ai-agents or the vercel-labs/agent-skills repo for format reference)
- Push to GitHub (user's GitHub: can use `gh` CLI with GITHUB_TOKEN from ~/.zshrc)
- Connect to Vercel for deployment

## Bugs Fixed in Previous Sessions (Don't Re-Introduce)

1. **start.sh path bug**: Must use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` for reliable paths
2. **greenlet missing**: SQLAlchemy async requires `greenlet>=3.0.0` in requirements.txt
3. **google-generativeai deprecated**: Must use `google-genai>=1.0.0` with `google.genai` SDK
4. **SSE streaming session lifetime**: Streaming generators MUST create own DB sessions, NOT use `Depends(get_db)`
5. **EventSourceResponse issues**: Use `StreamingResponse` with manual `data: {json}\n\n` formatting
6. **Anthropic extended thinking**: Requires `temperature=1` when `thinking` parameter is set
7. **OpenAI o-series**: No temperature param, use `developer` role not `system`, use `max_completion_tokens`

## Development Environment

- **Python**: Use conda `work_env` environment via miniforge3, packages managed with `uv`
- **Node**: npm v11.6.2, Node v25.2.1
- **API keys**: In `~/.zshrc` as env vars (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, GITHUB_TOKEN)
- **Git user**: Quilee Simeon (qsimeon@mit.edu)

## Suggested Implementation Order

1. **Init git repo**, create .gitignore, initial commit of current working state
2. **Add file/image upload** (backend endpoint, Attachment model, provider support, frontend UI)
3. **Add vector store integration** (pick Pinecone or Upstash, create per-chat stores, embed on every message, RAG retrieval in completions)
4. **Rewrite merge to use vector store merging** instead of copying all messages
5. **Migrate database** from SQLite to PostgreSQL (Neon or Vercel Postgres)
6. **Migrate file storage** to cloud (Vercel Blob or S3)
7. **Restructure for Vercel deployment** (api/index.py, vercel.json, env vars)
8. **Add landing page** with project motivation
9. **Add basic auth** (at minimum)
10. **Create README.md and AGENTS.md**
11. **Push to GitHub and deploy to Vercel**

## Current State

The app runs locally. To start: `cd ~/chat-merge-app && ./start.sh` (installs deps, builds frontend, starts uvicorn on port 8000). All three providers work, streaming works, merge works, reasoning traces are captured and displayed with a toggleable UI. The dark-themed UI is clean and functional. The main gaps are: no file uploads, no RAG/vector store (merge is full-message-copy), no cloud deployment readiness.
