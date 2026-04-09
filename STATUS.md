# Project Status -- ChatMerge
> Last reviewed: 2026-04-08
> Reviewed by: Claude (resituate -- full project recovery)

## Project Overview

ChatMerge is a multi-provider AI chat app (OpenAI, Anthropic, Gemini) whose core innovation is **vector-fusion conversation merging**: merged chats fuse their Pinecone vector namespaces via nearest-neighbor averaging, and all context in the merged chat is delivered via RAG -- no message copying, no context-window blowup. Users supply their own API keys. Deployed to Railway.

**Live URL**: `https://chat-merge-app-production.up.railway.app`

## Architecture

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
|  +-- /api/api-keys        +-- encryption_service (Fernet)        |
|  +-- /health              +-- storage_service    (local files)   |
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
  |  (SQLAlchemy    |       |  (text-embedding-3-    |
  |   async)        |       |   small, 1536-dim)     |
  |                 |       |                         |
  |  Chat, Message, |       |  1 namespace per chat   |
  |  APIKey,        |       |  fuse_namespaces() for  |
  |  Attachment,    |       |  merged chats           |
  |  MergeHistory   |       |                         |
  +-----------------+       +-----------------------+
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

## Progress Summary

| Area | Status | Notes |
|------|--------|-------|
| Multi-provider chat (OpenAI / Anthropic / Gemini) | Done | All 3 providers stream correctly |
| File & image uploads | Done | Drag-drop/paste; images sent to provider vision APIs |
| Vector-fusion merge | Done | `fuse_namespaces()` nearest-neighbor + averaging |
| Merged-chat RAG context | Done | `is_merged` flag, always-RAG path in completion_service |
| Encrypted API key storage | Done | Fernet encryption with env-var key support |
| Onboarding CTA (landing page) | Done | "Get started in 2 steps" guide |
| Railway deployment | Done | Dockerfile builder, PostgreSQL plugin wired |
| FastAPI lifespan migration | Done | Modern `lifespan` context manager |
| Fernet key stability | Done | `encryption_service` reads `FERNET_KEY` env var first |
| Playwright test suite | Done | 9/9 passing (local) |
| Documentation | Done | AGENTS.md comprehensive; README accurate |

## Current Model Lists

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o4-mini, o3, o3-mini |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5-20251001 |
| Gemini | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash |

## Fixes Applied (2026-04-08)

- Fixed: `gemini-1.5-pro` 404 NOT_FOUND -- updated to gemini-2.5-flash/2.5-pro/2.0-flash
- Fixed: Frontend/backend OpenAI model list mismatch -- synced to o4-mini/o3/o3-mini
- Fixed: Updated Anthropic models to Claude 4.5/4.6 family
- Fixed: `datetime.utcnow` -> `datetime.now(timezone.utc)` in models.py (deprecated in 3.12)
- Fixed: `min_items` -> `min_length` in schemas.py (Pydantic v2 deprecation)
- Fixed: Added STATUS.md to .gitignore
- Removed: Stale `COWORK_CODE_HANDOFF.md`

## Human Action Items (verify if done since Feb 24)

- **Set `FERNET_KEY` on Railway** -- Without it every redeploy generates a new key, making all stored API keys unreadable. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- **Set `ALLOWED_ORIGINS` on Railway** -- Should be `https://chat-merge-app-production.up.railway.app`
- **Fix Railway auto-deploy** -- GitHub App permissions; manual redeploy needed until fixed
- **Mount persistent volume** at `/app/backend/uploads` for file upload durability

## Deployment

**Stack**: Dockerfile builder -> Python 3.11-slim + Node 20 -> builds React dist -> uv sync -> uvicorn with `--proxy-headers`

**Required env vars**: `DATABASE_URL` (auto-injected by Railway PostgreSQL), `ALLOWED_ORIGINS`, `FERNET_KEY`
